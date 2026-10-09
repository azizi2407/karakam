#!/usr/bin/env python3
"""Typed second opinions from TypeSafe's Jev, for decisions that need no prose.

  jev.py effort  <plan-dir>                      each step's effort: keep, raise or lower
  jev.py lenses  <plan-dir>                      which optional critic lenses this plan needs
  jev.py triage  <step-file> <report> [<log>]    a FAIL: the Worker's fault, the spec's or the plan's
  jev.py rubric  <plan-dir>                      plan-quality checks as JSON (bench)

Jev answers yes/no and multiple-choice questions with probabilities; it can't
read the repo or run anything, so it is advice the caller weighs, never a
verdict. Needs TYPESAFE_API_KEY, or KARAKAM_JUDGE=jev when a proxy adds the
Authorization header itself. KARAKAM_JUDGE=off turns it off; then, or with no key, or when the API can't be reached, it prints one line saying why and
exits 3 — the caller goes on without it. TYPESAFE_BASE_URL overrides the API.
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

URL = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-latest"
# The API takes 64K tokens a request, 32K for the state plus the longest
# question; at ~4 characters a token this keeps the state well inside that.
STATE_CHARS = 90_000
UNAVAILABLE = 3

EFFORT = {
    "low": "Mechanical work: a rename across files, a config or version change, a known pattern applied verbatim.",
    "medium": "A small change whose shape is obvious and fully specified: a new field threaded through a known path, a thin wrapper over an existing function.",
    "high": "A module, an endpoint, a schema, cross-layer work, anything with rules that interact or a design decision to make.",
}
# Raise a step Jev thinks is likely high; lower one only when Jev is near sure.
RAISE_AT = 0.5
LOWER_AT = 0.85

# Architectural coherence and risk/omission always run; these two can be
# irrelevant to a plan, so Jev may skip them in round 1.
LENSES = {
    "stack/library-correctness": (
        "Does this plan choose, depend on or assume any third-party library, framework, external "
        "service, or a language/runtime version feature whose existence, compatibility or "
        "fitness could be wrong?"),
    "step-ordering & dependencies": (
        "Does this plan have enough steps, shared files or cross-step dependencies that the "
        "order, the depends_on fields or the files_touched lists could plausibly be wrong?"),
}
SKIP_BELOW = 0.15

TRIAGE = {
    "worker": "The Worker didn't do what the step file asks, or did it carelessly; following the spec as written would have passed.",
    "spec": "The Worker followed the step file, but the step file itself orders something wrong or impossible within its files_touched; fixing this one step file fixes it.",
    "plan": "The fault spans several steps, the methodology or the architecture; no single step file can fix it.",
}

RUBRIC = {
    "self_contained": "Is every step file self-contained: it carries the task, the acceptance criteria and files_touched, so a Worker needs no other plan file?",
    "runnable_criteria": "Are the acceptance criteria runnable checks (commands or tests with an observable result) rather than descriptions?",
    "no_seeding": "Do the criteria close the shortcut of staging the very state the test should prove, so a Worker cannot pass without exercising the real behavior?",
    "reaches_caller": "When a step changes something other code uses, does at least one of its checks go through that caller (the CLI, the client, the endpoint)?",
    "disjoint_files": "Do steps that may run in parallel (no depends_on path between them) touch disjoint files?",
    "honest_limits": "Does methodology.md state its known limits honestly?",
}


class Unavailable(Exception):
    pass


def api_key():
    if os.environ.get("KARAKAM_JUDGE", "").lower() == "off":
        raise Unavailable("KARAKAM_JUDGE=off")
    key = os.environ.get("TYPESAFE_API_KEY")
    if not key and os.environ.get("KARAKAM_JUDGE", "").lower() != "jev":
        raise Unavailable("no TYPESAFE_API_KEY")
    return key


def ask(state, questions):
    """POST one state and its questions; return {id: (value, {option: p})}."""
    key = api_key()
    if len(state) > STATE_CHARS:
        state = state[:STATE_CHARS] + "\n[truncated]"
    body = json.dumps({"model": MODEL, "state": state, "questions": questions}).encode()
    req = urllib.request.Request(
        os.environ.get("TYPESAFE_BASE_URL", URL), data=body, method="POST",
        headers={**({"Authorization": f"Bearer {key}"} if key else {}), "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
        raise Unavailable(f"Jev call failed: {e}") from e
    return {qid: read_answer(questions[qid], a) for qid, a in (data.get("answers") or {}).items()
            if qid in questions}


def read_answer(question, a):
    """One typed answer as (value, distribution). Tolerates the shapes the docs show."""
    if not isinstance(a, dict):
        a = {"value": a}
    if question["type"] == "noul":
        p = next((a[k] for k in ("noul", "probability", "value") if isinstance(a.get(k), (int, float))), None)
        if p is None:
            raise Unavailable(f"unreadable answer: {a}")
        return p >= 0.5, {"yes": float(p), "no": 1 - float(p)}
    dist = next((a[k] for k in ("probabilities", "distribution", "probs") if isinstance(a.get(k), dict)), None)
    pick = next((a[k] for k in ("choice", "value") if isinstance(a.get(k), str)), None)
    if dist is None and isinstance(a.get("choice"), dict):
        dist = a["choice"]
    if dist:
        dist = {k: float(v) for k, v in dist.items()}
        pick = pick or max(dist, key=dist.get)
    if pick is None:
        raise Unavailable(f"unreadable answer: {a}")
    return pick, dist or {pick: 1.0}


def ledger(plan):
    rows = {}
    for line in (plan / "progress.md").read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 5 and re.fullmatch(r"\d+", cells[0]):
            rows[cells[0].zfill(2)] = {"effort": cells[3], "critical": cells[4] == "yes"}
    return rows


def effort_advice(chosen, critical, pick, dist):
    p_high = dist.get("high", 0.0)
    if chosen != "high" and p_high >= RAISE_AT:
        return "raise to high"
    if chosen == "high" and not critical and pick != "high" and dist.get(pick, 0.0) >= LOWER_AT:
        return f"lower to {pick}"
    return "keep"


def cmd_effort(plan):
    rows = ledger(plan)
    q = {"effort": {"type": "choice", "instructions":
                    "How much thinking does a capable coding agent need to carry out this step correctly on the first try?",
                    "criteria": EFFORT}}
    for f in sorted((plan / "steps").glob("*.md")):
        nn = f.stem.zfill(2)
        row = rows.get(nn, {"effort": "high", "critical": False})
        pick, dist = ask(f.read_text(encoding="utf-8"), q)["effort"]
        probs = " ".join(f"{k}={dist.get(k, 0):.2f}" for k in EFFORT)
        print(f"{nn} chosen={row['effort']} jev={pick} ({probs}) -> "
              f"{effort_advice(row['effort'], row['critical'], pick, dist)}")


def plan_text(plan):
    parts = [f"# {p.relative_to(plan)}\n{p.read_text(encoding='utf-8')}"
             for p in [plan / "methodology.md", *sorted((plan / "steps").glob("*.md"))] if p.exists()]
    return "\n\n".join(parts)


def cmd_lenses(plan):
    q = {name: {"type": "noul", "instructions": text} for name, text in LENSES.items()}
    for name, (_, dist) in ask(plan_text(plan), q).items():
        p = dist["yes"]
        print(f"{name}: p={p:.2f} -> {'skip in round 1' if p < SKIP_BELOW else 'run'}")


def cmd_triage(step, report, log=None):
    state = f"# Step file\n{Path(step).read_text(encoding='utf-8')}\n\n# Observer report\n{read(report)}"
    if log:
        state += f"\n\n# Worker log\n{read(log)}"
    q = {"fault": {"type": "choice", "instructions":
                   "An Observer failed this step. Whose fault is the failure?", "criteria": TRIAGE}}
    pick, dist = ask(state, q)["fault"]
    print(f"{pick} ({' '.join(f'{k}={dist.get(k, 0):.2f}' for k in TRIAGE)})")


def cmd_rubric(plan):
    q = {k: {"type": "noul", "instructions": v} for k, v in RUBRIC.items()}
    print(json.dumps({k: round(d["yes"], 3) for k, (_, d) in ask(plan_text(plan), q).items()}))


def read(arg):
    p = Path(arg)
    return p.read_text(encoding="utf-8") if p.is_file() else arg


def main(argv):
    cmds = {"effort": (cmd_effort, 1), "lenses": (cmd_lenses, 1), "triage": (cmd_triage, 2), "rubric": (cmd_rubric, 1)}
    if not argv or argv[0] not in cmds or len(argv) - 1 < cmds[argv[0]][1]:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    fn, _ = cmds[argv[0]]
    args = [Path(a) if argv[0] != "triage" else a for a in argv[1:]]
    try:
        api_key()
        fn(*args)
    except (Unavailable, OSError) as e:
        print(f"jev unavailable: {e}")
        return UNAVAILABLE
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
