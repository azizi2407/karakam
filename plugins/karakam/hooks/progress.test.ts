import { describe, expect, test } from 'claude-code/testing'

import { classifySpawn, gitStep, parseLedger, verdict } from './ledger'

const LEDGER = `# Progress

| step | status | depends_on | effort | critical | file | note |
|------|--------|-----------|--------|----------|------|------|
| 01 | done | - | high | no | steps/01.md | parser, 12 tests |
| 02 | refactoring | 01 | high | yes | steps/02.md | refactor 1/3 @opus-high |
| 03 | pending | 02 | medium | no | steps/03.md | |
`

describe('ledger helpers', () => {
  test('parses the step rows', () => {
    expect(parseLedger(LEDGER)).toEqual([
      { id: '01', status: 'done', effort: 'high', critical: false, note: 'parser, 12 tests' },
      { id: '02', status: 'refactoring', effort: 'high', critical: true, note: 'refactor 1/3 @opus-high' },
      { id: '03', status: 'pending', effort: 'medium', critical: false, note: '' },
    ])
  })

  test('recognises Worker, refactor Worker and Observer spawns', () => {
    expect(classifySpawn('karakam:worker-high', 'Apply /p/plan/steps/02.md', 'Step 02 worker')).toEqual({
      step: '02', kind: 'worker', label: 'worker sonnet high',
    })
    expect(classifySpawn('karakam:worker-opus-high', 'Refactor round 1', 'Refactor round 1 step 02')).toEqual({
      step: '02', kind: 'worker', label: 'worker opus high (refactor)',
    })
    expect(classifySpawn('karakam:observer-high', 'Audit /p/plan/steps/02.md, lens: behavior', 'Step 02 observer'))
      .toEqual({ step: '02', kind: 'observer', label: 'observer high · behavior' })
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

test('the pane shows each step with its micro-steps', async ($, on) => {
  on('fs.read', () => ({ value: LEDGER }) as never)
  on('tool.call', () => ({ result: {} as never, text: 'ok' }))
  on('agent.spawn', (_$, e) => ({ model: 'm', agentId: `${e.subagentType}#${e.description}` }))
  on('turn.complete', (_$, e) => ({ text: e.answer }))

  await $.tool.call({ tool: 'Read', file_path: '/p/plan/progress.md' })
  const spawn = async (subagentType: string, description: string, prompt: string) => {
    const r = await $.agent.spawn({
      tool_use_id: description, prompt, description, subagentType,
      provider: { plugin: 'karakam', tier: 'user' }, parentModel: 'opus', background: true, fork: false,
    })
    return r.deny ? '' : (r.agentId ?? '')
  }
  const w = await spawn('karakam:worker-high', 'Step 02 worker', 'Apply /p/plan/steps/02.md')
  const o = await spawn('karakam:observer-high', 'Step 02 behavior observer', 'Audit /p/plan/steps/02.md, lens behavior')
  await spawn('karakam:worker-opus-high', 'Refactor round 1 step 02', 'Fix per /p/plan/reports/02-observer-behavior.md')
  await $.turn.complete({ answer: 'done, checks passed', durationMs: 72_000, isAborted: false, turnId: 't', agentId: w, reason: 'answer' })
  await $.turn.complete({ answer: 'FAIL: crashes on empty input', durationMs: 30_000, isAborted: false, turnId: 't', agentId: o, reason: 'answer' })

  for (const surface of ['terminal', 'desktop'] as const) {
    const ui = await $.ui.mount({
      plugin: 'karakam', surface, component: 'Pane', requestId: 'karakam',
      props: { title: 'Karagöz', isFocused: false, bodyColumns: 80, placement: 'dock', scroll: { top: 0, bodyRows: 30 } as never, view: {} as never },
    })
    const texts = (await ui.findAll({ type: 'Text' })).map(t => t.text)
    expect(texts.some(t => t.includes('1/3 done'))).toBe(true)
    expect(texts.some(t => t.includes('02 refactoring') && t.includes('critical'))).toBe(true)
    expect(texts.some(t => t.includes('├ ✓ worker sonnet high') && t.includes('1m 12s'))).toBe(true)
    expect(texts.some(t => t.includes('observer high · behavior') && t.includes('FAIL'))).toBe(true)
    expect(texts.some(t => t.includes('└ … worker opus high (refactor)'))).toBe(true)
  }
})
