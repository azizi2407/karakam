import { describe, expect, mock, test } from 'claude-code/testing'

import { haikuPrompt, isOff, isWorker, readHaiku } from './judge'

const EARLY = 'Parser done and 8 tests pass. Next I will wire it into the CLI and add the integration test.'
const FINAL = 'done — checks passed (12 tests). Files: src/parser.py, tests/test_parser.py. Log: /p/plan/logs/02.md'

describe('judge helpers', () => {
  test('judges Workers only; KARAKAM_JUDGE=off turns it off', () => {
    expect(isWorker('karakam:worker-high')).toBe(true)
    expect(isWorker('karakam:worker-opus-xhigh')).toBe(true)
    expect(isWorker('karakam:observer-high')).toBe(false)
    expect(isWorker('Explore')).toBe(false)
    expect(isOff('OFF')).toBe(true)
    expect(isOff(undefined)).toBe(false)
  })

  test("reads Haiku's answer", () => {
    expect(readHaiku('0.85')).toBe(0.85)
    expect(readHaiku('Probability: 1')).toBe(1)
    expect(readHaiku('yes')).toBeUndefined()
    expect(haikuPrompt(EARLY)).toContain(EARLY)
  })
})

const STOP = { stop_hook_active: false, agent_id: 'a1', agent_transcript_path: '/t', agent_type: 'karakam:worker-high' }

test('Haiku sends an early-stopping Worker back once and lets a final report through', async ($, on) => {
  mock.env(on, {})
  const prompts: string[] = []
  on('model.complete', (_$, e) => {
    const prompt = String(e.prompt)
    prompts.push(prompt)
    return { value: { isAnswered: true, text: prompt.includes('Next I will') ? '0.93' : '0.04', usage: {} } } as never
  })
  on('classic.SubagentStop', () => ({}))

  expect((await $.classic.SubagentStop({ ...STOP, last_assistant_message: EARLY } as never)).block).toContain('Finish the step')
  expect((await $.classic.SubagentStop({ ...STOP, last_assistant_message: FINAL } as never)).block).toBeUndefined()
  // Already sent back once: let it stop.
  expect((await $.classic.SubagentStop({ ...STOP, stop_hook_active: true, last_assistant_message: EARLY } as never)).block).toBeUndefined()
  // Not a Worker: never judged.
  expect((await $.classic.SubagentStop({ ...STOP, agent_type: 'karakam:observer-high', last_assistant_message: EARLY } as never)).block).toBeUndefined()
  expect(prompts.length).toBe(2)
})

test('KARAKAM_JUDGE=off keeps the guard out of the way', async ($, on) => {
  mock.env(on, { KARAKAM_JUDGE: 'off' })
  on('model.complete', () => { throw new Error('must not be called') })
  on('classic.SubagentStop', () => ({}))
  expect((await $.classic.SubagentStop({ ...STOP, last_assistant_message: EARLY } as never)).block).toBeUndefined()
})
