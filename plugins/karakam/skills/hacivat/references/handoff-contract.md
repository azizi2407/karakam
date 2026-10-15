# The Handoff Contract

The files Hacivat writes and Karagöz reads; the only interface between the two skills.

```
<project>/plan/
├── methodology.md          # the job's constitution
├── progress.md             # the ledger: the only file Karagöz reads each tick
├── steps/01.md, 02.md, …   # one self-contained file per step
├── logs/                   # Workers write here (empty at handoff)
├── reports/                # long Observer reports (empty at handoff)
└── .worktrees/             # Karagöz's, for parallel steps
```

Write the content in the user's language. Field names and status values (`depends_on`, `effort`, `critical`, `files_touched`, `pending`, `done`…) are keywords: keep them in English.

Write for a capable reader. Every line is read as an instruction, by every Worker and Observer of the step, so put down only what they can't know or work out themselves: this project's decisions, contracts, rules and traps. Leave out general engineering advice and how to do things they already know how to do.

## methodology.md

Short and dense; Observers check work against it.

```markdown
# Methodology: <project>

## Goal
<what will work when it's done — 3–5 sentences>

## Stack & libraries
- <library> — <why>

## Methods & patterns
<architecture, patterns, code organization>

## Step ordering & dependencies
<why this order>

## Integrity principles
<the shared contracts, interfaces, names and data flow that make the parts fit>

## Definition of Done + test strategy

## Known limits (deliberately out of scope)
<an honest list; the Observer rejects one that flatters the implementation>
```

## steps/NN.md

Two-digit numbers (`01.md`). Self-contained: a Worker reads only this file.

```markdown
# Step NN: <title>

## Goal
<what this step produces — one sentence>

## Dependencies
depends_on: [<step numbers>] or []

## Effort
effort: low | medium | high
critical: true | false
rationale: <one line>

## Relevant methodology
<only the contracts, interfaces and domain rules this step needs>

## Worker prompt
<what to build and where, the interfaces to honor, and the traps the Worker
 couldn't foresee. Not the general protocol (test-first, scope, log, reply):
 that is in the Worker's definition.>

## Acceptance criteria (executable, un-gameable)
<runnable checks that decide "done">

## Observer checks
<what to verify beyond the criteria, if anything>

## Outputs
log: logs/NN.md
files_touched: <exact files this step may write — one line, comma-separated>
```

- **`depends_on`**: only a real reason — the step writes a file an earlier one writes, or consumes what it produced. An invented dependency serializes steps that could run in parallel.
- **`files_touched`** is the scope boundary: the Worker may touch nothing else and the Observer fails the step if anything else changed. Too narrow rejects honest work; too wide lets a Worker half-do a later step, which then gets marked `done` unchecked. Keep it on one line: Karagöz reads it with one `grep '^files_touched:'` to find steps that can run in parallel. Two steps writing one file have a real dependency.
- **Acceptance criteria** run (a test, a command and its output) and can't be gamed: if a Worker could pass one without exercising the real behavior — staging the state it should prove — forbid the shortcut, require an observable side effect, or use a signal that can't be faked. When the step changes something other code uses, one criterion goes through that caller.
- **Remote work through MCP** (a Drive, a database, a tracker): `files_touched` and git don't reach it, worktrees don't isolate it and nothing reverts it. Name the server and the exact resources in the Worker prompt and what the Observer should read back in Observer checks; give two steps writing the same remote resource a `depends_on`; keep remote writes idempotent ("create if missing, otherwise overwrite").

## progress.md

Hacivat writes every row `pending`; Karagöz fills it in. Keep it a thin table: long reports go to `reports/`, the note holds one line and a path.

```markdown
# Progress

| step | status | depends_on | effort | critical | file | note |
|------|--------|-----------|--------|----------|------|------|
| 01 | pending | - | medium | no | steps/01.md | |
| 02 | pending | 01 | high | yes | steps/02.md | |
```

- `effort` and `critical` repeat the step file's values (`critical: true` = `yes`), so Karagöz never opens a step file to spawn its agents.
- Status: `pending` · `in_progress` (a Worker is on it) · `done` (audited, committed) · `refactoring` (failed its audit, being redone) · `blocked` (failed after the last refactor round; dependents wait). `in_progress` or `refactoring` at the start of a tick means the tick that set it died.
- Older plans have a `model` column (`opus | sonnet | haiku`) instead of `effort`; Karagöz reads it as `high | medium | low`.
- 30+ steps: Karagöz may archive settled rows into `progress-archive.md`.

## What Karagöz relies on

1. `progress.md` in the format above, with `effort` and `critical`.
2. A self-contained `steps/NN.md` for every `pending` step, declaring `effort`, `critical`, `depends_on`, acceptance criteria and Observer checks.
3. `logs/` and `reports/` exist.
