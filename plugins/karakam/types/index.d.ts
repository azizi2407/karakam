// The karakam progress pane's state contract (session-scoped `$.state`).

/** One row of the plan's progress.md ledger. */
export type KarakamStep = {
  id: string
  status: string
  /** Steps this one waits for (the ledger's depends_on). */
  dependsOn: string[]
  effort: string
  critical: boolean
  note: string
}

/** One micro-step of a plan step: a Worker or Observer run, or a git checkpoint. */
export type KarakamMicro = {
  /** The subagent's id, or the git call's tool_use_id. */
  id: string
  step: string
  kind: 'worker' | 'observer' | 'git'
  label: string
  status: 'running' | 'pass' | 'fail' | 'done'
  ms?: number
}

/** The ledger last read: where it is and its rows. */
export type KarakamLedger = {
  path: string
  steps: KarakamStep[]
}

declare module 'claude-code' {
  interface PluginState {
    karakam: {
      ledger: KarakamLedger | null
      micro: KarakamMicro[]
      /** The full step list instead of the compact view. */
      isExpanded: boolean
    }
  }
}
