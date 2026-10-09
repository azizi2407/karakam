// Worker stop guard: when a karakam Worker stops on a progress summary instead
// of a final report, send it back once to finish the step in the same context
// — cheaper than the refactor round a "not done" reply would cost.
//
// Haiku judges, through the session's own client, for about $0.0001 a stop;
// KARAKAM_JUDGE=off turns the guard off. Any failure lets the stop through.
import type { EngineInterface, On } from 'claude-code'

import { BLOCK_AT, SEND_BACK, haikuPrompt, isOff, isWorker, readHaiku } from './judge'

async function earlyStop($: EngineInterface, reply: string): Promise<number | undefined> {
  if (isOff(await $.env.get('KARAKAM_JUDGE'))) return undefined
  const r = await $.model.complete({ model: 'haiku', prompt: haikuPrompt(reply), maxTokens: 16 })
  return r.isAnswered ? readHaiku(r.text) : undefined
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
