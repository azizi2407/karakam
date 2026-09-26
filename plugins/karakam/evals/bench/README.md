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
```

Each run snapshots the plugin at launch (`results/<mode>/<label>/plugin/`), so you can keep editing the skills while it runs. Results are git-ignored. Costs are at API list prices; on a subscription they're a measure of work done, not a bill.

- **karagoz** copies `karagoz/plan/` — three steps: 01 and 02 independent (a parallel batch in worktrees), 03 critical and depending on both — into a fresh git repo, then sends the loop prompt into the same conversation (`--resume`) tick after tick, the way `/loop` does, until nothing is runnable. Afterwards `karagoz/hidden/test_hidden.py`, which the agents never see, grades the product end to end.
- **karagoz --scenario refactor** starts from a working codebase (`karagoz-refactor/base/`, stokcu v1 with its tests) and executes a three-step v2 plan with two flaws a real Hacivat plan could have:
  - step 02 adds a required `kategori` field and a new CSV header, but its `files_touched` leaves out `tests/test_rapor.py`, which still writes v1 CSVs. Its criteria (whole suite green *and* v1 header rejected) can't both hold without that file, so the step fails deterministically until the Coordinator recognises a single-step spec fault and widens `files_touched` (Karagöz's "whose fault" path) — or marks it blocked;
  - step 01 is labelled `effort: low` although Turkish casing (`I↔ı`, `İ↔i`) defeats `str.lower()`; a Worker that takes it as mechanical fails the Observer's probes and the refactor rounds have to climb effort.
  The report shows, per step, the Workers it took (`low→medium` …), spec edits, and the ledger notes; the hidden tests show whether the product ended up right.
- **hacivat** plans `hacivat/brief.md` (a small URL shortener) with no clarifying questions and no approval wait.

`by_role` splits the cost into the main session (Coordinator or Hacivat), workers, observers and critics, read from the transcripts Claude Code keeps under `~/.claude/projects/`. The main session's first turn pays a one-hour cache write for its whole prefix; subagents write five-minute caches.

The default scenario's plan is deliberately well specified — no version measured so far needed a refactor round on it — so it measures what a clean run costs. The `refactor` scenario measures recovery.
