# When a step fails

Read this when an Observer returns FAIL and it isn't a plain implementation bug, or when a step exhausts its refactor rounds.

## Is it the Worker's fault, or the plan's?

Sometimes the step definition itself orders the wrong thing: the Worker follows the spec exactly and the result is still wrong. Signs:

- The Worker matched the spec, yet the Observer shows with hard evidence that it doesn't actually work.
- On a critical step the two Observers disagree — one approves it as faithful to the spec, the other shows the real behavior is broken. That almost always means the spec is wrong.

Handing the same broken spec to another Worker, at any effort, produces the same result and burns a round. Instead:

- **Within one step you may fix the spec.** Edit the faulty instruction in `steps/NN.md` minimally, grounded in the Observer's evidence, then send the refactor Worker at the step's own effort (the problem was the spec, not the effort). Record the fix in the `progress.md` note — the plan never changes silently.
- **Beyond one step you stop.** If the fault spans several steps, a core decision in `methodology.md` is wrong, or the architecture has to change, don't rewrite the plan: mark the step `blocked` with the note "plan-level fault: <summary>" and carry on with independent work. The end-of-loop summary tells the user that Hacivat needs to run again.

You fix a proven single-step spec fault; you don't write plans.

## Blocked: account for the leftovers

A step that still fails after its last refactor round is `blocked`: note the reason and the report path. Then clean up what it left:

- **Ran in a worktree** → nothing reached the shared tree:
  ```
  git worktree remove --force <plan-dir>/.worktrees/NN
  git branch -D karagoz-step-NN
  ```
- **Ran in the project root, git repo** → revert exactly its `files_touched`:
  ```
  git checkout -- <files_touched>
  git clean -f -- <files_touched>     # only for files the step created
  ```
  Literal paths only, never a directory or wildcard — a `files_touched` that's too broad turns this into data loss. It can't reach earlier work because every `done` step was committed on PASS.
- **Not a git repo, or reverting would destroy work worth keeping** → leave it and write "half-finished changes on disk: <files>" into the note, so nothing downstream is blind to them.

Then keep going: steps that depend on it wait on their own (their dependency isn't `done`), and independent steps are picked up by the next tick.
