// Karagöz progress pane: the plan's steps from progress.md, and under each
// step its micro-steps — every Worker and Observer run and the git checkpoint —
// as the Coordinator spawns them. Opens when the karagoz skill starts;
// `/karakam-progress` opens it by hand.
import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { KarakamMicro, KarakamStep } from '../types'
import { classifySpawn, duration, gitStep, parseLedger, verdict } from './ledger'

const PANE = 'karakam'
const ledger = atom({ plugin: 'karakam', key: 'ledger' } as const, null)
const micro = atom({ plugin: 'karakam', key: 'micro' } as const, [])

type Look = { icon: string; color?: string; dim?: boolean }
const PENDING: Look = { icon: '·', dim: true }
const STEP_LOOK: Record<string, Look> = {
  done: { icon: '✓', color: 'success' },
  in_progress: { icon: '▶', color: 'warning' },
  refactoring: { icon: '↻', color: 'warning' },
  blocked: { icon: '✗', color: 'error' },
  pending: PENDING,
}
const MICRO_LOOK: Record<KarakamMicro['status'], { icon: string; color: string }> = {
  running: { icon: '…', color: 'warning' },
  pass: { icon: '✓', color: 'success' },
  done: { icon: '✓', color: 'subtle' },
  fail: { icon: '✗', color: 'error' },
}

const openPane = ($: EngineInterface) => $.ui.open({ id: PANE, title: 'Karagöz' })
const isLedgerPath = (path: string) => /(^|\/)progress\.md$/.test(path)

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'karakam-progress',
      description: 'Show the running karagoz plan: steps and their micro-steps',
    })
    return next(e)
  })

  on('command.run', { command: 'karakam-progress' }, async $ => {
    await openPane($)
    return { text: 'Karagöz progress pane opened.' }
  })

  // The skill starting (every /loop tick) is the cue to show the pane.
  on('tool.call', { tool: 'Skill' }, async ($, e, next) => {
    if (/(^|:)karagoz$/.test(e.skill)) {
      const opened = await openPane($)
      if (!opened.isPlaced) $.ui.status('karagoz running — /karakam-progress shows its steps')
    }
    return next(e)
  })

  // Every read or write of the ledger refreshes the step list.
  on('tool.call', async ($, e, next) => {
    const ran = await next(e)
    if ((e.tool === 'Read' || e.tool === 'Edit' || e.tool === 'Write') && isLedgerPath(e.file_path) && !ran.deny) {
      const path = e.file_path
      try {
        const steps: KarakamStep[] = parseLedger(await $.fs.read(path))
        const before = await read($, ledger)
        if (before && before.path !== path) await update($, micro, () => [])
        await update($, ledger, () => ({ path, steps }))
      } catch {
        // an unreadable ledger leaves the last one on screen
      }
    }
    return ran
  })

  // Git checkpoints: `stepgit.sh commit|land "karagoz step NN: …"`.
  on('tool.call', { tool: 'Bash' }, async ($, e, next) => {
    const git = gitStep(e.command)
    if (!git || !e.tool_use_id) return next(e)
    const id = e.tool_use_id
    const started = await $.clock.now()
    await update($, micro, list => [...list, { ...git, id, status: 'running' as const }])
    const ran = await next(e)
    const ms = (await $.clock.now()) - started
    const status: KarakamMicro['status'] = ran.deny || ran.isError ? 'fail' : 'pass'
    await update($, micro, list => list.map(m => (m.id === id ? { ...m, status, ms } : m)))
    return ran
  })

  // Worker and Observer runs start here…
  on('agent.spawn', async ($, e, next) => {
    const spawned = await next(e)
    const kind = classifySpawn(e.subagentType, e.prompt, e.description)
    if (kind && !spawned.deny && spawned.agentId) {
      const id = spawned.agentId
      await update($, micro, list => [...list, { ...kind, id, status: 'running' as const }].slice(-300))
    }
    return spawned
  })

  // …and end here, with their verdict.
  on('turn.complete', async ($, e, next) => {
    const id = e.agentId
    if (id) {
      const list = await read($, micro)
      const run = list.find(m => m.id === id && m.status === 'running')
      if (run) {
        const status = e.isAborted ? 'fail' : verdict(run.kind, e.answer)
        await update($, micro, l => l.map(m => (m.id === id ? { ...m, status, ms: e.durationMs } : m)))
      }
    }
    return next(e)
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text } = $.ui.resolve(e)
    const plan = await read($, ledger)
    const runs = await read($, micro)
    const steps: KarakamStep[] = plan?.steps ?? []
    const ids = [...new Set([...steps.map(s => s.id), ...runs.map(m => m.step)])].sort()
    const width = Math.max(10, e.props.bodyColumns)

    if (ids.length === 0) {
      return <Text dimColor>Waiting for karagoz to read its plan…</Text>
    }

    const count = (status: string) => steps.filter(s => s.status === status).length
    const done = count('done')
    const total = steps.length || ids.length
    const barWidth = Math.max(4, Math.min(30, width - 24))
    const filled = Math.round((done / Math.max(1, total)) * barWidth)
    const active = count('in_progress') + count('refactoring')
    const blocked = count('blocked')

    return (
      <Box flexDirection="column">
        {plan && (
          <Text dimColor wrap="truncate-start">
            {plan.path}
          </Text>
        )}
        <Text wrap="truncate">
          <Text color="success">{'█'.repeat(filled)}</Text>
          <Text dimColor>{'░'.repeat(barWidth - filled)}</Text> {done}/{total} done
          {active > 0 ? ` · ${active} running` : ''}
          {blocked > 0 ? ` · ${blocked} blocked` : ''}
        </Text>
        {ids.map(id => {
          const step = steps.find(s => s.id === id)
          const look = STEP_LOOK[step?.status ?? 'pending'] ?? PENDING
          const mine = runs.filter(m => m.step === id)
          return (
            <Box flexDirection="column" marginTop={1}>
              <Text wrap="truncate" dimColor={look.dim}>
                <Text color={look.color}>{look.icon}</Text> <Text bold>{id}</Text> {step?.status ?? 'running'}
                {step ? <Text dimColor> · {step.effort}{step.critical ? ' · critical' : ''}</Text> : ''}
                {step?.note ? <Text dimColor> — {step.note}</Text> : ''}
              </Text>
              {mine.map((m, i) => {
                const ml = MICRO_LOOK[m.status]
                return (
                  <Text wrap="truncate">
                    {'  '}
                    {i === mine.length - 1 ? '└ ' : '├ '}
                    <Text color={ml.color}>{ml.icon}</Text> {m.label}
                    {m.status === 'fail' && m.kind === 'observer' ? <Text color="error"> FAIL</Text> : ''}
                    {m.ms !== undefined ? <Text dimColor> {duration(m.ms)}</Text> : ''}
                  </Text>
                )
              })}
            </Box>
          )
        })}
      </Box>
    )
  })
}
