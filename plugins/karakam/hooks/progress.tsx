// Karagöz progress pane: the plan's steps from progress.md, and under each
// step its micro-steps — every Worker and Observer run and the git checkpoint —
// as the Coordinator spawns them. Opens when the karagoz skill starts;
// `/karakam-progress` opens it by hand.
//
// Compact by default: a narrow dock on the right of a fullscreen transcript,
// its content at the top — a one-line step map, the tally, and only the steps
// in motion. `d` (or the button) toggles the full list of every step.
import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register } from 'claude-code'

import type { KarakamMicro, KarakamStep } from '../types'
import { classifySpawn, duration, gitStep, openDeps, parseLedger, stateOf, verdict } from './ledger'
import type { StepState } from './ledger'

const PANE = 'karakam'
const ledger = atom({ plugin: 'karakam', key: 'ledger' } as const, null)
const micro = atom({ plugin: 'karakam', key: 'micro' } as const, [])
const isExpanded = atom({ plugin: 'karakam', key: 'isExpanded' } as const, false)

type Look = { icon: string; color?: string; dim?: boolean }
// One glyph per step state, shared by the step map and the step rows.
const LOOK: Record<StepState, Look> = {
  done: { icon: '✓', color: 'success' },
  running: { icon: '▶', color: 'warning' },
  refactoring: { icon: '↻', color: 'warning' },
  blocked: { icon: '✗', color: 'error' },
  ready: { icon: '○', color: 'suggestion' },
  waiting: { icon: '·', dim: true },
}
const ORDER: StepState[] = ['done', 'running', 'refactoring', 'ready', 'waiting', 'blocked']
const PER_ROW = 10
// Body columns asked of the dock, and rows of the inline block, per view.
const SIZE = { compact: { columns: 30, rows: 7 }, expanded: { columns: 72, rows: 24 } }
const MICRO_LOOK: Record<KarakamMicro['status'], { icon: string; color: string }> = {
  running: { icon: '…', color: 'warning' },
  pass: { icon: '✓', color: 'success' },
  done: { icon: '✓', color: 'subtle' },
  fail: { icon: '✗', color: 'error' },
}

const openPane = async ($: EngineInterface) =>
  $.ui.open({ id: PANE, title: 'Karagöz', ...SIZE[(await read($, isExpanded)) ? 'expanded' : 'compact'] })
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
    const { Box, Button, Text } = $.ui.resolve(e)
    const expanded = await read($, isExpanded)
    const plan = await read($, ledger)
    const runs = await read($, micro)
    const steps: KarakamStep[] = plan?.steps ?? []
    const ids = [...new Set([...steps.map(s => s.id), ...runs.map(m => m.step)])].sort()

    if (ids.length === 0) {
      return <Text dimColor>Waiting for karagoz to read its plan…</Text>
    }

    // A step known only from a running micro-step (no ledger read yet) counts as running.
    const stateById = new Map<string, StepState>(
      ids.map(id => {
        const step = steps.find(s => s.id === id)
        return [id, step ? stateOf(step, steps) : 'running']
      }),
    )
    const rows: string[][] = []
    for (let i = 0; i < ids.length; i += PER_ROW) rows.push(ids.slice(i, i + PER_ROW))
    const tally = ORDER.map(st => [st, [...stateById.values()].filter(v => v === st).length] as const)
      .filter(([, n]) => n > 0)

    const toggle = (
      <Button
        key="toggle"
        plain
        hotkey="d"
        label={expanded ? 'less' : 'details'}
        onPress={async () => {
          const next = !(await read($, isExpanded))
          await update($, isExpanded, () => next)
          await $.ui.open({ id: PANE, title: 'Karagöz', ...SIZE[next ? 'expanded' : 'compact'] })
        }}
      />
    )
    const map = rows.map(row => (
      <Text wrap="truncate">
        <Text dimColor>{row[0]} </Text>
        {row.map(id => {
          const look = LOOK[stateById.get(id) ?? 'waiting']
          return <Text color={look.color} dimColor={look.dim}>{expanded ? ' ' : ''}{look.icon}</Text>
        })}
      </Text>
    ))

    if (!expanded) {
      // Only what moves: running and refactoring steps with their latest micro-step, then blocked ones.
      const moving = ids.filter(id => ['running', 'refactoring', 'blocked'].includes(stateById.get(id) ?? ''))
      return (
        <Box flexDirection="column">
          {map}
          <Text wrap="truncate">
            {tally.map(([st, n]) => (
              <Text>
                <Text color={LOOK[st].color} dimColor={LOOK[st].dim}>{LOOK[st].icon}</Text>
                {n}{' '}
              </Text>
            ))}
          </Text>
          {moving.map(id => {
            const look = LOOK[stateById.get(id) ?? 'waiting']
            const last = runs.filter(m => m.step === id).at(-1)
            return (
              <Text wrap="truncate">
                <Text color={look.color}>{look.icon}</Text> <Text bold>{id}</Text>{' '}
                {last ? (
                  <Text>
                    <Text color={MICRO_LOOK[last.status].color}>{MICRO_LOOK[last.status].icon}</Text> {last.label}
                  </Text>
                ) : (
                  <Text dimColor>{stateById.get(id)}</Text>
                )}
              </Text>
            )
          })}
          {toggle}
        </Box>
      )
    }

    return (
      <Box flexDirection="column">
        {plan && (
          <Text dimColor wrap="truncate-start">
            {plan.path}
          </Text>
        )}
        {map}
        <Text wrap="truncate">
          {tally.map(([st, n], i) => (
            <Text>
              {i > 0 ? '  ' : ''}
              <Text color={LOOK[st].color} dimColor={LOOK[st].dim}>{LOOK[st].icon}</Text> {n} {st}
            </Text>
          ))}
        </Text>
        {ids.map(id => {
          const step = steps.find(s => s.id === id)
          const look = LOOK[stateById.get(id) ?? 'waiting']
          const waitsOn = step ? openDeps(step, steps) : []
          const mine = runs.filter(m => m.step === id)
          return (
            <Box flexDirection="column" marginTop={1}>
              <Text wrap="truncate" dimColor={look.dim}>
                <Text color={look.color}>{look.icon}</Text> <Text bold>{id}</Text> {stateById.get(id)}
                {step ? <Text dimColor> · {step.effort}{step.critical ? ' · critical' : ''}</Text> : ''}
                {waitsOn.length > 0 ? <Text dimColor> · waits on {waitsOn.join(', ')}</Text> : ''}
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
        <Box marginTop={1}>{toggle}</Box>
      </Box>
    )
  })
}
