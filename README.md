# Hacivat & Karagöz

An autonomous **plan-and-build pair** for Claude Code.

In Turkish shadow play, Hacivat and Karagöz are two halves of the same act: **Hacivat is the educated one — he schemes and puts things into words. Karagöz is the one who actually does the work on the ground.** These two skills split the same way.

- **`hacivat`** turns a large job into a plan that has survived criticism — clarifies the brief, runs a **four-lens critic panel** over the draft, hill-climbs until the objections are gone, assigns a model to every step, and writes the handoff files.
- **`karagoz`** executes that plan inside a `/loop` — one step per tick, each handed to a **Worker** sub-agent and audited by an adversarial **Observer**, with the status tracked in a ledger.

The point is a job that runs for hours without a human in the loop, and without the context blowing up.

## Install

```
/plugin marketplace add azizi2407/karakam
/plugin install karakam@kara-skills
```

Skills are namespaced by the plugin: `/karakam:hacivat` and `/karakam:karagoz`.

<details>
<summary>Or install manually (no marketplace)</summary>

```bash
git clone https://github.com/azizi2407/karakam.git
mkdir -p ~/.claude/skills
cp -R karakam/plugins/karakam/skills/hacivat ~/.claude/skills/
cp -R karakam/plugins/karakam/skills/karagoz ~/.claude/skills/
```
Then they're just `/hacivat` and `/karagoz`.
</details>

## Use

```
/karakam:hacivat
```
Describe the job. Hacivat asks a couple of clarifying questions, drafts the plan, runs the critic panel, refines, and hands you a summary plus a loop prompt:

```
✅ Plan ready: 7 steps, output directory ./my-project/plan/

To hand over:
1. Type /clear
2. Paste this:
   /loop 20m karagoz: execute the plan in ./my-project/plan/
```

`/clear` matters — the execution phase must start on a fresh context. Then Karagöz takes over and works through the plan on its own, closing the loop when the job is done.

**These skills only run when you name them.** They will not fire on their own, however much your request sounds like a job for them. That's deliberate: they spin up an expensive machine, and you decide when that's worth it.

## How it works

Four roles:

| Role | Job | Model |
|---|---|---|
| **Creator (Hacivat)** | Clarify → plan → critic panel → hill-climb → handoff files. Talks to you. | Opus |
| **Coordinator (Karagöz)** | One tick = one step to `done`. Picks the step, sends the Worker, calls the Observer, updates the ledger. Writes no code. | Sonnet |
| **Worker** | Executes one step, test-first. Writes a short log. | Assigned per step by Hacivat |
| **Observer** | Audits the step adversarially — runs the tests itself, tries to refute it. | Haiku / Sonnet |

The handoff between the halves is four files:

```
plan/
├── methodology.md     # the constitution: goal, stack, methods, integrity rules, DoD
├── progress.md        # thin ledger — the ONLY file the Coordinator reads
├── steps/NN.md        # self-contained steps: worker prompt, model, acceptance criteria
├── logs/  reports/    # Worker logs and long Observer reports
```

### Context economy

The Coordinator stays **thin**, and everything else follows from that:

- **Pass paths, not contents.** It says "read `steps/03.md`" — it never reads 03.md itself. The Worker opens it in its own isolated context.
- **Stateless.** Every tick reads the truth fresh from `progress.md`. Nothing accumulates across ticks.
- **Short reports.** Workers and Observers return 2–3 lines; long reports go to a file, and only the path comes back.

That's what lets the loop spin for hours instead of collapsing after a few ticks.

### Defense in depth — no human required

Quality is guarded by three autonomous layers, none of which stops to ask you anything:

1. **Test-first Workers** — a step's "done" is tied to a check that runs, not to the Worker's own claim.
2. **Adversarial Observers** — the Observer doesn't trust the Worker's report. It runs the tests itself, and it's suspicious of the Worker's *test code* too (a test can fool itself by staging the very state it should prove).
3. **Double Observer on critical steps** — two lenses, one on behavior and one on integrity. **Either one can veto.**

That third layer earns its keep. In the first real run of this pair, on a critical step:

- The Worker reported *"35/35 tests passed"* — but one of its tests had seeded the state it was meant to prove, so the real path never ran.
- **Observer-B (integrity)** approved the step: the code matched the spec exactly. It was right.
- **Observer-A (behavior)** ran the flow itself and rejected it: a rate limiter that only armed *after* a successful send, meaning it offered no protection precisely when the mail server was down — unbounded requests, each pinned to a 10-second timeout.
- The spec itself was wrong. The Worker had followed it faithfully.

A single Observer — **either one of them** — would have let that through.

### Smart continuation

When a step can't pass after its refactor rounds, the loop doesn't stall waiting for you. The step is marked `blocked`, everything that depends on it waits, and independent work carries on. When there's nothing left to do, the loop closes itself and leaves you a summary of what's `done`, what's `blocked`, and why.

## Cost

Be honest with yourself about this: it is not cheap.

- One critic panel round ≈ **340k tokens** (4 lenses). The hill-climb allows up to 3 rounds.
- Execution runs roughly **110–140k tokens per step** (Worker + Observer); a critical step with two Observers and a refactor round costs several times that.

On a large autonomous job that's a bargain — a broken plan means hours of wrong output. On a small one it's overkill; use plain Claude Code instead. Hacivat will ask before spending an extra panel round if you're watching the budget.

## Requirements

- Claude Code with sub-agent (Agent tool) access, and access to the models the plan assigns (Opus / Sonnet / Haiku).
- For long autonomous runs on a server, run inside `tmux`/`screen` — `/loop` lives in the session, and it dies with your SSH connection.

## Language

The skills' instructions are in English, but **everything they produce follows you**: the plan, the step files, the worker prompts and the conversation are written in whatever language you're speaking. Structural keywords (`depends_on`, `model`, `kritik`, `pending`/`done`/`refactoring`/`blocked`) stay in place — both halves parse them.

## License

MIT
