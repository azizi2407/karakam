# Cost benchmark

`claude plugin eval` grades behavior, but it forces an OS sandbox on child sessions (where that sandbox can't start, child Bash dies) and it doesn't split cost by sub-agent. This benchmark drives headless `claude -p` directly so both halves can be measured end to end — cost per role, and whether the product actually works.

```bash
cd plugins/karakam/evals/bench
python3 run.py karagoz --label <name> --runs 3                      # clean run: fixed 3-step plan
python3 run.py karagoz --scenario refactor --label <name> --runs 3  # hard run: forces refactor rounds
python3 run.py hacivat --label <name> --runs 2                      # plan the fixed brief
python3 run.py report                                               # compare every label

# an older version, e.g. 1.1 (its plans use the model column):
python3 run.py karagoz --scenario refactor --label v1.1 --plugin-ref 23ac7be --legacy-plan

# exercise the effort ladder: worker-low becomes a deliberately sloppy first pass
python3 run.py karagoz --scenario refactor --label sloppy --inject-fault worker-low
```

Each run snapshots the plugin at launch (`results/<mode>/<label>/plugin/`), so you can keep editing the skills while it runs. Results are git-ignored. Costs are at API list prices; on a subscription they're a measure of work done, not a bill.

- **karagoz** copies `karagoz/plan/` — three steps: 01 and 02 independent (a parallel batch in worktrees), 03 critical and depending on both — into a fresh git repo, then sends the loop prompt into the same conversation (`--resume`) tick after tick, the way `/loop` does, until nothing is runnable. Afterwards `karagoz/hidden/test_hidden.py`, which the agents never see, grades the product end to end.
- **karagoz --scenario refactor** starts from a working codebase (`karagoz-refactor/base/`, stokcu v1 with its tests) and executes a three-step v2 plan with two flaws a real Hacivat plan could have:
  - step 02 adds a required `kategori` field and a new CSV header, but its `files_touched` leaves out `tests/test_rapor.py`, which still writes v1 CSVs. Its criteria (whole suite green *and* v1 header rejected) can't both hold without that file, so the step fails deterministically until the Coordinator recognises a single-step spec fault and widens `files_touched` (Karagöz's "whose fault" path) — or marks it blocked;
  - step 01 is labelled `effort: low`, but its rules interact: Turkish casing (`I↔ı`, `İ↔i`) defeats `str.lower()`, decomposed (NFD) input — as macOS exports it — has to be normalized *before* the Turkish mapping or a decomposed `İ` turns into `ı`, and matching is accent-sensitive, so the common "NFKD and strip the marks" recipe is wrong too. The Observer checks name the rules but give no examples. The hidden tests fail each of those four wrong implementations.
  The report shows, per step, the Workers it took (`low→medium` …), spec edits, and the ledger notes; the hidden tests show whether the product ended up right.
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

- **Spec faults are handled.** Every run of both versions caught step 02's fault on the first audit, widened `files_touched` to include `tests/test_rapor.py`, and passed after one round. 1.2 kept the step's effort for that round (`medium→medium`), as it should when the fault is the spec's; when the Worker itself reported the criteria unsatisfiable, the Coordinator fixed the spec without waiting for an audit.
- **Opus at low effort didn't fall for the Worker trap.** Neither the plain casing trap (which also didn't catch 1.1's Haiku) nor the hardened one: 6/6 runs got step 01 right on the first `low` pass.
- **The ladder works when a Worker does fail.** With `worker-low` replaced by a deliberately sloppy first pass, the Observer rejected it both times and the Coordinator sent the next round one level up (`low→medium`), which passed. The recovery round added about $0.30 per run.
