**English** · [Türkçe](README.tr.md)

# Hacivat & Karagöz

An autonomous **plan-and-build pair** for Claude Code.

In Turkish shadow play, Hacivat and Karagöz are two halves of the same act: **Hacivat is the educated one — he schemes and puts things into words. Karagöz is the one who actually does the work on the ground.** These two skills split the same way.

- **`hacivat`** turns a large job into a plan that has survived criticism — clarifies the brief, runs a **four-lens critic panel** over the draft, hill-climbs until the objections are gone, sets how hard each step's Worker should think, and writes the handoff files.
- **`karagoz`** executes that plan inside a `/loop` — one step per tick (or several at once when independent), each handed to a **Worker** sub-agent and audited by an adversarial **Observer**, with the status tracked in a ledger.

The point is a job that runs for hours without a human in the loop, and without the context blowing up.

## Install

```
/plugin marketplace add azizi2407/karakam
/plugin install karakam@kara-skills
```

Skills are namespaced by the plugin: `/karakam:hacivat` and `/karakam:karagoz`.

<details>
<summary>Or run it from a clone</summary>

```bash
git clone https://github.com/azizi2407/karakam.git
claude --plugin-dir karakam/plugins/karakam      # for one session
```
Or keep it installed from the clone: `/plugin marketplace add ./karakam`, then `/plugin install karakam@kara-skills`. Copying only the skill folders into `~/.claude/skills/` doesn't work: the skills spawn the plugin's `karakam:` sub-agents, which only exist when karakam is loaded as a plugin.
</details>

## Use

```
/karakam:hacivat
```
Describe the job. Hacivat asks a couple of clarifying questions, drafts the plan, runs the critic panel, refines, and hands you a summary, a cost estimate and the commands to start execution:

```
✅ Plan ready: 7 steps, ./my-project/plan/ — estimated execution: ~$5–9

To hand over:
0. Commit your own work, then the plan: git add ./my-project/plan && git commit -m "plan"
1. /clear
2. /model opus                 (skip if the session is already on Opus)
3. /effort medium
4. /autocompact 150k
5. /loop 20m karagoz:parallel-low execute the plan in ./my-project/plan/
```

Commit first (in a git project): Karagöz checkpoints every finished step with git and reverts a failed one on its own files, so it has to start from a clean tree — commit your own changes yourself rather than with a blanket `git add -A`, which would sweep in stray files too. `/clear` matters — the execution phase must start on a fresh context, and that fresh start is also the one moment where switching model, effort or compaction settings costs nothing. `/effort medium` pins the Coordinator — your session, 30–40% of the execution bill — to the effort it was measured at; the session otherwise keeps whatever effort you last set, and a leftover `xhigh` would pay for deep thinking on mechanical ledger work every turn. The sub-agents' effort lives in their own definitions. The word after `karagoz:` is the run mode Hacivat picked for the plan (see [Parallelism on independent steps](#parallelism-on-independent-steps)); change it if you want. The `/autocompact` window is sized to the plan — 150k–250k depending on the run mode and the plan's size. Claude Code's default for Opus 5.5 is 1M tokens, which would let the loop's conversation, resent on every turn, grow for hours; a smaller window caps that, while leaving room for several ticks between compactions (compaction fires ~33K below the window, and a session starts at ~35–50K before any work). On an API key, drop the interval (`/loop karagoz:parallel-low …`): the prompt cache lives five minutes there, and a 20-minute gap would re-write the whole conversation on every tick. Then Karagöz takes over and works through the plan on its own, closing the loop when the job is done.

**These skills only run when you name them.** They will not fire on their own, however much your request sounds like a job for them. That's deliberate: they spin up an expensive machine, and you decide when that's worth it.

## How it works

Four roles:

| Role | Job | Runs as |
|---|---|---|
| **Creator (Hacivat)** | Clarify → plan → critic panel → hill-climb → handoff files. Talks to you. | Your session (Opus) |
| **Critic** | Reviews the plan through one of four lenses. | `karakam:critic` — Opus, medium effort |
| **Coordinator (Karagöz)** | One tick = the currently runnable step(s) to `done`. Picks them, sends the Workers, calls the Observers, updates the ledger. Writes no code. | Your session (Opus, medium effort) |
| **Worker** | Executes one step, test-first. Writes a short log. | `karakam:worker-<effort>` — Sonnet 5.5, at the effort Hacivat set for the step (`medium` by default); refactor rounds: `worker-opus-high`, then `worker-opus-xhigh` |
| **Observer** | Audits the step adversarially — runs the checks itself, tries to refute it. | `karakam:observer-medium`; two `observer-high` on critical steps |

