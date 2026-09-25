# Running a batch in parallel

Read this when two or more steps are eligible and their `files_touched` lists are pairwise disjoint.

Concurrent Workers writing into the same working directory would make each other's changes look like scope violations to the Observers, so each step gets its own git worktree. (Not a git repo → no worktrees: run the steps one at a time instead.)

1. **Once per run**, before the first worktree: make sure `<plan-dir>/.worktrees/` is listed in `.git/info/exclude` (local bookkeeping — never the project's tracked `.gitignore`). Otherwise the untracked worktrees show up in `git status --porcelain` and contaminate every solo-step scope check in the shared root.
2. For each step in the batch:
   ```
   git worktree add <plan-dir>/.worktrees/NN -b karagoz-step-NN <current-branch>
   ```
3. Mark every step in the batch `in_progress` (one edit), then spawn all Workers **in a single message**, each with its worktree as the project root. They commit their change inside the worktree.
4. Audit each step as soon as its Worker returns — don't wait for the whole batch. Give its Observer the worktree path and `<current-branch>` as the base branch.
5. **PASS** → from the main tree:
   ```
   git merge --no-ff karagoz-step-NN -m "karagoz step NN: <title>"
   git worktree remove <plan-dir>/.worktrees/NN
   git branch -d karagoz-step-NN
   ```
   A merge conflict means a Worker wrote outside its declared scope despite the disjoint check — `git merge --abort` and treat it as a scope-violation FAIL; don't force it through.
6. **FAIL** → refactor rounds run inside the same worktree. If the step ends `blocked`, nothing ever reached the shared tree:
   ```
   git worktree remove --force <plan-dir>/.worktrees/NN
   git branch -D karagoz-step-NN
   ```
