# Running a batch in parallel

Read this when two or more steps are eligible and their `files_touched` lists are pairwise disjoint.

Concurrent Workers writing into the same working directory would make each other's changes look like scope violations to the Observers, so each step gets its own git worktree. (Not a git repo → no worktrees: run the steps one at a time instead.) `stepgit.sh` is `scripts/stepgit.sh` in this skill's base directory.

1. **Once per run**, before the first worktree: make sure `<plan-dir>/.worktrees/` is listed in `.git/info/exclude` (local bookkeeping — never the project's tracked `.gitignore`). Otherwise the untracked worktrees show up in `git status --porcelain` and contaminate every solo-step scope check in the shared root.
2. For each step in the batch:
   ```
   git worktree add <plan-dir>/.worktrees/NN -b karagoz-step-NN
   ```
3. Mark every step in the batch `in_progress` (one edit), then spawn all Workers **in a single message**, each with its worktree as the project root and the main tree's plan directory (absolute path) for the step file and log. Workers don't commit.
4. Audit each step in its worktree (the Observers can go out in one message).
5. **PASS** → land it, then mark it `done`. From the project root, one step at a time:
   ```
   stepgit.sh land <plan-dir>/.worktrees/NN karagoz-step-NN "karagoz step NN: <title>" <files_touched>
   ```
   It commits the step in its worktree, merges the branch, and only then removes the worktree and the branch — each stage only if the one before succeeded. Don't hand-chain those commands: a commit that failed (a signing timeout, a hook) followed by a forced worktree removal throws away a step that passed.
   - **Exit 1** — the commit or the merge failed even after a retry. The step's work is still in its worktree (or committed on its branch). Treat it like a failed checkpoint in the project root: mark it `blocked` with the error, leave the worktree, end the loop and tell the user.
   - **Exit 2** — merge conflict (already aborted). A Worker wrote outside its declared scope despite the disjoint check: treat it as a scope-violation FAIL; don't force it through.
6. **FAIL** → refactor rounds run inside the same worktree. If the step ends `blocked`, nothing ever reached the shared tree:
   ```
   git worktree remove --force <plan-dir>/.worktrees/NN
   git branch -D karagoz-step-NN
   ```
