import { describe, expect, mock, test } from 'claude-code/testing'

import { classifySpawn, gitStep, isLedger, parseLedger, planDirsIn, stateOf, verdict } from './ledger'

const LEDGER = `# Progress

| step | status | depends_on | effort | critical | file | note |
|------|--------|-----------|--------|----------|------|------|
| 01 | done | - | high | no | steps/01.md | parser, 12 tests |
| 02 | refactoring | 01 | high | yes | steps/02.md | refactor 1/3 @opus-high |
| 03 | pending | 02 | medium | no | steps/03.md | |
`

// Done out of order: 01, 02, 05 and 07 finished while 03, 04 and 06 wait.
const GRAPH = `| step | status | depends_on | effort | critical | file | note |
|------|--------|-----------|--------|----------|------|------|
| 01 | done | - | high | no | steps/01.md | |
| 02 | done | - | high | no | steps/02.md | |
| 03 | pending | 02 | high | no | steps/03.md | |
| 04 | pending | 03 | medium | no | steps/04.md | |
| 05 | done | - | high | no | steps/05.md | |
| 06 | pending | 05, 08 | high | no | steps/06.md | |
| 07 | done | - | high | no | steps/07.md | |
| 08 | refactoring | 07 | high | yes | steps/08.md | refactor 1/3 @opus-high |
| 09 | pending | 08 | low | no | steps/09.md | |
| 10 | blocked | 01 | high | no | steps/10.md | plan-level fault |
`

describe('ledger helpers', () => {
  test('finds the plan from absolute step paths, and knows a ledger from any progress.md', () => {
    expect(planDirsIn('Apply /home/a/repo/docs/karakam/x/steps/02.md; log to /home/a/repo/docs/karakam/x/logs/02.md'))
      .toEqual(['/home/a/repo/docs/karakam/x'])
    expect(planDirsIn('cd w && cat /r/plan/.worktrees/02/plan/progress.md')).toEqual([])
    expect(isLedger(GRAPH)).toBe(true)
    expect(isLedger('# Progress\n\n- [x] wrote the intro\n- [ ] 02 review\n')).toBe(false)
  })

  test('parses the step rows', () => {
    expect(parseLedger(LEDGER)).toEqual([
      { id: '01', status: 'done', dependsOn: [], effort: 'high', critical: false, note: 'parser, 12 tests' },
      { id: '02', status: 'refactoring', dependsOn: ['01'], effort: 'high', critical: true, note: 'refactor 1/3 @opus-high' },
      { id: '03', status: 'pending', dependsOn: ['02'], effort: 'medium', critical: false, note: '' },
    ])
  })

  test('a pending step is ready once its dependencies are done, else waiting', () => {
    const steps = parseLedger(GRAPH)
    expect(steps.map(s => stateOf(s, steps)).join(' ')).toBe(
      'done done ready waiting done waiting done refactoring waiting blocked',
    )
  })

  test('recognises Worker, refactor Worker and Observer spawns', () => {
    expect(classifySpawn('karakam:worker-high', 'Apply /p/plan/steps/08.md', 'Step 08 worker')).toEqual({
      step: '08', kind: 'worker', label: 'worker-high · sonnet',
    })
    expect(classifySpawn('karakam:worker-opus-high', 'Refactor round 1', 'Refactor round 1 step 02')).toEqual({
      step: '02', kind: 'worker', label: 'worker-opus-high · refactor',
    })
    expect(classifySpawn('karakam:observer-high', 'Audit /p/plan/steps/02.md, lens: behavior', 'Step 02 observer'))
      .toEqual({ step: '02', kind: 'observer', label: 'observer-high · behavior' })
    expect(classifySpawn('Explore', 'steps/02.md', 'look around')).toBeUndefined()
  })

  test('reads verdicts and git checkpoints', () => {
    expect(verdict('observer', 'FAIL: the CLI crashes on --ay 0000-01')).toBe('fail')
    expect(verdict('observer', 'PASS — all checks ran')).toBe('pass')
    expect(verdict('worker', 'not done; checks failed')).toBe('fail')
    expect(gitStep('bash stepgit.sh land plan/.worktrees/04 karagoz-step-04 "karagoz step 04: CLI" a b'))
      .toEqual({ step: '04', kind: 'git', label: 'land (commit + merge)' })
    expect(gitStep('git status')).toBeUndefined()
  })
})

