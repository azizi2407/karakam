# Crash recovery

Read this when a tick starts and `progress.md` has a step marked `in_progress` or `refactoring`.

Both statuses are tick-local. `in_progress` is written right before a Worker is spawned and replaced with the real outcome before that tick ends; a refactor cycle (Worker → Observer, up to three rounds) also runs start to finish inside one tick. Finding either one at the *start* of a tick means the tick that owned it never finished — it crashed, was killed, or ran out of turns. Treat them alike: a stale `refactoring` row is invisible to step selection (eligible = `pending` only), so leaving it would stall that step forever.

Recover every such step before picking new work:

- **It ran in an isolated worktree** (parallel batch): the shared tree was never touched.
  ```
  git worktree remove --force <plan-dir>/.worktrees/NN
  git branch -D karagoz-step-NN
  ```
  Set the step back to `pending`.
- **It ran directly in the project root:** treat it like a step that failed before its refactor rounds. In a git repo, revert exactly its `files_touched`:
  ```
  git checkout -- <files_touched>
  git clean -f -- <files_touched>     # only for files the step created
  ```
  List the literal paths — never a directory or wildcard. This is safe because every `done` step is committed on PASS, so the checkout can only discard this interrupted step's own uncommitted work. If it isn't a git repo, or reverting would destroy work worth keeping, leave the files and name them in the note instead. Either way set the step back to `pending` with the note "recovered from an interrupted tick".

The refactor count in the note (`refactor 2/3 @high`) survives recovery; keep it, so a step that keeps crashing still reaches its round limit.
