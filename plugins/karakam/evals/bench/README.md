# Cost benchmark

`claude plugin eval` grades behavior, but it forces an OS sandbox on child sessions (where that sandbox can't start, child Bash dies) and it doesn't split cost by sub-agent. This benchmark drives headless `claude -p` directly so both halves can be measured end to end — cost per role, and whether the product actually works.

```bash
cd plugins/karakam/evals/bench
python3 run.py karagoz --label <name> --runs 3                      # clean run: fixed 3-step plan
python3 run.py karagoz --scenario refactor --label <name> --runs 3  # hard run: forces refactor rounds
python3 run.py karagoz --scenario fifo --label <name> --max-ticks 10 # large run: 6 steps, tricky rules
python3 run.py hacivat --label <name> --runs 2                      # plan the fixed brief
python3 run.py report                                               # compare every label

# an older version, e.g. 1.1 (its plans use the model column):
python3 run.py karagoz --scenario refactor --label v1.1 --plugin-ref 23ac7be --legacy-plan

# exercise the effort ladder: worker-low becomes a deliberately sloppy first pass
python3 run.py karagoz --scenario refactor --label sloppy --inject-fault worker-low

# A/B: every step one effort level lower; Workers on another model
python3 run.py karagoz --label down --effort-shift-down
python3 run.py karagoz --scenario refactor --label sonnet --worker-model sonnet
```

The main session runs at `--effort medium` unless told otherwise, as the handoff pins it.

Each run snapshots the plugin at launch (`results/<mode>/<label>/plugin/`), so you can keep editing the skills while it runs. Results are git-ignored. Costs are at API list prices; on a subscription they're a measure of work done, not a bill.

- **karagoz** copies `karagoz/plan/` — three steps: 01 and 02 independent (a parallel batch in worktrees), 03 critical and depending on both — into a fresh git repo, then sends the loop prompt into the same conversation (`--resume`) tick after tick, the way `/loop` does, until nothing is runnable. Afterwards `karagoz/hidden/test_hidden.py`, which the agents never see, grades the product end to end.
- **karagoz --scenario refactor** starts from a working codebase (`karagoz-refactor/base/`, stokcu v1 with its tests) and executes a three-step v2 plan with two flaws a real Hacivat plan could have:
  - step 02 adds a required `kategori` field and a new CSV header, but its `files_touched` leaves out `tests/test_rapor.py`, which still writes v1 CSVs. Its criteria (whole suite green *and* v1 header rejected) can't both hold without that file, so the step fails deterministically until the Coordinator recognises a single-step spec fault and widens `files_touched` (Karagöz's "whose fault" path) — or marks it blocked;
  - step 01 is labelled `effort: low`, but its rules interact: Turkish casing (`I↔ı`, `İ↔i`) defeats `str.lower()`, decomposed (NFD) input — as macOS exports it — has to be normalized *before* the Turkish mapping or a decomposed `İ` turns into `ı`, and matching is accent-sensitive, so the common "NFKD and strip the marks" recipe is wrong too. The Observer checks name the rules but give no examples. The hidden tests fail each of those four wrong implementations.
  The report shows, per step, the Workers it took (`low→medium` …), spec edits, and the ledger notes; the hidden tests show whether the product ended up right.
- **karagoz --scenario fifo** is the large one: the same v1 codebase gets stock movements with FIFO costing — six steps (`karagoz-fifo/plan/`), two parallel batches, two critical steps, run with `--max-ticks 10`. The plan has no planted fault; its difficulty is rules that each have a tempting shortcut: ASCII-only, zero-padded dates (`\d` and `int()` accept other digits); customer returns that bring back the *last-consumed* units as separate lots, only against the latest issue; same-day order by file line; strict number formats (`Decimal()` accepts `NaN`, exponents and spaces); totals rounded once from exact sums; reports that process movements only up to their cut-off date; CLI errors that name the file. The plan states every rule and the Observer checks name them without examples; the 57 hidden tests fail each shortcut (checked by mutating a reference solution).
- **hacivat** plans `hacivat/brief.md` (a small URL shortener) with no clarifying questions and no approval wait.

`by_role` splits the cost into the main session (Coordinator or Hacivat), workers, observers and critics, read from the transcripts Claude Code keeps under `~/.claude/projects/`. The main session's first turn pays a one-hour cache write for its whole prefix; subagents write five-minute caches.

The default scenario's plan is deliberately well specified — no version measured so far needed a refactor round on it — so it measures what a clean run costs. The `refactor` scenario measures recovery.

