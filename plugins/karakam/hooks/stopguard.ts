// Worker stop guard: when a karakam Worker stops on a progress summary instead
// of a final report, send it back once to finish the step in the same context
// — cheaper than the refactor round a "not done" reply would cost.
//
// The judge is TypeSafe's Jev when TYPESAFE_API_KEY is set (a typed yes/no
// with its probability), else Haiku through the session's own client (about
// $0.0001 a judgment); KARAKAM_JUDGE=haiku|jev|off picks one. Any failure lets
// the stop through.
import type { EngineInterface, On } from 'claude-code'

import { BLOCK_AT, JEV_URL, SEND_BACK, haikuPrompt, isWorker, jevBody, pickBackend, readHaiku, readJev } from './judge'

async function earlyStop($: EngineInterface, reply: string): Promise<number | undefined> {
  const backend = pickBackend(await $.env.get('KARAKAM_JUDGE'), await $.env.get('TYPESAFE_API_KEY'))
  if (backend === 'jev') {
    const key = await $.env.get('TYPESAFE_API_KEY')
    const r = await $.http.fetch(JEV_URL, {
      method: 'POST',
      headers: { Authorization: `Bearer ${key}`, 'Content-Type': 'application/json' },
      body: jevBody(reply),
    })
    return r.ok ? readJev(r.text) : undefined
  }
  if (backend === 'haiku') {
    const r = await $.model.complete({ model: 'haiku', prompt: haikuPrompt(reply), maxTokens: 16 })
    return r.isAnswered ? readHaiku(r.text) : undefined
  }
  return undefined
}

// A plugin loads one hooks module: progress.tsx calls this from its `register`.
export function registerStopGuard(on: On): void {
  on('classic.SubagentStop', async ($, e, next) => {
    const result = await next(e)
    // Once per stop: a Worker already sent back finishes as it sees fit.
    if (result.block || e.stop_hook_active || !isWorker(e.agent_type) || !e.last_assistant_message) return result
    try {
      const p = await earlyStop($, e.last_assistant_message)
      return p !== undefined && p >= BLOCK_AT ? { ...result, block: SEND_BACK } : result
    } catch {
      return result
    }
  })
}
