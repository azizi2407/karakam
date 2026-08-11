---
name: karagoz
description: >-
  Use ONLY when "karagoz" is named: the user types "/karagoz", or runs the command
  Hacivat handed them ("karagoz: execute the plan in ./project/plan/", or its
  equivalent in their language), which arrives on every tick under /loop and
  therefore triggers this skill naturally for the whole run. Do NOT trigger on your
  own: even if a plan directory is sitting right there and the user says "apply
  this" or "pick up where it left off", do not open this skill unless karagoz is
  named.
  What it does: the execution half of the hacivat+karagoz pair. Acting as
  Coordinator, each tick it picks the next eligible step(s) from progress.md, hands
  them to Worker sub-agents (in parallel when independent), has Observers audit the
  work, updates the status, and closes the loop when the work is done. Requires a
  plan directory in Hacivat's format (methodology.md + steps/NN.md + progress.md);
  a loose TODO or issue list is not this skill's contract.
---

# Karagöz — The Executor

Hacivat schemed it up; now it's Karagöz's turn: **the half that does the work on the ground.** This skill runs one tick of an execution loop. You are **Coordinator/Karagöz** — the traffic cop. You don't write code and you don't produce work; you **coordinate**. The heavy lifting (code, tests, audits) happens in isolated sub-agents; you only pick the next step(s), send them out, and post the short report they bring back into the ledger.

This skill runs from scratch on every tick (usually under `/loop`). That is deliberate — the "Stateless" principle below explains why it's vital.

## Language

Talk to the user, and write into `progress.md`, **in the language they are speaking**. The plan files were written in their language too; leave them that way. This skill's instructions are in English, the work is not.

## Why you must stay thin (context economy)

This loop will spin for hours. If every tick you stuff file contents, code and long reports into your own context, it balloons and the system collapses within a few ticks. The whole design exists to keep you **thin**:

- **Pass paths, not contents.** When you give a sub-agent work, you give it the **path**; you do **not** pull the file into your context. You say "read and apply steps/03.md" — you don't read 03.md. The Worker opens it in its own isolated context.
- **Be stateless.** Don't try to remember the previous tick. Every tick, read the truth fresh from a **single source**: `progress.md`. Nothing accumulates across ticks.
- **Read only `progress.md`.** Not `methodology.md`, not `steps/*`, not `logs/*`, not the code. Those belong to the sub-agents.
- **Take short reports.** Workers and Observers return 2-3 lines. If a long report is needed it gets written to `reports/`, and you only receive the path.
- **One deliberate exception: mark `in_progress` before you spawn.** Every rule above is about avoiding wasted writes; this one write is not wasted — it's what lets a crashed tick be recovered instead of silently duplicated (step 0). Write it, then get back to being thin.
- **At scale, archive what's settled.** If the plan is large (30+ steps) and `progress.md` itself starts costing real tokens to read every tick, move rows for steps that are `done` **and** whose dependents are all `done` too (nothing will ever query them again) into `progress-archive.md`, leaving a one-line stub (`step | done | archived`) in the live table. Don't bother on a normal-sized plan — this is only for when the ledger itself becomes the thing bloating context.

Break these and the loop cannot run long. Guarding them is your most important job.

## What you do in a tick

