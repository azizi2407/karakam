// Pure helpers for the Worker stop guard: the question Haiku is asked, how its
// answer is read, and when a stop is sent back.

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

export const isOff = (judge: string | undefined): boolean => judge?.trim().toLowerCase() === 'off'

export function haikuPrompt(reply: string): string {
  return `${EARLY_STOP}\n\nYes means: ${CRITERIA.true}\nNo means: ${CRITERIA.false}\n\n` +
    'Answer with only the probability that the answer is yes, a number between 0 and 1.\n\n' +
    `<reply>\n${reply.slice(-20_000)}\n</reply>`
}

export function readHaiku(text: string): number | undefined {
  const m = text.match(/\b(0(?:\.\d+)?|1(?:\.0+)?)\b/)
  return m ? Number(m[1]) : undefined
}
