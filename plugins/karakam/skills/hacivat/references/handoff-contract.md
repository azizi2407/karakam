# The Handoff Contract

This is the schema for the files Hacivat produces and Karagöz consumes. It is the only interface between the two skills; break the format and Karagöz cannot read the plan.

Everything goes into a single output directory (suggested: `./<project>/plan/`). Layout:

```
<project>/plan/
├── methodology.md          # the constitution
├── progress.md             # thin status ledger (the only file Karagöz reads)
├── steps/
│   ├── 01.md               # self-contained step files
│   ├── 02.md
│   └── ...
├── logs/                   # Workers write here (Hacivat leaves it empty)
├── reports/                # long Observer reports land here (Hacivat leaves it empty)
└── .worktrees/             # Karagöz creates/removes these when running steps in parallel
```

**Before writing:** if the output directory already exists and its `progress.md` shows any step not `pending`, that's a previous run's real progress — don't overwrite it silently (see Hacivat's SKILL.md, "Finish the handoff files").

**Language:** write the *content* of these files in the language the user speaks. The field names and status values below (`depends_on`, `model`, `critical`, `pending`, `done`…) are keywords — keep those as-is, in English, so both skills can parse them reliably.

---

## methodology.md

The constitution of the job. The Observer keeps checking against this to decide whether work is still faithful to the plan and method. Sections:

```markdown
# Methodology: <project name>

## Goal
<What are we building; what will be working when it's done — 3-5 sentences>

## Stack & libraries
- <library/tool> — <why chosen, what job it does>

## Methods & patterns
<Architectural approach, patterns to follow, code organization principles>

## Step ordering & dependencies
<Why this order; which step rests on which; the overall flow>

## Integrity principles
<How the steps must fit together: shared contracts, interfaces, naming,
 data flow — the rules that make the assembled parts a coherent system>

## Definition of Done + test strategy
<When is a step "finished"; the general testing approach>

## Known limits (deliberately out of scope)
<Honest list of what this plan does NOT solve, and why that trade-off was chosen.
 Do not use this section to bury a real hole — the Observer will check it against
 the code and reject a section that flatters the implementation.>
```

Keep `methodology.md` **short and dense**. Every extra paragraph costs tokens in every Worker/Observer call that reads it.

---

## steps/NN.md

One file per step, two-digit sequential number (`01.md`, `02.md`…). It must be **self-contained**: a Worker should be able to read only this file and finish the step, without being forced to open anything else.

```markdown
# Step NN: <title>

## Goal
<What this step produces — one sentence>

## Dependencies
depends_on: [<step numbers>, or empty []]

## Model
model: opus | sonnet | haiku
critical: true | false
rationale: <why this model / why critical>

Only list a dependency that has a *real* reason: either this step writes to the
same file as an earlier one, or it consumes a contract/file that step produced.
Sequence number alone is not a reason. This also matters for parallel execution:
two steps with no real dependency and disjoint `files_touched` may be run
concurrently by Karagöz — an invented dependency serializes them for nothing.

## Relevant methodology
<Copy ONLY the slice of methodology.md that concerns this step.
 This is what lets the Worker skip reading the whole methodology.>

## Worker prompt
<The full, self-contained instruction handed to the Worker. Include the
 "just code plus a short log, no commentary" discipline. State exactly what to
 do, which files to touch, which interfaces to honor.>

## Acceptance criteria (executable, un-gameable)
<Runnable checks that decide "done": which test must pass, which command must
 print what, which behavior must be observable.
 Make them un-gameable: forbid shortcuts ("do not create the file by hand"),
 require an observable side effect, and prefer signals that can't be faked
 (timing, ordering) over ones a Worker can stage.>

## Observer checks
<The concrete things the Observer must verify: fidelity to the methodology,
 not breaking integrity, correct interface, nothing missing.>

## Outputs
log: logs/NN.md          # the Worker records its work here
files_touched: <the exact files this step may write to>
```

**`files_touched` is a scope contract, not documentation.** The Worker is forbidden from touching anything outside it, and the Observer fails the step if something else changed. So list it precisely: too narrow and honest work gets rejected; too wide (or vague, like "the whole module") and you hand a Worker license to wander into a later step's territory — half-doing work that will then be marked `done` by whoever finds it "already there". If two steps genuinely must write to the same file, that's a real dependency: say so in `depends_on` so they run in sequence. A precise list also unlocks Karagöz's parallel path: steps with disjoint `files_touched` and no real `depends_on` between them can run concurrently, each in its own isolated worktree.

---

## progress.md

The **only** file Karagöz reads each tick. That's why it must stay **thin** — a status table, not a report dump. Long Observer reports go to `reports/NN-observer.md`; here you keep a one-line summary plus the path.

Hacivat builds the skeleton (everything `pending`), Karagöz fills it in.

```markdown
# Progress

| step | status | depends_on | model | critical | file | note |
|------|--------|-----------|-------|----------|------|------|
| 01 | pending | - | sonnet | no | steps/01.md | |
| 02 | pending | 01 | opus | yes | steps/02.md | |
| 03 | pending | 01 | sonnet | no | steps/03.md | |
```

Status values: `pending` · `in_progress` · `done` · `refactoring` · `blocked`

- `pending` — not started
- `in_progress` — a Worker is currently working this step (or was, when the tick that owned it died mid-way — see Karagöz's crash-recovery step)
- `done` — Worker finished, Observer approved
- `refactoring` — Observer rejected it, being fixed (within the step)
- `blocked` — failed after the max refactor rounds; its dependents wait

`in_progress` is set by a tick right before it spawns a Worker and cleared before that tick ends. Finding it still set at the *start* of a tick is a crash signal, not a normal state — it means the previous tick never got to close it out. The same is true of `refactoring`: a refactor cycle runs start-to-finish within a single tick, so finding it still set at the start of the next one is the identical crash signal, and Karagöz's crash recovery treats both alike.

**Why `model` and `critical` live here:** Karagöz must know the model when spawning a Worker and the criticality flag when setting up the Observer. If that information existed only inside `steps/NN.md`, the Coordinator would have to open the step file every tick — and the "read only progress.md" rule, i.e. the entire context economy, would collapse on the first tick. These values must match `steps/NN.md` exactly; Hacivat writes both.

**At scale, archive what's settled.** If the plan is large enough (30+ steps) that `progress.md` itself becomes costly to read every tick, Karagöz may move rows for steps that are `done` **and** whose dependents are all `done` too (so nothing will ever query them again) into `progress-archive.md`, leaving a one-line stub in the live table. Skip this on a normal-sized plan — it's ceremony the ledger doesn't need until it's genuinely bloated.

---

## What Karagöz expects (the consumer side)

Karagöz relies on this contract:
1. `progress.md` exists and uses the table format above, including `model` and `critical`.
2. Every `pending` step has a `steps/NN.md` and it is self-contained.
3. Every step declares `model`, `critical`, `depends_on`, acceptance criteria and Observer checks.
4. `logs/` and `reports/` directories exist (even if empty).

With those four in place, Karagöz executes the plan without friction.