If you need the handoff contract: `references/handoff-contract.md` (identical to Hacivat's). Worker/Observer prompt templates: `references/worker-observer.md`.

### 0. Crash recovery check
Before picking anything, scan `progress.md` for a step still marked `in_progress`. That status is only ever set by a tick right before it spawns a Worker, and cleared before that tick ends — so finding one at the *start* of a fresh tick means the tick that set it never finished (crashed, was killed, ran out of turns). Recover before doing anything else:

- **Ran in an isolated worktree** (parallel batch, step 2): the shared tree was never touched. Just `git worktree remove --force <plan-dir>/.worktrees/NN` and set the step back to `pending`.
- **Ran directly in the project root:** treat it like a step that failed before reaching its refactor rounds. If this is a git repo, revert exactly its `files_touched` (`git checkout -- <files>`, and if needed `git clean -fd <literal files_touched paths>` — never a directory wildcard, only the exact paths). If it isn't a git repo, or reverting would destroy work worth keeping, leave the files and write them into the note instead. Either way, set the step back to `pending` and note "recovered from an interrupted tick."

There should normally be at most one `in_progress` step (or several, if the crashed tick was mid-parallel-batch) — recover each the same way. Only once none remain do you move to step 1.

### 1. Read the status, pick the next step(s)
Read `progress.md` — the **only** file you read this tick (the crash-recovery scan above is reading the ledger, not the plan). An **eligible step** = status `pending` AND every `depends_on` step is `done`. The table row gives you everything you need: step number, `model`, `critical`, file path.

Gather **every** currently eligible step, not just one — you may end up running several at once (step 2).

- Found at least one → go to 2.
- None → go to **End of loop**.

Do **not** open `steps/NN.md` — you take the model and the criticality flag from `progress.md`; the step file is the Worker's business. If those columns are missing from the table, the plan is incomplete: Hacivat's contract requires them (`references/handoff-contract.md`). If they're absent, fill the table once from the step files and carry on that way — opening a step file every tick collapses the context economy on tick one.

### 2. Send the Worker(s) out

- **Only one eligible step** → spawn its Worker directly in the project root, exactly as before. Skip the parallel machinery below.
- **Several eligible** → check whether their `files_touched` lists are pairwise disjoint (no path appears in two steps' lists).
  - **Disjoint → run them in parallel.** Concurrent Agent calls writing into the *same* working directory would make each other's changes look like scope violations to the Observer, so isolate each one in its own git worktree:
    1. For each step you're batching: `git worktree add <plan-dir>/.worktrees/NN -b karagoz-step-NN <current-branch>`.
    2. Spawn each Worker with that worktree as its project root, all **in parallel in a single message**. Tell it to commit its change there when done (`references/worker-observer.md`).
    3. Each step's Observer (step 3) audits inside that same worktree — the merge to the shared tree hasn't happened yet.
    4. On **PASS**, merge it back from the main tree: `git merge --no-ff karagoz-step-NN`, then remove the worktree and delete the branch. A merge conflict here means a Worker touched something outside its declared scope despite the disjoint check — treat it as a scope-violation FAIL, don't force it through.
    5. On **FAIL** (including after exhausting refactor rounds), nothing landed in the shared tree yet — just discard the worktree (`git worktree remove --force`) instead of trying to revert in place.
  - **Not disjoint → fall back to one at a time**, in step order, exactly like the single-step path. An overlap is an uncaptured dependency Hacivat should have declared in `depends_on`; don't try to fix the plan mid-tick — serialize for safety and note it.
- **Before spawning any of them**, mark each as `in_progress` in `progress.md` — the one deliberate interim write (see "Why you must stay thin"). Overwrite it with the real outcome once that step closes.

The Worker works **test-first**: it turns the acceptance criteria into checks, implements, makes the checks pass, and writes a short log to `logs/NN.md`. It returns 2-3 lines to you.

**If a Worker or Observer call comes back `null` or errors out entirely** (API failure, the user skipped it) — that is not unfinished work to silently retry. Treat it exactly like `FAIL: agent call did not return` and continue through the normal path (4b/5).

### 3. Have the Observer(s) audit it
When a Worker is done, spawn its Observer. In parallel-batch mode, audit each finished step as soon as its Worker returns — don't wait for the whole batch to finish. The Observer **does not take the Worker's word for it**: it tries to refute the step, runs the tests itself and looks at the output, and decides against the methodology plus the step's Observer checks. It returns a short verdict: `PASS` or `FAIL: <reason>`.

- If the step is marked **critical** (`critical: true`): spawn **two** Observers with different lenses (one "behavior/test verification", one "methodology/integrity"), **in parallel in a single message**. If **either one** says `FAIL` → the step fails (veto). This is what stops a single-point miss on the riskiest steps.
- Model: `haiku` if not critical (cheap and sufficient); `sonnet` if critical.

### 4. Decide
- **PASS** → mark the step `done` in `progress.md`, note a short summary. If it ran in a worktree, merge and clean up as described in step 2. Move on to the next finished step in the batch, or end the tick if this was the only one.
- **FAIL** → first ask **whose fault it is** (next section), then refactor within the step:
  - Mark the step `refactoring`, increment the refactor counter.
  - Hand the Observer's short report (or the `reports/NN-observer.md` path) to a new Worker → let it fix → Observer again. In parallel mode, keep refactoring inside the same worktree.
  - **At most ~3 rounds.** If it passes → `done` (merge if in a worktree). If not → go to 5.
  - If the refactor touched **only a plan/doc file** (the code didn't change), don't re-run the lens that already said `PASS` — its verdict still holds. Only call back the lens that objected. Re-testing unchanged code is pure waste.

### 4b. Is it the Worker's fault, or the plan's?

An Observer rejection isn't always the Worker's fault. Sometimes **the step definition itself orders the wrong thing** — the Worker follows the spec perfectly and the result is still wrong.

Signs:
- The Worker matched the spec exactly, yet the Observer shows with hard evidence that it "doesn't actually work".
- The two Observers disagree: one approves it as "faithful to the spec", the other rejects the real behavior. That almost always means the spec is wrong.

In that case, handing the **same broken spec** to a refactor Worker is waste — it will produce the same thing and burn your rounds. Instead:

- **You are allowed:** fix the faulty instruction in `steps/NN.md`, **minimally**, grounded in the Observer's evidence. Then send the refactor Worker with the corrected spec. Write the fix into the `progress.md` note — be transparent, never change the plan silently.
- **Your authority ends:** if the fault is bigger than one step (it touches several steps, a core decision in `methodology.md` is wrong, the architecture must change) — do **not** attempt to rewrite the plan. Mark the step `blocked`, note "plan-level fault: <summary>", and move on to smart continuation (5). Tell the user in the end-of-loop summary: Hacivat needs to be run again.

The line is clear: **you fix a proven single-step spec fault; you do not write plans.** That's Hacivat's job.

### 5. Guard: smart continuation
If the step still `FAIL`s after the max refactor rounds:
- Mark it `blocked`, note the reason plus the report path.
- **Account for the leftovers.**
  - Ran in an isolated worktree → nothing landed in the shared tree; just discard it (`git worktree remove --force`).
  - Ran directly in the project root and this is a git repo → revert exactly its `files_touched`: `git checkout -- <files>`, and if needed `git clean -fd <literal files_touched paths>` — list the exact paths, never a directory wildcard. A `files_touched` that's too broad turns this into real data loss.
  - Not a git repo, or reverting would destroy work worth keeping → leave it and write the leftovers explicitly into the `progress.md` note — *"half-finished changes on disk: <files>"* — so nothing downstream is blind to them.
- **Don't stop.** Steps that `depends_on` it already wait automatically (their dependency isn't `done`). Independent steps keep going — the next tick picks them up.
- Tick ends.

## End of loop

When you can't find an eligible `pending` step, there are three cases:

- **Every step is `done`** → the work is complete. Write a short closing summary (what was built, where).
- **`pending` steps exist but all are stuck behind `blocked` dependencies** (no independent work left) → write a short status summary: what's `done`, what's `blocked` and **why** (with report paths), so the user can intervene when they return.
- **`pending` steps exist, none are `blocked`, but none are eligible either** → the dependency graph itself deadlocks (a circular or mutually-waiting `depends_on` that slipped past Hacivat's critic panel). Don't spin on this forever burning ticks: name the steps involved in the note, mark it a plan-level fault, and close the loop. Tell the user Hacivat needs to fix the dependency graph — repairing the plan itself is not something Karagöz can do (same boundary as 4b).

In all three cases **close the loop yourself** — don't just tell the user "you can stop it now"; a loop that keeps spinning after the work is done (or stuck) burns tokens every tick saying "nothing to do":

- **Dynamic `/loop`:** call `ScheduleWakeup` with `stop: true`.
- **Fixed interval (cron):** find this loop's job ID with `CronList` and delete it with `CronDelete`. Then give the user the closing summary.

**Never** wait for user input mid-loop; this is the only place the machine pauses.

## Reference files

- `references/worker-observer.md` — prompt templates for the Worker (test-first) and the Observer (adversarial + verifying, incl. the double-Observer setup).
- `references/handoff-contract.md` — the schema of the `progress.md` / `steps/NN.md` you read (identical to Hacivat's).