Every sub-agent is a plugin agent (`plugins/karakam/agents/`), so its protocol, tools, model and effort live in its definition rather than being re-typed by the Coordinator on every call. Workers write code on Sonnet 5.5, at `high` effort unless a step is mechanical; the Observers that audit them, the critics and the Coordinator run on Opus. When a step fails its audit, the retry goes to a stronger model, not just more thinking: an Opus Worker at `high`, then at `xhigh`. Fable is never used unless you ask for it.

The handoff between the halves is four files:

```
plan/
├── methodology.md     # the constitution: goal, stack, methods, integrity rules, DoD
├── progress.md        # thin ledger — the ONLY file the Coordinator reads
├── steps/NN.md        # self-contained steps: worker prompt, effort, acceptance criteria
├── logs/  reports/    # Worker logs and long Observer reports
```

### Context economy

The Coordinator stays **thin**, and everything else follows from that:

- **Pass paths, not contents.** It says "read `steps/03.md`" — it never reads 03.md itself. The Worker opens it in its own isolated context.
- **The ledger is the only state.** Every tick reads the truth fresh from `progress.md`, so compacting the loop's conversation loses nothing. The one interim write is the `in_progress` mark set right before a Worker is spawned, which exists solely so a tick that dies mid-way can be recovered by the next one.
- **Rare paths load on demand.** Crash recovery, worktree mechanics and failure handling live in reference files the Coordinator opens only when that situation arises; the per-tick skill body stays small, because every tick adds it to a conversation that every later turn resends.
- **Short reports.** Workers and Observers return 2–3 lines; long reports go to a file, and only the path comes back.

That's what lets the loop spin for hours instead of collapsing after a few ticks.

### Parallelism on independent steps

Steps whose `files_touched` lists don't overlap can run in the same tick, in parallel — each isolated in its own git worktree, so one Worker's changes never look like a scope violation to another step's Observer. On PASS the step is committed in its worktree and merged into the shared tree; on FAIL the worktree is discarded without ever having touched the shared tree. Overlapping `files_touched` still runs one step at a time, in order.

How many steps a tick may take is the run mode, the word after `karagoz:` in the loop command. Hacivat picks it from the plan's dependency graph:

| Mode | Steps per tick | Hacivat picks it when |
|---|---|---|
| `single` | 1 | the steps form a chain, or you want each step to land before the next starts |
| `parallel-low` | up to 2 | the plan has independent steps — the default |
| `parallel-high` | up to 4 | 3 or more steps can run together and none of them is critical |

A batch ends only when its slowest step does, so a critical step with its refactor rounds holds back a wide batch; and four Workers at once spend a subscription's usage window four times as fast. A loop command without a mode, from before 1.9, runs as `parallel-high`.

Parallel batches need git worktrees. If the project isn't a git repo, Hacivat says so at handoff and lets you choose: `git init` it, and get parallel steps and per-step checkpoints, or go on without git as `single`, where a failed step's partial changes stay in the files.

A solo step that runs directly in the shared root gets committed there on PASS too, before the ledger calls it `done`. That checkpoint is what makes reverting a failed or interrupted step safe — the revert only ever reaches that step's own uncommitted work, never an earlier `done` step's — and gives the next parallel batch a correct branch point. Those commits and reverts go through a small script (`skills/karagoz/scripts/stepgit.sh`) that handles the files a step creates or deletes, which plain `git add` / `git checkout` on a file list silently get wrong.

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

### Progress pane

When Karagöz starts, a small pane opens in the top-right corner — a narrow column docked to the right of the fullscreen transcript (above the prompt on the main screen). Steps don't finish in order — Karagöz runs whatever the dependency graph allows — so it shows a map with one cell per step, how many are in each state, and every sub-agent running right now — by name, the step it works on, and for how long:

```
01 ✓✓○·✓·✓↻·✗
✓4 ↻1 ○1 ·3 ✗1
▶ 03 observer-medium 41s
▶ 08 worker-opus-high · r… 2m 5s
✗ 10 blocked
details
```

`✓` done, `▶` running, `↻` refactoring, `✗` blocked, `○` ready (every dependency done, it can start now), `·` waiting. Press `d` (or `details`) for the full list: every step, what each waiting one waits on, and under each step its micro-steps as they happen — every Worker and Observer run (its agent, Observer lens, verdict, how long it took, the model it ran on and the tokens it used), refactor rounds on Opus, and the git checkpoint:

