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
import { classifySpawn, duration, gitStep, shortModel, tokens, isLedger, openDeps, parseLedger, planDirsIn, stateOf, verdict } from './ledger'
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

// The ledger. Only the main loop's own traces name the plan — a sub-agent may
// read some other progress.md — and a file counts only if it parses as one.
// It is then followed by its mtime, whoever writes it: the Coordinator often
// updates it from Bash, not with Edit.
let seen = { path: '', mtimeMs: -1 }
async function refresh($: EngineInterface) {
  const plan = await read($, ledger)
  if (!plan) return
  try {
    const { mtimeMs } = await $.fs.stat(plan.path)
    if (plan.path === seen.path && mtimeMs === seen.mtimeMs) return
    const text = await $.fs.read(plan.path)
    seen = { path: plan.path, mtimeMs }
    if (isLedger(text)) await update($, ledger, () => ({ path: plan.path, steps: parseLedger(text) }))
  } catch {
    // gone or unreadable: keep the last one on screen
  }
}
async function discover($: EngineInterface, text: string) {
  const current = (await read($, ledger))?.path
  for (const dir of planDirsIn(text)) {
    const path = `${dir}/progress.md`
    if (path === current) return
    try {
      const body = await $.fs.read(path)
      if (!isLedger(body)) continue
      if (current) await update($, micro, () => [])   // a different plan: start its micro-steps afresh
      seen = { path: '', mtimeMs: -1 }
      await update($, ledger, () => ({ path, steps: parseLedger(body) }))
      return
    } catch {
      // not there: try the next one
    }
  }
}


export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'karakam-progress',
      description: 'Show the running karagoz plan: steps and their micro-steps',
    })
    // While a plan is on screen: follow the ledger, and tick the running timers.
    $.clock.every(4000, () => {
      void (async () => {
        await refresh($)
        if ((await read($, micro)).some(m => m.status === 'running')) $.ui.invalidate('ui.render')
      })()
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

  on('tool.call', async ($, e, next) => {
    const ran = await next(e)
    if (e.agentId === undefined) {
      if (e.tool === 'Read' || e.tool === 'Edit' || e.tool === 'Write') await discover($, e.file_path)
      else if (e.tool === 'Bash' && e.command.includes('progress.md')) await discover($, e.command)
      await refresh($)
    }
    return ran
  })


  // Git checkpoints: `stepgit.sh commit|land "karagoz step NN: …"`.
  on('tool.call', { tool: 'Bash' }, async ($, e, next) => {
    const git = gitStep(e.command)
    if (!git || !e.tool_use_id) return next(e)
    const id = e.tool_use_id
    const started = await $.clock.now()
    await update($, micro, list => [...list, { ...git, id, status: 'running' as const, startedAt: started }])
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
      await discover($, e.prompt)
      const id = spawned.agentId
      const startedAt = await $.clock.now()
      const model = spawned.model
      await update($, micro, list => [...list, { ...kind, id, status: 'running' as const, startedAt, model }].slice(-300))
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
        const u = e.usage
        const usage = u
          ? {
              model: u.model,
              tokens: u.input_tokens + u.output_tokens + u.cache_read_input_tokens + u.cache_creation_input_tokens,
              outTokens: u.output_tokens,
            }
          : {}
        await update($, micro, l => l.map(m => (m.id === id ? { ...m, status, ms: e.durationMs, ...usage } : m)))
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
      // What is happening now: every running sub-agent or checkpoint, by name, step and elapsed time;
      // then steps in motion with nothing running (between rounds), and blocked ones.
      const now = await $.clock.now()
      const running = runs.filter(m => m.status === 'running').sort((a, b) => a.step.localeCompare(b.step))
      const idle = ids.filter(
        id => ['running', 'refactoring', 'blocked'].includes(stateById.get(id) ?? '') && !running.some(m => m.step === id),
      )
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
          {running.map(m => (
            <Text wrap="truncate">
              <Text color="warning">▶</Text> <Text bold>{m.step}</Text> {m.label}
              {m.startedAt !== undefined ? <Text dimColor> {duration(now - m.startedAt)}</Text> : ''}
            </Text>
          ))}
          {idle.map(id => {
            const look = LOOK[stateById.get(id) ?? 'waiting']
            return (
              <Text wrap="truncate">
                <Text color={look.color}>{look.icon}</Text> <Text bold>{id}</Text> <Text dimColor>{stateById.get(id)}</Text>
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
                    {m.model ? <Text dimColor> · {shortModel(m.model)}</Text> : ''}
                    {m.tokens !== undefined ? (
                      <Text dimColor> · {tokens(m.tokens)} tokens ({tokens(m.outTokens ?? 0)} out)</Text>
                    ) : ''}
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