## Results so far (Opus 5.5 Coordinator, API list prices)

| scenario | 1.1 (Sonnet/Haiku sub-agents) | 1.2 (Opus, effort-tuned) |
|---|---|---|
| `stokcu` (clean) | $1.83 · 18/18 · 0 refactor rounds (2 runs) | $1.46 · 18/18 · 0 rounds (3 runs) |
| `refactor` | $2.23 · 21/21 · ~10.5 min (2 runs) | $1.66 · 21/21 · ~4.3 min (3 runs) |
| `refactor`, step 01 hardened (casing + NFD + accents) | — | $1.66 · 30/30 · 1 round (3 runs) |
| `refactor`, hardened, `--inject-fault worker-low` | — | $1.97 · 30/30 · 2 rounds (2 runs) |
| `refactor`, hardened, 1.2.1 (stepgit.sh, checkpoint before `done`) | — | $1.69 · 30/30 · 1 round (2 runs) |

- **Spec faults are handled.** Every run of both versions caught step 02's fault on the first audit, widened `files_touched` to include `tests/test_rapor.py`, and passed after one round. 1.2 kept the step's effort for that round (`medium→medium`), as it should when the fault is the spec's; when the Worker itself reported the criteria unsatisfiable, the Coordinator fixed the spec without waiting for an audit.
- **Opus at low effort didn't fall for the Worker trap.** Neither the plain casing trap (which also didn't catch 1.1's Haiku) nor the hardened one: 6/6 runs got step 01 right on the first `low` pass.
- **The ladder works when a Worker does fail.** With `worker-low` replaced by a deliberately sloppy first pass, the Observer rejected it both times and the Coordinator sent the next round one level up (`low→medium`), which passed. The recovery round added about $0.30 per run.

### 1.3: lower efforts, `low → high` ladder, Coordinator pinned at medium (2 runs each)

| scenario | plan's efforts | one level lower (`--effort-shift-down`, 1.3's rubric) |
|---|---|---|
| `stokcu` (clean) | $1.46 · 18/18 · 0 rounds | $1.24 · 18/18 · 0 rounds |
| `refactor`, hardened | $1.66 · 30/30 · 1 round | $1.47 · 30/30 · 1 round |
| `refactor`, hardened, `--inject-fault worker-low` | $1.85 · 30/30 · 2 rounds (`low→high`) | — |
| `refactor`, hardened, `--worker-model sonnet` | $1.28 · 30/30 · 0–1 rounds | — |

- **One level lower cost 11–15% less and lost nothing.** Every step at `low` on the refactor plan — the critical step 03 and the trap step 01 included — and `low`/`low`/`medium` on the clean plan: same hidden-test results, no extra rounds, Worker spend down about a third. Hacivat's rubric now starts well-specified steps at `low`.
- **`low→high` recovers for less than `low→medium` did.** With the sloppy `worker-low`, the second Worker ran at `high` and passed both times; the recovery added about $0.20 over the plain hard run, against about $0.30 for 1.2's one-level step. The spec-fault round still ran at the step's own effort (`medium→medium`, `low→low`), as it should.
- **Sonnet 5.5 Workers matched Opus here.** 30/30 in both runs, Worker spend $0.15–0.19 against $0.44–0.50 for Opus at the same efforts. Observers stayed on Opus. Two runs on one small task; the plugin's default is still Opus.
- **Hacivat applies the new rubric.** Planning the brief cost $2.71 (2 runs) and produced 5-step plans with 3–4 steps at `low` and the critical or interpretive ones at `medium`.

### Large plan: `fifo`, Opus vs Sonnet 5.5 Workers (1.3, 3 runs each)

| Workers | cost per run | hidden tests | refactor rounds | Worker spend | wall |
|---|---|---|---|---|---|
| Opus (plugin default) | $3.32 · $3.45 · $5.32 | 57/57 in 3 of 3 | 0 · 0 · 2 | $1.12–1.69 | 8.7–13.8 min |
| Sonnet 5.5 (`--worker-model sonnet`) | $2.67 · $3.40 · $2.63 | 57/57 in 3 of 3 | 0 · 1 · 0 | $0.40–0.52 | 6.7–8.4 min |

