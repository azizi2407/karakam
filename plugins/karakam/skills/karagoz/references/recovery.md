# Crash recovery

Read this when a tick starts and `progress.md` has a step marked `in_progress` or `refactoring`.

Both statuses are tick-local: `in_progress` is written right before a Worker is spawned, and a refactor cycle runs start to finish inside one tick, so finding either one at the *start* of a tick means the tick that owned it died — crashed, killed, or out of turns. A stale `refactoring` row is invisible to step selection (eligible = `pending` only), so leaving it would stall the step forever. Recover every such step before picking new work.

`stepgit.sh` is `scripts/stepgit.sh` in this skill's base directory.

## 1. Did it actually finish?

The checkpoint commit lands before the ledger says `done`, so a tick that died between the two leaves a finished step marked `in_progress`. Check first:

```
git log --oneline --grep="^karagoz step NN:"
```

A hit means the step passed and was checkpointed (and, for a worktree step, merged). Mark it `done` with the note "recovered: checkpoint found", remove a leftover worktree or branch if there is one (below), and move on.

For a worktree step, also check its branch: `git log --oneline --grep="^karagoz step NN:" karagoz-step-NN`. A hit there but not in HEAD means the step passed and was committed, but the tick died before the merge — finish it with `stepgit.sh land` (as in `references/parallel.md`) instead of discarding it.

## 2. Discard the interrupted attempt

A worktree step is one whose `<plan-dir>/.worktrees/NN` still exists, or whose branch `karagoz-step-NN` shows up in `git worktree list` / `git branch`.

- **Worktree step:** the shared tree was never touched.
  ```
  git worktree remove --force <plan-dir>/.worktrees/NN
  git branch -D karagoz-step-NN
  ```
- **Step in the project root, git repo:** revert exactly its `files_touched` — edits undone, deletions restored, files it created removed:
  ```
  stepgit.sh revert <files_touched>
  ```
  This can't reach earlier work, because every `done` step is committed before it's marked done.
- **Not a git repo**, or reverting would destroy work worth keeping: leave the files and name them in the note.

## 3. Put it back in the queue — with a limit

Set the step to `pending`. Keep whatever the note already says about refactor rounds (`refactor 2/3 @opus-xhigh`), so the next attempt resumes with that Worker and round instead of starting over, and add or increment a crash count: `recovered 1x`, `recovered 2x`, …

A step whose tick dies a third time is not going to finish this way — usually it's too big for one tick, or it wedges a tool. Mark it `blocked` with "keeps crashing its tick (recovered 3x)" instead, and let independent work carry on.