```
· 06 waiting · high · waits on 08
↻ 08 refactoring · high · critical — refactor 1/3 @opus-high
  ├ ✓ worker-high · sonnet 1m 12s · sonnet-5.5 · 45.8k tokens (3.2k out)
  ├ ✗ observer-high · behavior FAIL 30s · opus-5.5 · 61.0k tokens (2.1k out)
  └ … worker-opus-high · refactor · opus-5.5
```

It is a Claude Code mod (`plugins/karakam/hooks/progress.tsx`): it only watches — the skills run the same without it. Opened on its own, the pane needs a terminal at least 144 columns wide; `/karakam-progress` opens it at any width.

### Worker stop guard

When a Worker stops on a progress summary ("next I'll wire the CLI…") instead of a final report, the guard sends it back once to finish in the same context — instead of letting the step fail its audit or the Coordinator spend Opus turns resuming it. Haiku judges each Worker stop through your own session, for about $0.0001; `KARAKAM_JUDGE=off` turns it off. It only reads the Worker's last reply, never replaces an Observer, and any failure lets the stop through.

1.6 also tried TypeSafe's Jev as the judge and as a second opinion on Hacivat's efforts, critic lenses and failure triage. Jev and Haiku caught the same stops, and on effort they picked the same level for 53 of 56 steps — both leaning to `high` where an Opus referee mostly said `medium` — so 1.7 keeps the guard on Haiku and drops Jev (details in the bench README).

### Smart continuation

When a step can't pass after its refactor rounds, the loop doesn't stall waiting for you. The step is marked `blocked`, everything that depends on it waits, and independent work carries on. When there's nothing left to do (or the dependency graph turns out to deadlock), the loop closes itself and leaves you a summary of what's `done`, what's `blocked`, and why.

## Cost and benchmarks

Measured, not guessed. [`plugins/karakam/evals/bench`](plugins/karakam/evals/bench) runs both halves headless on fixed tasks, splits the bill by role, and grades the product with hidden acceptance tests the agents never see. Prices are Opus 5.5 API list prices; on a subscription, read them as how much of your usage a run takes.

| Benchmark | 1.1 (Sonnet/Haiku sub-agents) | 1.2 (all Opus, effort-tuned) | 1.3 (steps start at `low`) | 1.4 (Sonnet 5.5 Workers at `high`) |
|---|---|---|---|---|
| **Karagöz, clean run** — 3-step plan, 2 parallel + 1 critical | $1.83 · hidden tests 18/18 | $1.46 · 18/18 | $1.24 · 18/18 | **$1.11** · 18/18 |
| **Karagöz, hard run** — existing codebase, a planted spec fault (1 refactor round) | $2.23 · 21/21 · ~10.5 min | $1.66 · 21/21 · ~4.3 min | $1.47 · 30/30 · ~3.7 min | **$1.39** · 30/30 · ~3.7 min |
| **Karagöz, hard run + sloppy first Worker** (fault injection, 2 refactor rounds) | — | $1.97 · 30/30 | $1.85 · 30/30 | **$1.54** · 30/30 |
| **Karagöz, large run** — 6 steps of FIFO stock costing, 2 critical | — | — | $3.32–5.32 · 57/57 | **$2.89–3.28** · 57/57 |
| **Hacivat** — planning a 6-step plan, critic panel included | $3.35 | $3.08 | $2.71 | **$2.62** |

**Why 1.2 is cheaper despite running everything on Opus:** Opus 5.5 at medium effort finishes in fewer turns; the Coordinator — 30–40% of the execution bill — got thinner (plugin agents instead of prompt templates re-typed on every call, rare paths loaded on demand); and the critic panel's later rounds verify earlier objections instead of reviewing the whole plan afresh. Without that last change, Opus critics raised a new crop of major objections every round and planning cost $5.18.

**Why 1.3 is cheaper again:** every step runs one effort level lower than in 1.2 — well-specified work at `low`, even on the critical step — and the hidden tests came out the same, with no extra refactor rounds; Worker spend fell by about a third. The handoff also pins the Coordinator at `medium`, the effort all of these numbers were measured at.

**Why 1.4 is cheaper still:** Workers run on Sonnet 5.5, whose tokens cost half of Opus's — at `high` effort they spent less than Opus Workers at `low`/`medium`, and got every hidden test right in all 6 runs across the three plans without an extra refactor round. The bill is now mostly the Opus side: Observers and the Coordinator.

