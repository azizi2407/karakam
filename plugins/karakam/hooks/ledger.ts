// Pure helpers of the progress pane: parsing the ledger and recognising the
// Coordinator's sub-agent spawns and git checkpoints. No `$` here.
import type { KarakamMicro, KarakamStep } from '../types'

const ROW = /^\|\s*(\d{2,})\s*\|(.*)\|\s*$/

/** The step rows of a progress.md ledger (header and separator skipped). */
export function parseLedger(text: string): KarakamStep[] {
  const steps: KarakamStep[] = []
  for (const line of text.split('\n')) {
    const m = ROW.exec(line.trim())
    if (!m) continue
    // | step | status | depends_on | effort (or legacy model) | critical | file | note |
    const [, id = '', rest = ''] = m
    const cells = rest.split('|').map(c => c.trim())
    steps.push({
      id,
      status: cells[0] ?? '',
      effort: cells[2] ?? '',
      critical: /^(yes|true)$/i.test(cells[3] ?? ''),
      note: cells.length > 5 ? cells.slice(5).join(' | ') : '',
    })
  }
  return steps
}

/** The step number a Coordinator message names: `steps/NN.md`, `logs/NN.md`, "step NN". */
export function stepOf(...texts: string[]): string | undefined {
  for (const t of texts) {
    const m = /(?:steps|logs|reports)\/(\d{2,})[.-]/.exec(t) ?? /\b(?:step|adım)\s*#?(\d{1,3})\b/i.exec(t)
    if (m?.[1]) return m[1].padStart(2, '0')
  }
  return undefined
}

/** A karakam Worker or Observer spawn as a micro-step, or undefined for any other agent. */
export function classifySpawn(
  subagentType: string,
  prompt: string,
  description: string,
): Pick<KarakamMicro, 'step' | 'kind' | 'label'> | undefined {
  const m = /^karakam:(worker|observer)-(.+)$/.exec(subagentType)
  const step = stepOf(prompt, description)
  if (!m || !step) return undefined
  const [, role, variant = ''] = m
  if (role === 'worker') {
    const opus = variant.startsWith('opus-')
    const effort = opus ? variant.slice(5) : variant
    return { step, kind: 'worker', label: `worker ${opus ? 'opus' : 'sonnet'} ${effort}${opus ? ' (refactor)' : ''}` }
  }
  const lens = /\b(behavior|integrity)\b/i.exec(`${description} ${prompt}`)
  return { step, kind: 'observer', label: `observer ${variant}${lens?.[1] ? ` · ${lens[1].toLowerCase()}` : ''}` }
}

/** How a finished micro-step went, from the sub-agent's final answer. */
export function verdict(kind: KarakamMicro['kind'], answer: string): KarakamMicro['status'] {
  if (kind === 'observer') {
    if (/\bFAIL\b/.test(answer)) return 'fail'
    if (/\bPASS\b/.test(answer)) return 'pass'
    return 'done'
  }
  return /\bnot done\b/i.test(answer) ? 'fail' : 'pass'
}

/** A `stepgit.sh commit|land` call as a micro-step, or undefined. */
export function gitStep(command: string): Pick<KarakamMicro, 'step' | 'kind' | 'label'> | undefined {
  const m = /stepgit\.sh\s+(commit|land)\b/.exec(command)
  const step = m && stepOf(command)
  return m && step ? { step, kind: 'git', label: m[1] === 'land' ? 'land (commit + merge)' : 'commit' } : undefined
}

/** `1m 12s`, `45s`. */
export function duration(ms: number): string {
  const s = Math.max(0, Math.round(ms / 1000))
  return s >= 60 ? `${Math.floor(s / 60)}m ${s % 60}s` : `${s}s`
}
