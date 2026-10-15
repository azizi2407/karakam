# The Critic Panel & Hill-Climb

## The four lenses

1. **architectural-coherence** — Do the pieces form one consistent system? Do the contracts between steps (config keys, field names, paths, interfaces) line up, each step producing what the next assumes?
2. **stack/library-correctness** — Are the libraries right, real and compatible? Version traps? A more standard choice? Safe runtime assumptions?
3. **step-ordering & dependencies** — Is `depends_on` right: missing, spurious, forward or circular? Two steps writing one file without an order? Steps to split or merge, each fitting one Worker? `files_touched` precise enough to run independent steps in parallel?
4. **risk/omission-detection** — What's missing: error paths, security gaps, edge cases, test holes, assumed requirements, criteria a Worker could pass without the real behavior or that never go through the callers? Judge severity against the job's actual scope.

## Spawning the critics

Four `karakam:critic` agents in one message. Each gets the plan directory, its lens name and definition, and on a later round its own critical and major objections from the round before plus one line each on what you changed. Paths, not contents.

## The hill-climb

```
lenses = all four
for round in 1..3:
    run the critics in `lenses`, in parallel
    if no critical/major objection anywhere and every lens scored >= 8: stop
    fix every critical/major objection; for a low score without one, take that lens's suggestions
    lenses = those with a critical/major objection or a score below 8,
             plus step-ordering whenever steps were split, merged or renumbered
```

- A critical or major objection always means another round, whatever the scores. Minors alone don't; fix the cheap ones in passing.
- Later rounds verify: each critic checks its own open objections and raises new ones only if critical or caused by your change. Without that every round finds a fresh crop of majors and the climb never converges.
- Fix with `Edit` on the affected files; never regenerate the plan.
- After round three, write what genuinely remains into `methodology.md` under "Known limits" and tell the user.
- Splitting or renumbering a step leaves stale references in `methodology.md`, other steps and `progress.md`: sweep them yourself (`grep -rn "step 0" plan/`, or the phrase in the user's language) before the next round.

Scores are each lens's confidence, not a measurement: critical/major objections are the hard signal. The panel never runs anything; faults that only show at execution are the Observers' job.

## Cost

Measured on Opus 5.5 at API list prices: planning a six-step plan costs about $3, the critics about $1.3–1.4 of it over seven or eight calls. On a small or routine job one round is enough.