const PANE_PROPS = {
  title: 'Karagöz', isFocused: false, bodyColumns: 80, placement: 'dock' as const,
  scroll: { top: 0, bodyRows: 30 } as never, view: {} as never,
}
const PLAN = '/home/a/repo/docs/karakam/plan'
const OTHER = `# progress\n\n| step | status | depends_on | effort | critical | file | note |\n|---|---|---|---|---|---|---|\n| 01 | done | - | low | no | steps/01.md | |\n`

test('the pane follows the right plan and every sub-agent', async ($, on) => {
  mock.clock(on)
  let ledgerText = GRAPH
  let mtimeMs = 1
  on('fs.read', (_$, e) => ({ value: e.path === `${PLAN}/progress.md` ? ledgerText : OTHER }) as never)
  on('fs.stat', () => ({ value: { kind: 'file', size: 1, mtimeMs, isLink: false } }) as never)
  on('tool.call', () => ({ result: {} as never, text: 'ok' }))
  on('agent.spawn', (_$, e) => ({ model: e.subagentType.includes('opus') ? 'claude-opus-5-5' : 'claude-sonnet-5-5', agentId: e.description }))
  on('turn.complete', (_$, e) => ({ text: e.answer }))
  on('ui.open', () => ({ value: { isPlaced: true } }) as never)

  const spawn = (subagentType: string, description: string, prompt: string) =>
    $.agent.spawn({
      tool_use_id: description, prompt, description, subagentType,
      provider: { plugin: 'karakam', tier: 'user' }, parentModel: 'opus', background: true, fork: false,
    })
  const texts = async (ui: { findAll: (q: { type: string }) => Promise<{ text: string }[]> }) =>
    (await ui.findAll({ type: 'Text' })).map(t => t.text)

  // The Coordinator's spawns name the plan by absolute path; nothing read the ledger with Read.
  await spawn('karakam:worker-high', 'Worker step 08', `Apply ${PLAN}/steps/08.md, log ${PLAN}/logs/08.md`)
  await spawn('karakam:worker-low', 'Worker step 03', `Apply ${PLAN}/steps/03.md`)
  // A sub-agent reading some other progress.md changes nothing.
  await $.tool.call({ tool: 'Read', file_path: '/home/a/repo/docs/karakam/old/progress.md', agentId: 'Worker step 08' } as never)
  await $.turn.complete({
    answer: 'done, checks passed', durationMs: 72_000, isAborted: false, turnId: 't', agentId: 'Worker step 03', reason: 'answer',
    usage: { model: 'claude-sonnet-5-5', input_tokens: 1000, output_tokens: 3200, cache_read_input_tokens: 40000, cache_creation_input_tokens: 1600 },
  } as never)
  await spawn('karakam:observer-medium', 'Observer step 03', `Audit ${PLAN}/steps/03.md`)

  let terminal: Awaited<ReturnType<typeof $.ui.mount>> | undefined
  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({ plugin: 'karakam', surface, component: 'Pane', requestId: 'karakam', props: PANE_PROPS })
    if (surface === 'terminal') terminal = ui
    const compact = await texts(ui)
    expect(compact.some(t => t.startsWith('01') && t.includes('✓✓○·✓·✓↻·✗'))).toBe(true)
    expect(compact.some(t => t.includes('▶ 08 worker-high · sonnet'))).toBe(true)
    expect(compact.some(t => t.includes('▶ 03 observer-medium'))).toBe(true)
    expect(compact.some(t => t.includes('10') && t.includes('blocked'))).toBe(true)

    await ui.press({ key: 'toggle' })
    const full = await texts(ui)
    expect(full.some(t => t.includes(`${PLAN}/progress.md`))).toBe(true)
    expect(full.some(t => t.includes('06 waiting') && t.includes('waits on 08'))).toBe(true)
    expect(full.some(t => t.includes('├ ✓ worker-low · sonnet') && t.includes('1m 12s') && t.includes('sonnet-5.5')
      && t.includes('45.8k tokens (3.2k out)'))).toBe(true)
    expect(full.some(t => t.includes('└ … observer-medium') && t.includes('sonnet-5.5'))).toBe(true)
    await ui.press({ key: 'toggle' })
  }

  // The Coordinator marks 08 done from Bash: the pane follows the file, not the tool.
  ledgerText = GRAPH.replace('| 08 | refactoring |', '| 08 | done |')
  mtimeMs = 2
  await $.tool.call({ tool: 'Bash', command: `sed -i 's/refactoring/done/' ${PLAN}/progress.md` } as never)
  expect((await texts(terminal!)).some(t => t.startsWith('01') && t.includes('✓✓○·✓○✓✓○✗'))).toBe(true)
})