**How it recovers when a step fails:**
- **A fault in the plan gets fixed, not retried.** In every hard run of both versions, the step whose `files_touched` was too narrow failed its first audit; the Coordinator recognised a single-step spec fault, widened the list, and the step passed on the next round — at the same effort, since more thinking can't fix a wrong spec.
- **A weak Worker gets a stronger one.** With the first Worker replaced by a deliberately sloppy pass, the Observer rejected it every time and the next Worker passed. 1.2 sent it one level up (`low → medium`) for about $0.30 more; 1.3 goes straight to `high` (`low → high`) and the recovery cost about $0.20. In 1.4 the retry goes to Opus (`high → opus-high`).
- **Opus at low effort rarely needs that.** A step labelled `low` whose rules interact (Turkish casing, Unicode normalization, accent sensitivity — each wrong shortcut fails the hidden tests) was solved on the first pass in 6 of 6 runs.
- **Sonnet 5.5 Workers passed too, for less.** With every Worker switched to Sonnet 5.5 (Observers still on Opus), the hard run passed 30/30 in both runs at $1.28 against $1.66 for Opus Workers. On a larger plan — six steps of FIFO stock costing, each rule with a tempting shortcut that 57 hidden tests catch — Sonnet Workers passed 57/57 in 3 of 3 runs at $2.63–3.40, against $3.32–5.32 for Opus Workers (also 57/57), with no more refactor rounds; Worker spend was $0.40–0.52 against $1.12–1.69. 1.4 makes Sonnet 5.5 the default Worker; the bench's `--worker-model opus` option reruns the comparison.
- **A Worker that stops half-way is sent back, not chased.** With every Worker made to stop on a progress summary after writing the code, the Coordinator noticed each time and resumed the Worker itself — 3 resumes, about twice the Coordinator turns, $1.31–1.45. With the 1.6 stop guard the Workers were sent back before the Coordinator saw them: $1.09–1.15 judged by Haiku and $1.19–1.27 by Jev, against $1.07–1.18 for clean runs. Both judges caught every half-finished Worker and sent back none of the 12 clean ones; the judgments themselves cost hundredths of a cent. Every run passed 18/18.
- **`medium` by default, `high` where the traps are.** With every step forced to `medium`, the three-step plans passed every hidden test for 7–10% less than at `high`; on `fifo` the two critical steps whose rules each have a tempting shortcut failed their first audit at `medium` (3 Opus refactor rounds over 2 runs) and the plan cost more than at `high`. 1.8 makes `medium` the default and keeps `high` for exactly those steps.
- **Parallel steps buy time, not money.** On `fifo`, running independent steps two at a time (`parallel-low`) finished about a fifth faster than one at a time (`single`), for about $0.07 more — the Coordinator's worktree bookkeeping. 1.9 lets Hacivat pick the run mode per plan, and keeps critical steps out of wide batches, since a batch waits for its slowest step.
- **A failed checkpoint no longer loses work.** In one large run a step passed its audit, but committing it hit a signing timeout, and the Coordinator's hand-chained commit–merge–cleanup went on to delete the worktree. 1.3 lands parallel steps with `stepgit.sh land`, which retries a failed commit or merge once and removes the worktree only after the merge succeeded.

**What to expect per step:** a small, well-specified step runs about **$0.3–0.5** end to end, a larger one up to ~$1, a critical step (two Observers at high effort) about twice that, and every refactor round adds another Worker and Observer run. Hacivat turns that into a range for your plan before you start.

These are small, fixed tasks — they show relative cost and whether recovery works, not how often a real job's steps fail. On a large autonomous job the whole machine is a bargain: a broken plan means hours of wrong output. On a small one it's overkill; use plain Claude Code instead.

## Requirements

- Claude Code with sub-agent (Agent tool) access, Opus and Sonnet. Fable is used only if you ask for it.
- For the progress pane and the Worker stop guard: a Claude Code build with function hooks (mods).
- For long autonomous runs on a server, run inside `tmux`/`screen` — `/loop` lives in the session, and it dies with your SSH connection.

## Language

The skills' instructions are in English, but **everything they produce follows you**: the plan, the step files, the worker prompts and the conversation are written in whatever language you're speaking. Structural keywords (`depends_on`, `effort`, `critical`, `pending`/`in_progress`/`done`/`refactoring`/`blocked`) stay in place — both halves parse them.

## License

MIT
