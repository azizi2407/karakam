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
  Coordinator, each tick it picks the next eligible step from progress.md, hands it
  to a Worker sub-agent, has an Observer audit it, updates the status, and closes
  the loop when the work is done. Requires a plan directory in Hacivat's format
  (methodology.md + steps/NN.md + progress.md); a loose TODO or issue list is not
  this skill's contract.
---

# Karagöz — The Executor

Hacivat schemed it up; now it's Karagöz's turn: **the half that does the work on the ground.** This skill runs one tick of an execution loop. You are **Coordinator/Karagöz** — the traffic cop. You don't write code and you don't produce work; you **coordinate**. The heavy lifting (code, tests, audits) happens in isolated sub-agents; you only pick the next step, send them out, and post the short report they bring back into the ledger.

This skill runs from scratch on every tick (usually under `/loop`). That is deliberate — the "Stateless" principle below explains why it's vital.

## Language

Talk to the user, and write into `progress.md`, **in the language they are speaking**. The plan files were written in their language too; leave them that way. This skill's instructions are in English, the work is not.

## Why you must stay thin (context economy)

This loop will spin for hours. If every tick you stuff file contents, code and long reports into your own context, it balloons and the system collapses within a few ticks. The whole design exists to keep you **thin**:

- **Pass paths, not contents.** When you give a sub-agent work, you give it the **path**; you do **not** pull the file into your context. You say "read and apply steps/03.md" — you don't read 03.md. The Worker opens it in its own isolated context.
- **Be stateless.** Don't try to remember the previous tick. Every tick, read the truth fresh from a **single source**: `progress.md`. Nothing accumulates across ticks.
- **Read only `progress.md`.** Not `methodology.md`, not `steps/*`, not `logs/*`, not the code. Those belong to the sub-agents.
- **Take short reports.** Workers and Observers return 2-3 lines. If a long report is needed it gets written to `reports/`, and you only receive the path.

Break these and the loop cannot run long. Guarding them is your most important job.

## What you do in a tick

If you need the handoff contract: `references/handoff-contract.md` (identical to Hacivat's). Worker/Observer prompt templates: `references/worker-observer.md`.

### 1. Read the status, pick the next step
Read `progress.md` — the **only** file you read this tick. An **eligible step** = status `pending` AND every `depends_on` step is `done`. The table row gives you everything you need: step number, `model`, `kritik`, file path.

- Found one → go to 2.
- None → go to **End of loop**.

Do **not** open `steps/NN.md` — you take the model and the criticality flag from `progress.md`; the step file is the Worker's business. If those columns are missing from the table, the plan is incomplete: Hacivat's contract requires them (`references/handoff-contract.md`). If they're absent, fill the table once from the step files and carry on that way — opening a step file every tick collapses the context economy on tick one.

### 2. Send the Worker out
Spawn a Worker sub-agent using the step's `steps/NN.md` path and the model from `progress.md` (Agent tool, `model` = the step's model). The Worker works **test-first**: it turns the acceptance criteria into checks, implements, makes the checks pass, and writes a short log to `logs/NN.md`. It returns 2-3 lines to you. Template: `references/worker-observer.md`.

If you're waiting on the Worker synchronously, don't update `progress.md` yet — you'll write the result in a moment anyway, and the interim write is wasted. Only if the tick might be cut short (a very long step, a background spawn) drop a "worker running" note so the next tick can tell what happened.

### 3. Have the Observer audit it
When the Worker is done, spawn an Observer sub-agent. The Observer **does not take the Worker's word for it**: it tries to refute the step, runs the tests itself and looks at the output, and decides against the methodology plus the step's Observer checks. It returns a short verdict: `PASS` or `FAIL: <reason>`.

- If the step is marked **critical** (`kritik: true`): spawn **two** Observers with different lenses (one "behavior/test verification", one "methodology/integrity"), **in parallel in a single message**. If **either one** says `FAIL` → the step fails (veto). This is what stops a single-point miss on the riskiest steps.
- Model: `haiku` if not critical (cheap and sufficient); `sonnet` if critical.

### 4. Decide
- **PASS** → mark the step `done` in `progress.md`, note a short summary. Tick ends.
- **FAIL** → first ask **whose fault it is** (next section), then refactor within the step:
  - Mark the step `refactoring`, increment the refactor counter.
  - Hand the Observer's short report (or the `reports/NN-observer.md` path) to a new Worker → let it fix → Observer again.
  - **At most ~3 rounds.** If it passes → `done`. If not → go to 5.
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
- **Don't stop.** Steps that `depends_on` it already wait automatically (their dependency isn't `done`). Independent steps keep going — the next tick picks them up.
- Tick ends.

## End of loop

When you can't find an eligible `pending` step, there are two cases:

- **Every step is `done`** → the work is complete. Write a short closing summary (what was built, where).
- **`pending` steps exist but all are stuck behind `blocked` dependencies** (no independent work left) → write a short status summary: what's `done`, what's `blocked` and **why** (with report paths), so the user can intervene when they return.

In both cases **close the loop yourself** — don't just tell the user "you can stop it now"; a loop that keeps spinning after the work is done burns tokens every tick saying "nothing to do":

- **Dynamic `/loop`:** call `ScheduleWakeup` with `stop: true`.
- **Fixed interval (cron):** find this loop's job ID with `CronList` and delete it with `CronDelete`. Then give the user the closing summary.

**Never** wait for user input mid-loop; this is the only place the machine pauses.

## Reference files

- `references/worker-observer.md` — prompt templates for the Worker (test-first) and the Observer (adversarial + verifying, incl. the double-Observer setup).
- `references/handoff-contract.md` — the schema of the `progress.md` / `steps/NN.md` you read (identical to Hacivat's).
