# The Critic Panel & Hill-Climb

We criticize the plan through four independent angles rather than one pair of eyes. The point is to break single-point blindness: what one lens misses, another catches.

## Cost — spend it deliberately

One panel round ≈ **4 × ~85k = ~340k tokens**. Three rounds ≈ 1M. That is a serious budget; don't mistake hill-climbing for free quality:

- **On small or routine jobs one round is enough.** If nothing critical/major comes back, don't start a second round.
- **Returns fall off fast between rounds.** In practice rounds 1–2 catch the real breakage (contract gaps, code that cannot work, security holes); round 3 mostly turns up renumbering leftovers and minor inconsistencies. That is exactly why the limit is 3.
- **On a big job that will run autonomously for hours, the panel is cheap** — a broken plan means hours of wrong output. Scale the ratio accordingly.
- If the user is cost-sensitive, ask before spending an extra round.

Spawn critics with **sonnet** — criticizing a plan needs reasoning but produces nothing; opus is waste here.

## The four lenses

Each lens is a separate sub-agent and looks **only through its own angle**. Spawn all four **in parallel in a single message** (Agent tool, four calls in one turn) — not sequentially, or you wait for nothing.

1. **architectural-coherence** — Does the plan build a coherent system as a whole? Are the pieces mutually consistent, or are there contradictory decisions? Are layers/responsibilities clear? Are the contracts between steps (config keys, field names, CSS classes, file paths) consistent — does a step actually produce what the next one assumes?
2. **stack/library-correctness** — Are the chosen libraries right for the job, do they actually exist, do they work together? Version/compatibility traps? A better or more standard alternative? Are language/runtime version assumptions safe for the target environment?
3. **step-ordering & dependencies** — Is the order sound? Are the `depends_on` fields right — anything missing or spurious? Does a step depend on a later one (forward/circular)? Do two steps write to the same file in a way that can clash — is their order guaranteed? Any step that should be split or merged? Are step sizes evenly atomic (does each fit one Worker context)?
4. **risk/omission-detection** — What's missing? Unhandled error paths, security gaps, edge cases, test holes, silently assumed requirements? Judge severity honestly against the actual scope — don't inflate enterprise wishlist items to "critical" on a small job.

## Critic sub-agent prompt template

Spawn each lens with this skeleton (pass paths, don't embed content — the plan files are already on disk):

```
You are a plan critic. Look through exactly one angle: <LENS NAME and definition>.

Read the plan: <plan directory path> (methodology.md + steps/*.md).

Your job is to try to REFUTE the plan from this angle — not to approve it.
Report only problems that fall within your lens.

Output (terse, structured — do not write an essay):
- objections: each {severity: critical|major|minor, step: NN or "general",
  problem: <one sentence>, suggestion: <one sentence>}
- score: 0-10 (how mature the plan is from this angle; 10 = flawless)
```

## The hill-climb mechanism (hybrid rule)

Once the panel reports back, climb:

```
round = 1
while round <= 3:
    run_panel()                            # 4 lenses in parallel
    if any lens has critical or major:
        fix_plan(close those objections)   # Edit only the affected steps/NN.md
        round += 1
        continue
    if all lenses score >= 8:
        stop("plan has settled")
    else:
        fix_plan(suggestions from the lowest-scoring lens)
        round += 1
stop("max rounds")
```

Key points:
- **Critical/major always triggers another round.** Never wave one through just because the scores look good.
- **Minor objections alone don't trigger a round.** If critical/major are clear and the scores are at threshold, stop. Polishing minors forever is waste.
- **Fixing means diffs, not rewrites.** `Edit` only the step files that drew objections. Regenerating the whole plan is the most expensive mistake available to you.
- **Max 3 rounds.** This bounds *panel runs*, not fixes. The final round's objections still get judged: fix the **cheap, mechanical ones** (wrong reference, missing line, a one-line code change) — but **do not start another panel round**. Write whatever genuinely remains into `methodology.md` under "Known limits", honestly (no burying), and flag it to the user when you present.

## The split/renumbering trap

During hill-climbing you will often need to split a step or renumber (e.g. separating network work from security logic). When you do, **also fix every prose reference to the old numbers** — the narrative in `methodology.md`, other steps' "step NN produces this" sentences, and `progress.md`. The panel catches these leftovers reliably, but that means burning a whole round on them; clean them up yourself and spend the round on real problems instead.

After renumbering, a quick sweep: `grep -rn "step 0" plan/` (or the equivalent phrasing in the user's language) to find every reference.

## Why hybrid?

With scores alone, a model can shrug and say "8.5 is good enough" while a critical hole sits open. With blockers alone, you have no way to know when to stop on a plan that has no blockers but is still weak. Hybrid: blockers are the safety net, the score is the measure of "good enough".

## What the panel cannot do

The panel reads the plan, not the running system. Some faults only surface during execution — a spec that looks perfectly reasonable but orders the wrong thing. That is precisely why Karagöz has an adversarial Observer, and why critical steps get two. Don't try to buy that certainty with more panel rounds; it isn't for sale there.
