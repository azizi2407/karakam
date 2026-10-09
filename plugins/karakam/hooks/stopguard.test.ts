import { describe, expect, mock, test } from 'claude-code/testing'

import { haikuPrompt, isWorker, pickBackend, readHaiku, readJev } from './judge'

const EARLY = 'Parser done and 8 tests pass. Next I will wire it into the CLI and add the integration test.'
const FINAL = 'done — checks passed (12 tests). Files: src/parser.py, tests/test_parser.py. Log: /p/plan/logs/02.md'

describe('judge helpers', () => {
  test('judges Workers only, and picks the backend from the environment', () => {
    expect(isWorker('karakam:worker-high')).toBe(true)
    expect(isWorker('karakam:worker-opus-xhigh')).toBe(true)
    expect(isWorker('karakam:observer-high')).toBe(false)
    expect(isWorker('Explore')).toBe(false)
    expect(pickBackend(undefined, 'k')).toBe('jev')
    expect(pickBackend(undefined, undefined)).toBe('off')
    expect(pickBackend('haiku', undefined)).toBe('haiku')
    expect(pickBackend('OFF', 'k')).toBe('off')
    expect(pickBackend('jev', undefined)).toBe('off')
  })

  test('reads Jev and Haiku answers', () => {
    expect(readJev('{"answers":{"early":{"type":"noul","noul":0.93}}}')).toBe(0.93)
    expect(readJev('{"answers":{"early":{"probability":0.2}}}')).toBe(0.2)
    expect(readJev('not json')).toBeUndefined()
    expect(readHaiku('0.85')).toBe(0.85)
    expect(readHaiku('Probability: 1')).toBe(1)
    expect(readHaiku('yes')).toBeUndefined()
    expect(haikuPrompt(EARLY)).toContain(EARLY)
  })
})

const STOP = { stop_hook_active: false, agent_id: 'a1', agent_transcript_path: '/t', agent_type: 'karakam:worker-high' }

test('Jev sends an early-stopping Worker back once and lets a final report through', async ($, on) => {
  mock.env(on, { TYPESAFE_API_KEY: 'k' })
  const bodies: string[] = []
  on('http.fetch', (_$, e) => {
    bodies.push(String(e.init?.body))
    const p = String(e.init?.body).includes('Next I will') ? 0.93 : 0.04
    return { value: { status: 200, ok: true, headers: {}, text: JSON.stringify({ answers: { early: { type: 'noul', noul: p } } }) } } as never
  })
  on('classic.SubagentStop', () => ({}))

  expect((await $.classic.SubagentStop({ ...STOP, last_assistant_message: EARLY } as never)).block).toContain('Finish the step')
  expect((await $.classic.SubagentStop({ ...STOP, last_assistant_message: FINAL } as never)).block).toBeUndefined()
  // Already sent back once: let it stop.
  expect((await $.classic.SubagentStop({ ...STOP, stop_hook_active: true, last_assistant_message: EARLY } as never)).block).toBeUndefined()
  // Not a Worker: never judged.
  expect((await $.classic.SubagentStop({ ...STOP, agent_type: 'karakam:observer-high', last_assistant_message: EARLY } as never)).block).toBeUndefined()
  expect(bodies.length).toBe(2)
  expect(JSON.parse(bodies[0]!).questions.early.type).toBe('noul')
})

test('Haiku judges with KARAKAM_JUDGE=haiku; with no judge nothing is called', async ($, on) => {
  mock.env(on, { KARAKAM_JUDGE: 'haiku' })
  let calls = 0
  on('model.complete', () => { calls++; return { value: { isAnswered: true, text: '0.9', usage: {} } } as never })
  on('classic.SubagentStop', () => ({}))
  expect((await $.classic.SubagentStop({ ...STOP, last_assistant_message: EARLY } as never)).block).toContain('Finish the step')
  expect(calls).toBe(1)
})

test('without a key the guard stays out of the way', async ($, on) => {
  mock.env(on, {})
  on('http.fetch', () => { throw new Error('must not be called') })
  on('classic.SubagentStop', () => ({}))
  expect((await $.classic.SubagentStop({ ...STOP, last_assistant_message: EARLY } as never)).block).toBeUndefined()
})
