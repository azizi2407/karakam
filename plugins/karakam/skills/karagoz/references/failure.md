# When a step fails

Read this when an Observer returns FAIL and it isn't a plain implementation bug, or when a step exhausts its refactor rounds. `stepgit.sh` is `scripts/stepgit.sh` in this skill's base directory.

## Is it the Worker's fault, or the plan's?

Sometimes the step definition itself orders the wrong thing: the Worker follows the spec exactly and the result is still wrong. Signs:

- The Worker matched the spec, yet the Observer shows with hard evidence that it doesn't actually work.
- The Worker reports that the criteria can't all be met within its `files_touched`.
- On a critical step the two Observers disagree — one approves it as faithful to the spec, the other shows the real behavior is broken. That almost always means the spec is wrong.

Handing the same broken spec to another Worker, at any effort, produces the same result and burns a round. Instead:

- **Within one step you may fix the spec.** Edit the faulty instruction in `steps/NN.md` minimally, grounded in the evidence, then send the refactor round to the step's own Worker, `karakam:worker-<effort>` (the problem was the spec, not the Worker). Record the fix in the `progress.md` note — the plan never changes silently.
- **If the fix widens `files_touched` inside a parallel batch**, check the new list against the other steps of the batch. If it now overlaps one that hasn't merged yet, the two would edit the same file in separate worktrees: don't refactor this tick — discard this step's worktree, set it back to `pending` with the fix noted, and add the other step to its `depends_on` (in the ledger and the step file). It runs after that one merges.
- **Beyond one step you stop.** If the fault spans several steps, a core decision in `methodology.md` is wrong, or the architecture has to change, don't rewrite the plan: mark the step `blocked` with the note "plan-level fault: <summary>" and carry on with independent work. The end-of-loop summary tells the user that Hacivat needs to run again.

You fix a proven single-step spec fault; you don't write plans.

## Blocked: account for the leftovers

A step that still fails after its last refactor round is `blocked`: note the reason and the report path. Then clean up what it left:

- **Ran in a worktree** → nothing reached the shared tree:
  ```
  git worktree remove --force <plan-dir>/.worktrees/NN
  git branch -D karagoz-step-NN
  ```
- **Ran in the project root, git repo** → put exactly its `files_touched` back as they are in HEAD:
  ```
  stepgit.sh revert <files_touched>
  ```
  It can't reach earlier work, because every `done` step was committed before it was marked done. A `files_touched` that's too broad would still turn this into data loss — it reverts whatever the list names.
- **Not a git repo, or reverting would destroy work worth keeping** → leave it and write "half-finished changes on disk: <files>" into the note, so nothing downstream is blind to them.

Then keep going: steps that depend on it wait on their own (their dependency isn't `done`), and independent steps are picked up by the next tick.
