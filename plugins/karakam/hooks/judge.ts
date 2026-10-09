// Pure helpers for the Worker stop guard: the question asked, how Jev's and
// Haiku's answers are read, and when a stop is sent back.

export const JEV_URL = 'https://api.typesafe.ai/v1/systemone'

export type Backend = 'jev' | 'haiku' | 'off'

// The guard judges only first-pass and refactor Workers, never Observers or critics.
export const isWorker = (agentType: string): boolean => /^(karakam:)?worker-/.test(agentType)

export const EARLY_STOP =
  'Does this reply stop before the work is over: a progress summary that announces the next action, ' +
  'an offer to continue, or a report that one milestone or part is done while more remains?'

export const CRITERIA = {
  true: 'It ends on what comes next, an offer to go on, or a partial milestone: the agent could still act.',
  false: 'It is a final report: done with checks passing, or not done because something named blocks it.',
}

// Send a Worker back only when the judge is fairly sure: a wrong send-back costs a turn, a missed one a round.
export const BLOCK_AT = 0.7

export const SEND_BACK =
  'Your reply ends before the step is finished. Finish the step in this turn: take the action you ' +
  'announced now, run the checks, then reply with done / not done, whether the checks passed, files ' +
  'touched, and the log path. If something outside files_touched genuinely blocks you, say what and stop.'

export function pickBackend(judge: string | undefined, key: string | undefined): Backend {
  const asked = judge?.trim().toLowerCase()
  // `jev` with no key: a proxy adds the Authorization header (a cloud environment's network secret).
  if (asked === 'off' || asked === 'haiku' || asked === 'jev') return asked
  return key ? 'jev' : 'haiku'
}

export function jevBody(reply: string): string {
  return JSON.stringify({
    model: 'jev-latest',
    state: reply.slice(-20_000),
    questions: { early: { type: 'noul', instructions: EARLY_STOP, criteria: CRITERIA } },
  })
}

// `{ answers: { early: { type: 'noul', noul: 0.93 } } }`, or the field under another name.
export function readJev(text: string): number | undefined {
  try {
    const a = (JSON.parse(text) as { answers?: Record<string, unknown> }).answers?.early
    if (typeof a === 'number') return a
    if (a && typeof a === 'object') {
      for (const k of ['noul', 'probability', 'value']) {
        const v = (a as Record<string, unknown>)[k]
        if (typeof v === 'number') return v
      }
    }
  } catch { /* unreadable: no judgment */ }
  return undefined
}

export function haikuPrompt(reply: string): string {
  return `${EARLY_STOP}\n\nYes means: ${CRITERIA.true}\nNo means: ${CRITERIA.false}\n\n` +
    'Answer with only the probability that the answer is yes, a number between 0 and 1.\n\n' +
    `<reply>\n${reply.slice(-20_000)}\n</reply>`
}

export function readHaiku(text: string): number | undefined {
  const m = text.match(/\b(0(?:\.\d+)?|1(?:\.0+)?)\b/)
  return m ? Number(m[1]) : undefined
}