- **Both got every rule right.** No run of either failed a hidden test; the Observers (Opus in both arms) sent back one step in two runs — the same step 06 edge case (`--ay 0000-01` crashed instead of reporting an invalid month) with each model. Sonnet Workers wrote fewer tests of their own (100–113 against 135–152 in the final suite).
- **The Opus arm's $5.32 run lost a step to a git failure, not to the model.** Step 02 passed both critical Observers, but its worktree commit hit a signing timeout; the Coordinator had chained commit, merge and `worktree remove --force` without checking each result, so the passed work was deleted and the step re-run. That's what `stepgit.sh land` now prevents. Without it the arms are $3.32–3.45 (Opus) against $2.63–2.67 (Sonnet) for clean runs.
- **What this doesn't show:** a task hard enough that the Worker model changes the outcome. Both scenarios are well-specified plans with a strong Observer; on them Sonnet 5.5 Workers cost 20–30% less per run at the same result.

### 1.4: Sonnet 5.5 Workers at `high`, refactor rounds on Opus (`--step-effort high`, 2 runs each)

| scenario | cost | hidden tests | refactor rounds |
|---|---|---|---|
| `stokcu` (clean) | $1.09 · $1.13 | 18/18 ×2 | 0 |
| `refactor`, hardened | $1.37 · $1.40 | 30/30 ×2 | 1 (spec fault, `high→high`) |
| `refactor`, hardened, `--inject-fault worker-high` | $1.41 · $1.67 | 30/30 ×2 | 1 · 2 (`high→opus-high`) |
| `fifo` | $2.89 · $3.28 | 57/57 ×2 | 0 |
| `hacivat` | $2.62 (1 run) | — | — |

- **Sonnet at `high` costs less than Opus at `low`/`medium`.** Worker spend was $0.18–0.26 on the three-step plans and $0.63–0.74 on `fifo`, against $0.33–0.56 and $1.12–1.69 for Opus Workers in 1.3; no extra rounds.
- **The ladder reaches Opus.** With the sloppy first pass, one run's Observer passed the sloppy step anyway (its code was right; the report called its tests thin), the other sent it to `worker-opus-high`, which passed. The spec-fault round stayed on the step's own Worker.
- **Hacivat applies the rubric.** 4 of 5 steps at `high`, one at `medium`.

### 1.6: Worker stop guard (`stokcu`, `--step-effort high`, 2 runs each)

`--early-stop worker-high` makes every Worker stop after writing the code, on a progress summary that announces the checks as its next action. `--judge` sets `KARAKAM_JUDGE` for the run; Jev itself couldn't be reached from the bench machine, so the guard judged with Haiku.

| Arm | Cost | Coordinator turns | Sent back by the guard | Hidden tests |
|---|---|---|---|---|
| early stop, no guard (`--judge off`) | $1.31–1.45 | 24–26 | 0 (Coordinator resumed each Worker with SendMessage) | 18/18 |
| early stop, guard (`--judge haiku`) | $1.09–1.15 | 12–13 | 3 of 3 | 18/18 |
| clean Workers, guard (`--judge haiku`) | $1.07–1.09 | 13–14 | 0 of 3 | 18/18 |

- **The guard pays for itself many times over.** Haiku cost $0.0003 a run; the Coordinator turns it saved cost about $0.27.
- **No false alarms in this sample.** None of the 6 clean Worker stops was sent back.
- **Without it, Opus does the chasing.** The Coordinator noticed every half-finished reply and resumed the Worker itself — correct, but on Opus, in the context that has to stay small.

### 1.6 with Jev (same arms, `--judge jev`, 2 runs each; Hacivat 1 run)

The first runs against the live API (`jev-1.13.0`). Answers came back in the documented shape (`noul`, `choice` with `probabilities`), so no parsing change was needed.

| Arm | Cost | Sent back by the guard | Hidden tests |
|---|---|---|---|
| early stop, no guard (from the Haiku table) | $1.31–1.45 | — | 18/18 |
| early stop, guard (`--judge jev`) | $1.19–1.27 | 3 of 3 | 18/18 |
| clean Workers, guard (`--judge jev`) | $1.17–1.18 | 0 of 3 | 18/18 |

