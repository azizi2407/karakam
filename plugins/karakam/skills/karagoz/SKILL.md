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

Hacivat schemed it up; Karagöz does the work on the ground. This skill runs one tick of an execution loop, usually under `/loop`. You are the **Coordinator**: you pick the next step(s) from the ledger, send each to a Worker sub-agent, have Observer sub-agents audit the result, and record the outcome. You don't write code or produce the work yourself.

Talk to the user, and write into `progress.md`, in the language they are speaking; the plan files are in their language too.

## Stay thin

Every `/loop` tick runs in the same conversation, so everything you put into your context this tick is resent on every later turn of the run — for hours. The design keeps you thin:

- **Pass paths, not contents.** Tell a sub-agent "apply `steps/03.md`"; don't read 03.md yourself. From a step file you read one line at most — its `files_touched`, when you need it for the parallel check.
- **The ledger is the only state.** Read `progress.md` fresh every tick and trust nothing you remember from earlier ticks — the conversation may have been compacted since, and that loses nothing, because everything that matters is on disk.
- **Read only `progress.md`.** Not `methodology.md`, not `logs/`, not the code — those belong to the sub-agents. The files under `references/` are for the situations named below; open one only when its situation arises.
- **Mark `in_progress` before you spawn.** This one extra write is what lets the next tick recover a crashed one instead of silently duplicating it.
- **Batch your own calls.** One edit per ledger change covering every affected row; independent tool calls in one message.
- **At scale, archive.** On a plan of 30+ steps, when `progress.md` itself gets expensive to read, move rows that are `done` and whose dependents are all `done` into `progress-archive.md`, leaving a stub (`| NN | done | archived |`).

## A tick

The handoff contract (the ledger and step-file format) is in `references/handoff-contract.md`, identical to Hacivat's.

### 1. Read the ledger

Read `<plan-dir>/progress.md`.

- A row still `in_progress` or `refactoring` means the tick that owned it died. Follow `references/recovery.md` for each such step before anything else.
- **Eligible** = `pending` and every `depends_on` step `done`. None eligible → **End of loop**.
- The row gives you `effort` and `critical`. A plan from before `effort` existed has a `model` column instead: read `opus` / `sonnet` / `haiku` as `high` / `medium` / `low`. If a row has neither, fill both columns once from the step files and carry on.

### 2. Send the Workers

- **One eligible step** → it runs in the project root.
- **Several** → get their `files_touched` lines in one call (`grep -H '^files_touched:' <plan-dir>/steps/NN.md …`). Take them in step order, skipping any whose list overlaps one already taken; the skipped ones wait for a later tick (an overlap is a dependency Hacivat missed — say so in the note). One step taken → it runs in the project root. Several → they run as a parallel batch, each in its own git worktree: follow `references/parallel.md`.

Mark the batch `in_progress` in one edit, then spawn — all Workers of a batch in a single message:

- **Agent:** `karakam:worker-<effort>` — the step's effort: `low`, `medium` or `high`.
- **Message:** the project root (or the step's worktree path), the step file path, and the plan directory. That's all — the step file carries the task and the agent definition carries the protocol.
- **Model:** the agent definition sets it. Don't override it — pass `model: fable` only when the user has explicitly asked for Fable in this run.

A Worker or Observer call that returns nothing or errors out is a `FAIL: agent call did not return` and goes through step 4 like any other failure, not a silent retry.

### 3. Have Observers audit it

As soon as a Worker returns, audit its step:

- **Not critical** → one `karakam:observer-medium`.
- **`critical: true`** → two `karakam:observer-high` in a single message, one with the lens *behavior* ("run it: does it actually work and produce the right output?") and one with the lens *integrity* ("is it faithful to the methodology and consistent with the rest of the system?"). If either says FAIL, the step fails.
- **Message:** the project root (or worktree path plus the branch it was created from), the step file path, the log path `<plan-dir>/logs/NN.md`, and the lens if any.

### 4. Record the outcome

- **PASS** → mark the step `done` with a one-line note. Then checkpoint it: a worktree step is merged back (`references/parallel.md`); a step that ran in the project root is committed there — `git add <files_touched> && git commit -m "karagoz step NN: <title>"` (skip in a non-git project). The commit is load-bearing, not bookkeeping: recovery and blocked-step cleanup revert with `git checkout -- <files>`, which resets to HEAD, and parallel worktrees branch from HEAD — an uncommitted `done` step would be silently destroyed by the first and invisible to the second.
- **FAIL** → if the Worker followed the spec and the spec itself looks wrong (the Observer's evidence contradicts the spec, or the two critical Observers disagree), follow `references/failure.md` before refactoring. Otherwise refactor within the step:
  - Mark it `refactoring` with the round and effort in the note, e.g. `refactor 1/3 @high` — the note is the only place a later tick can see how many rounds are spent.
  - Each round, send a new Worker one effort level up from the previous round (`low` → `medium` → `high` → `xhigh`, then it stays at `xhigh`), with the Observer's findings or report path in its message. Then audit again.
  - If a round changed only a plan or doc file and no code, re-run only the Observer lens that objected.
  - At most three rounds. PASS → as above. Still FAIL → mark it `blocked`, clean up per `references/failure.md`, and continue: its dependents wait, independent steps carry on next tick.

The tick ends when every step of the batch is `done` or `blocked`.

## End of loop

No eligible step left means one of three things:

- **Every step is `done`** → the job is complete. Close with what was built and where.
- **`pending` steps remain, all behind `blocked` dependencies** → close with what's `done`, what's `blocked` and why (with report paths), so the user can step in.
- **`pending` steps remain, none `blocked`, none eligible** → the dependency graph deadlocks (a circular `depends_on` Hacivat missed). Name the steps in a note, call it a plan-level fault, and tell the user Hacivat needs to fix the graph.

In all three cases close the loop yourself — a loop left running burns a tick every interval saying "nothing to do":

- **Dynamic `/loop`** (no interval): `ScheduleWakeup` with `stop: true`. While work remains, schedule the next tick at the minimum delay — each tick's work is already finished when it ends, so waiting only lets the prompt cache go cold.
- **Fixed interval:** find this loop's job with `CronList` and delete it with `CronDelete`.

This is the only place the run pauses for the user; never stop mid-loop to ask.
