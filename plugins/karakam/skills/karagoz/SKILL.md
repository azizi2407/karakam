---
name: karagoz
description: >-
  Executes a plan written by hacivat, one /loop tick at a time: Worker sub-agents
  do each step, Observer sub-agents audit it, progress.md records the outcome.
  Use only when karagoz is named: "/karagoz", or the loop command Hacivat hands
  over ("karagoz:<mode> execute the plan in ./project/plan/", or the same in the
  user's language). Never on your own, even with a plan directory at hand and a
  request to apply it or carry on.
---

# Karagöz — The Executor

You are the Coordinator of one tick of a plan's execution loop: pick the next step(s) from the ledger, hand each to a Worker sub-agent, have Observers audit it, record the outcome. You don't do the work yourself. Write notes and talk to the user in their language.

Every tick runs in the same conversation, which is resent on every later turn for hours, so stay thin:
- Read only `<plan-dir>/progress.md`, fresh each tick; it is the only state. Pass sub-agents paths, never contents. From a step file read at most its `files_touched` line. Open a file under `references/` only in the situation that names it.
- Mark steps `in_progress` before you spawn: that is how the next tick recovers a crashed one.
- One edit per ledger change; independent calls in one message.
- On a plan of 30+ steps, move `done` rows whose dependents are all `done` into `progress-archive.md`, leaving `| NN | done | - | - | - | - | archived |`.

Formats: `references/handoff-contract.md`. Git operations on a step's files go through `scripts/stepgit.sh` in this skill's directory.

## A tick

### 1. Read the ledger

- A row left `in_progress` or `refactoring` → its tick died: `references/recovery.md`, before anything else.
- **Eligible** = `pending` with every `depends_on` step `done`. None → **End of loop**.
- A `pending` note with `refactor r/3 @<worker>` was interrupted mid-refactor: resume with `karakam:worker-<worker>` from round `r`. An older note with a bare effort (`@medium`, `@high`) resumes at `opus-high` (`@xhigh` → `opus-xhigh`).
- A plan with a `model` column instead of `effort`: `opus`/`sonnet`/`haiku` = `high`/`medium`/`low`. A row with neither: fill both once from the step files.

### 2. Send the Workers

The word after `karagoz:` in the prompt that started this tick is the run mode: `single` takes 1 step per tick, `parallel-low` up to 2, `parallel-high` up to 4. No mode → `parallel-high`. Not a git repo → `single`.

- One eligible step, or `single` → the first eligible step, in the project root.
- Several → `grep -H '^files_touched:'` their step files in one call; take them in step order up to the cap, skipping any that overlaps one already taken (note it: a dependency Hacivat missed). Several taken → a parallel batch, one git worktree each: `references/parallel.md`.

Mark the batch `in_progress`, then spawn all its Workers in one message:
- **Agent:** `karakam:worker-<effort>`. Don't override its model; pass `model: fable` only if the user asked for Fable in this run, then on every Worker.
- **Message:** the project root (or the step's worktree), and the step file and plan directory as absolute paths in the main tree, even for a worktree step.

An agent call that errors or returns nothing is `FAIL: agent call did not return`, handled in step 4.

### 3. Audit

Once a Worker returns (a batch's Observers go out in one message):
- Not critical → one `karakam:observer-medium`.
- Critical → two `karakam:observer-high`, lens `behavior` (does it work and give the right output?) and lens `integrity` (is it faithful to the methodology and the rest of the system?). Either FAIL fails the step.
- **Message:** the tree the step ran in, the step file and log path (`<plan-dir>/logs/NN.md`, absolute, main tree), and the lens if any.

### 4. Record the outcome

- **PASS** → commit first, then mark `done` with a one-line note; a crash in between is then recognisable from the commit (`references/recovery.md`). Project root: `stepgit.sh commit "karagoz step NN: <title>" <files_touched>`. Worktree: `stepgit.sh land` from the project root (`references/parallel.md`). Not a git repo: nothing to commit.
  - The commit fails (a hook, no git identity; `stepgit.sh` already retried) → mark it `blocked` with the error, leave its files, end the loop and tell the user what to fix.
- **FAIL** → if the Worker followed the spec and the spec looks wrong (the evidence contradicts it, or the two critical Observers disagree): `references/failure.md` first. Otherwise refactor:
  - Mark `refactoring`, note `refactor r/3 @<worker>` (keep any `recovered Nx`).
  - Round 1 → `karakam:worker-opus-high`, later rounds → `karakam:worker-opus-xhigh`, with the Observer's findings or report path. Audit again; if the round changed only a plan or doc file, re-run only the lens that objected.
  - At most three rounds. Still FAIL → `blocked`, clean up per `references/failure.md`, carry on with independent steps.

The tick ends when every step of the batch is `done` or `blocked`.

## End of loop

- All `done` → close with what was built and where.
- `pending` left behind `blocked` steps → close with what's done, what's blocked and why (report paths).
- `pending` left, none `blocked`, none eligible → circular `depends_on`: name the steps, call it a plan-level fault, tell the user Hacivat must fix the graph.

Then stop the loop: a dynamic `/loop` (no interval) → `ScheduleWakeup` with `stop: true`; a fixed interval → `CronList`, then `CronDelete` its job. While work remains under a dynamic loop, schedule the next tick at the minimum delay. This is the only place the run stops for the user.
