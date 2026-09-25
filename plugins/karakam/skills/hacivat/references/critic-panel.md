# The Critic Panel & Hill-Climb

The plan is criticized through four independent lenses rather than one pair of eyes, so that what one lens misses another catches.

## The four lenses

Each critic looks only through its own lens.

1. **architectural-coherence** — Does the plan build a coherent system? Are the pieces mutually consistent, or do decisions contradict each other? Are layers and responsibilities clear? Do the contracts between steps (config keys, field names, file paths, interfaces) line up — does each step produce what the next one assumes?
2. **stack/library-correctness** — Are the chosen libraries right for the job, do they exist, do they work together? Version or compatibility traps? A more standard alternative? Are language/runtime version assumptions safe for the target environment?
3. **step-ordering & dependencies** — Is the order sound? Are `depends_on` fields right — missing, spurious, forward or circular? Do two steps write the same file without an ordering between them? Should a step be split or merged; does each fit one Worker's context? Are `files_touched` lists precise enough for independent steps to run in parallel?
4. **risk/omission-detection** — What's missing? Unhandled error paths, security gaps, edge cases, test holes, silently assumed requirements, acceptance criteria that a Worker could satisfy without exercising the real behavior or that never check the path through the callers. Judge severity against the job's actual scope — an enterprise wishlist item on a small job is not critical.

## Spawning the critics

Spawn four `karakam:critic` agents **in a single message**. The agent definition carries the critic's role and output format; your message gives it:

- the plan directory,
- the lens name and its definition from the list above,
- on a later round, the steps that changed since that critic's last review (and, in one line each, what changed).

Pass paths, not contents — the plan is already on disk.

## The hill-climb

```
lenses = all four
round = 1
while round <= 3:
    run the critics in `lenses`, in parallel
    open = lenses with a critical/major objection or a score below 8
    if no critical/major objection anywhere and every lens scored >= 8:
        stop("plan has settled")
    fix the plan: close every critical/major objection; for a low score
                  without one, take the lowest-scoring lens's suggestions
    lenses = open, plus step-ordering whenever steps were split, merged or renumbered
    round += 1
stop("max rounds")
```

- **Critical/major always triggers another round.** Don't wave one through because the scores look good.
- **Minor objections alone don't.** If critical/major are clear and the scores are at threshold, stop. Cheap, mechanical minors (a wrong reference, a missing line) you may fix without another round.
- **Settled lenses stay settled.** A lens with no critical/major and a score of 8+ doesn't run again — the one exception is step-ordering after a split, merge or renumbering, because those change the dependency graph it judges.
- **Fix with diffs.** `Edit` only the files that drew objections. Regenerating the whole plan is the most expensive mistake available.
- **Three rounds at most.** The final round's objections still get judged — fix the cheap ones, but don't start a fourth round. Write whatever genuinely remains into `methodology.md` under "Known limits", honestly, and flag it to the user when you present.

## The split/renumbering trap

Splitting or renumbering a step leaves stale references behind: the narrative in `methodology.md`, other steps' "step NN produces this" sentences, `progress.md`. Sweep them yourself right after the change (`grep -rn "step 0" plan/`, or the phrase in the user's language) — otherwise the panel spends a whole round on them instead of on real problems.

## Why hybrid?

With scores alone, "8.5 is good enough" can wave through an open critical hole. With blockers alone, there's no way to know when a plan with no blockers but weak spots is good enough. Blockers are the safety net; the score is the measure of "good enough".

## What the panel cannot do

The panel reads the plan; it never runs anything. Some faults only surface during execution — a spec that looks reasonable but orders the wrong thing — which is why Karagöz has adversarial Observers, and two on critical steps. More panel rounds can't buy that certainty.

For the same reason, a lens's score is its own confidence, not a measurement. Treat critical/major objections as the hard signal (they're concrete and checkable); a high score only means "this lens found nothing else to flag".

## Cost

A full panel round is four Opus critics each reading the whole plan; later rounds are cheaper because only the lenses with open objections run.

- **On a large autonomous job the panel is cheap** — a broken plan means hours of wrong output.
- **On small or routine jobs one round is enough.** If nothing critical or major comes back, stop.
- **Returns fall off fast.** Rounds one and two catch the real breakage (contract gaps, code that can't work, security holes); a third mostly finds leftovers — which is why the limit is three.