- **Jev and Haiku catch the same stops.** Both sent back every half-finished Worker (6 of 6 across their runs) and none of the 12 clean ones. A Jev judgment costs about 350 input tokens at $0.042/MTok, about $0.00002; Haiku's is about $0.0001. Both round to nothing next to a $1 run.
- **The run-to-run spread is Opus, not the judge.** The clean Jev runs cost $0.09 more than the clean Haiku ones; the difference is all Observer and Coordinator spend, and no Coordinator resumed a Worker in any guarded run.
- **Hacivat used both planning checks.** `jev.py lenses` kept both optional lenses for this plan (a web service with a database: p = 0.37 and 0.46, well above the 0.15 skip line). `jev.py effort` advised raising two `medium` steps to `high` (p(high) = 0.67, 0.70), and Hacivat raised both. The plan cost $3.60 against $2.62 in 1.4. That is one run each, of a larger plan (6 steps, 3 critical, against 5) with one more critic call; Jev's own share is a few hundredths of a cent. Rubric: runnable criteria 0.96, honest limits 0.95, no seeding 0.82, disjoint files 0.67, reaches the caller 0.63, self-contained 0.58.
- **Triage on a planted spec fault** (fifo step 02 told to consume newest-first, the Worker followed it): `spec` at 0.82.

### 1.7: does Jev's effort advice hold up? (Opus referee, 56 step files)

Every step file the bench has, from the three fixed plans and Hacivat's runs: 56 steps whose ledger names an effort (older plans with a model column left out). Jev and Haiku each saw what `jev.py effort` saw — the step file alone — and gave a distribution over low / medium / high. The referee was Opus 5.5 at `high` effort, with the plan's `methodology.md` as well and asked to reason first. Each distribution went through `jev.py`'s own advice rule against Hacivat's choice: raise to `high` at p(high) ≥ 0.5, lower only at ≥ 0.85 on a non-critical `high` step.

| | top pick = Opus's | advice = Opus's | raises advised | raises Opus agreed with | mean p(high) | cost (56 steps) |
|---|---|---|---|---|---|---|
| Jev | 26 / 56 | 34 / 56 | 27 | 6 | 0.75 | ~$0.001 |
| Haiku (`low` effort) | 25 / 56 | 34 / 56 | 29 | 7 | 0.67 | $0.07 |
| Opus referee | — | — | 7 | — | 0.43 | $4.31 |

- **Jev and Haiku are the same judge here.** They picked the same level for 53 of 56 steps and differed in advice on two.
- **Neither agrees with the referee.** Both read nearly every step as `high` (Jev 45, Haiku 47); Opus picked `medium` for 33, `high` for 19 and `low` for 4. About four in five of their raises were steps Opus would have kept.
- **The run record sides with the referee where it exists.** In 1.3's `fifo` runs with Sonnet Workers at the plan's own efforts, step 05 at `medium` passed first time in 3 of 3 (Jev and Haiku: raise to `high`); step 06 at `medium` needed a refactor round in 1 of 3, on an edge case Opus Workers also missed.

So the effort check adds a near-automatic bump to `high` on top of a rubric that already says "when in doubt, `high`". 1.7 drops it, with the rest of Jev: the lens check never skipped a lens in a real plan (p 0.31–0.47 against a 0.15 line), triage duplicated a decision the Opus Coordinator already makes, and the stop guard works as well on Haiku.

### 1.8: `medium` as the default effort (`--step-effort medium`, 2 runs each)

Every step forced to `medium` — the worst case for the new rubric, which keeps `high` for steps whose rules have tempting shortcuts — against 1.4's every-step-`high` runs.

| Plan | 1.4, all `high` | 1.8, all `medium` | hidden tests | Opus refactor rounds (medium) |
|---|---|---|---|---|
| `stokcu` (3 steps) | $1.09–1.13 | $0.98–1.01 | 18/18 ×2 | 0 · 0 |
| `refactor` (3 steps, planted spec fault) | $1.37–1.40 | $1.27–1.32 | 30/30 ×2 | 0 · 0 (the spec-fault round, as in 1.4, stays on the step's own Worker) |
| `fifo` (6 steps, 2 critical) | $2.89–3.28 | $3.17–4.38 | 57/57 ×2 | 1 · 2 |
| `hacivat` (new rubric) | $2.62 (5 steps: 4 high, 1 medium) | $3.01 (6 steps: 4 high, 1 medium, 1 low) | — | — |

- **On well-specified steps `medium` is enough, and 7–10% cheaper.** Every hidden test passed; Worker spend fell by about a fifth.
- **On steps with traps it isn't.** In `fifo`, step 02 (the FIFO ledger, critical) failed its first audit at `medium` in both runs and step 06 (the CLI, critical) in one; each went to an Opus Worker and passed, but the rounds made the plan 3–42% dearer than running it at `high`. These are exactly the steps the new rubric keeps at `high`: rules that interact, each with a tempting shortcut.
- **Hacivat draws the line where it should.** With the new rubric it put the steps that hold the domain rules and the critical ones at `high`, a thin wrapper at `medium` and the scaffolding at `low`.
