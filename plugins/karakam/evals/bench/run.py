#!/usr/bin/env python3
"""Cost benchmark for the karakam plugin.

`claude plugin eval` forces an OS sandbox on child sessions; where that
sandbox can't start (nested containers), child Bash dies and karagoz can't run
a single test. This runner drives headless `claude -p` directly instead, which
also gives us what the eval harness doesn't: per-model cost (`modelUsage`),
so Worker / Observer / critic spend can be told apart.

karagoz mode reproduces a /loop faithfully: every tick is the same prompt sent
into the SAME conversation (`--resume <session>`), back to back, until the
ledger has no runnable work left. Afterwards the hidden acceptance tests
(never visible to the agents) grade the product.

hacivat mode runs one planning session on a fixed brief and records cost,
critic-panel size and the resulting plan.

  python3 run.py karagoz --label baseline --runs 2
  python3 run.py hacivat --label baseline --runs 2
  python3 run.py report

Results land in results/<mode>/<label>/run-N/ (git-ignored).
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN = HERE.parents[1]  # plugins/karakam
REPO = HERE.parents[3]
RESULTS = HERE / "results"
# karagoz scenarios: <dir>/plan (+ optional <dir>/base, the codebase the plan
# starts from) and <dir>/hidden/test_hidden.py
SCENARIOS = {"stokcu": HERE / "karagoz", "refactor": HERE / "karagoz-refactor"}
LEGACY_MODEL = {"low": "haiku", "medium": "sonnet", "high": "opus"}
SHIFT_DOWN = {"low": "low", "medium": "low", "high": "medium"}
# set from the command line: main-session effort, as the handoff pins it
MAIN_EFFORT = "medium"

KARAGOZ_PROMPT = (
    "karagoz: ./plan/ içindeki planı uygula. "
    "(Headless benchmark: /loop yok. Döngü kapatma adımında ScheduleWakeup/"
    "Cron çağırma, yalnızca kısa bir kapanış özeti ver.)"
)
HACIVAT_PROMPT = (HERE / "hacivat" / "brief.md").read_text(encoding="utf-8") \
    if (HERE / "hacivat" / "brief.md").exists() else ""
TOOLS = "Read Write Edit Glob Grep Bash Agent Task Skill TodoWrite"


def sh(cmd, cwd, **kw):
    return subprocess.run(cmd, cwd=cwd, shell=isinstance(cmd, str),
                          capture_output=True, text=True, **kw)


def snapshot_plugin(dest, ref=None):
    """Freeze the plugin under test: the working tree, or a git ref (e.g. v1.1)."""
    if dest.exists():
        return dest
    if ref is None:
        shutil.copytree(PLUGIN, dest, ignore=shutil.ignore_patterns("evals"))
        return dest
    tmp = dest.parent / "_archive"
    tmp.mkdir(parents=True, exist_ok=True)
    arch = subprocess.run(["git", "-C", str(REPO), "archive", "--format=tar", ref,
                           "plugins/karakam"], capture_output=True, check=True).stdout
    subprocess.run(["tar", "-x", "-C", str(tmp)], input=arch, check=True)
    shutil.copytree(tmp / "plugins" / "karakam", dest, ignore=shutil.ignore_patterns("evals"))
    shutil.rmtree(tmp)
    return dest


SLOPPY = """You are a Worker in a karakam plan, playing a deliberately sloppy first pass
for a benchmark of the recovery path. Read the step file you are given, then
implement only what its "Acceptance criteria" section literally tests — skip
the "Relevant methodology" section and any rule the criteria don't check. Write
tests only for those criteria, make them pass, write a short log to
<plan-dir>/logs/NN.md, and stay inside files_touched. If you were given a
worktree, commit there. Reply with: done, checks passed, files touched, log path.
"""


def inject_fault(plugin, agent):
    """Replace one agent's body with a sloppy first pass (frontmatter kept)."""
    f = plugin / "agents" / f"{agent}.md"
    head = f.read_text(encoding="utf-8").split("---", 2)
    f.write_text(f"---{head[1]}---\n\n{SLOPPY}", encoding="utf-8")


def use_worker_model(plugin, model):
    """Run every Worker on another model (Observers and critics stay on Opus)."""
    for f in (plugin / "agents").glob("worker-*.md"):
        f.write_text(f.read_text(encoding="utf-8").replace("\nmodel: opus\n", f"\nmodel: {model}\n", 1),
                     encoding="utf-8")


def shift_efforts_down(plan):
    """A/B: every step one effort level lower (high→medium, medium→low)."""
    prog = plan / "progress.md"
    prog.write_text(re.sub(r"^(\|[^|]*\|[^|]*\|[^|]*\|)\s*(low|medium|high)\s*\|",
                           lambda m: f"{m.group(1)} {SHIFT_DOWN[m.group(2)]} |",
                           prog.read_text(encoding="utf-8"), flags=re.M), encoding="utf-8")
    for step in (plan / "steps").glob("*.md"):
        step.write_text(re.sub(r"(## Effort\neffort: )(low|medium|high)",
                               lambda m: m.group(1) + SHIFT_DOWN[m.group(2)],
                               step.read_text(encoding="utf-8")), encoding="utf-8")


def to_legacy_plan(plan):
    """Rewrite an effort-column plan into the pre-1.2 model-column contract."""
    prog = plan / "progress.md"
    s = prog.read_text(encoding="utf-8").replace("| effort |", "| model |")
    s = re.sub(r"^(\|[^|]*\|[^|]*\|[^|]*\|)\s*(low|medium|high)\s*\|",
               lambda m: f"{m.group(1)} {LEGACY_MODEL[m.group(2)]} |", s, flags=re.M)
    prog.write_text(s, encoding="utf-8")
    for step in (plan / "steps").glob("*.md"):
        t = re.sub(r"## Effort\neffort: (low|medium|high)",
                   lambda m: f"## Model\nmodel: {LEGACY_MODEL[m.group(1)]}",
                   step.read_text(encoding="utf-8"))
        step.write_text(t, encoding="utf-8")


def claude(prompt, cwd, plugin, model, session=None, budget=15.0, timeout=3600):
    cmd = ["claude", "-p", prompt, "--plugin-dir", str(plugin),
           "--model", model, "--output-format", "json",
           "--permission-mode", "acceptEdits", "--allowed-tools", *TOOLS.split(),
           "--effort", MAIN_EFFORT, "--max-budget-usd", str(budget)]
    if session:
        cmd += ["--resume", session]
    t0 = time.time()
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    try:
        data = json.loads(p.stdout)
    except json.JSONDecodeError:
        data = {"is_error": True, "raw_stdout": p.stdout[-4000:], "stderr": p.stderr[-4000:]}
    data["_wall_s"] = round(time.time() - t0, 1)
    return data


ROW = re.compile(r"^\|\s*(\d+)\s*\|\s*([a-z_]+)\s*\|", re.M)


def ledger(proj):
    f = proj / "plan" / "progress.md"
    return dict(ROW.findall(f.read_text(encoding="utf-8"))) if f.exists() else {}


def ledger_notes(proj):
    f = proj / "plan" / "progress.md"
    if not f.exists():
        return {}
    return {m.group(1): m.group(2).strip() for m in re.finditer(
        r"^\|\s*(\d+)\s*\|(?:[^|]*\|){5}([^|]*)\|", f.read_text(encoding="utf-8"), re.M)}


def pytest_counts(proj, target):
    p = sh([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", target],
           cwd=proj, timeout=600)
    tail = (p.stdout.strip().splitlines() or [""])[-1]
    passed = int(m.group(1)) if (m := re.search(r"(\d+) passed", tail)) else 0
    failed = sum(int(x) for x in re.findall(r"(\d+) (?:failed|error)", tail))
    return {"passed": passed, "failed": failed, "tail": tail}


def run_karagoz(run_dir, plugin, model, max_ticks, scen, legacy, shift=False):
    proj = run_dir / "proj"
    if (scen / "base").exists():
        shutil.copytree(scen / "base", proj, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(scen / "plan", proj / "plan")
    if legacy:
        to_legacy_plan(proj / "plan")
    if shift:
        shift_efforts_down(proj / "plan")
    (proj / "plan" / "logs").mkdir(exist_ok=True)
    (proj / "plan" / "reports").mkdir(exist_ok=True)
    for c in ("git init -q .", "git config user.email bench@example.com",
              "git config user.name bench", "git add -A", "git commit -qm plan"):
        sh(c, cwd=proj)
    start = sh("git rev-parse HEAD", cwd=proj).stdout.strip()
    ticks, session = [], None
    for n in range(1, max_ticks + 1):
        d = claude(KARAGOZ_PROMPT, proj, plugin, model, session)
        (run_dir / f"tick-{n}.json").write_text(json.dumps(d, indent=1))
        session = d.get("session_id") or session
        state = ledger(proj)
        ticks.append({"tick": n, "cost": d.get("total_cost_usd", 0),
                      "turns": d.get("num_turns"), "wall_s": d["_wall_s"],
                      "error": d.get("is_error"), "ledger": state})
        runnable = [s for s, st in state.items() if st in ("pending", "in_progress", "refactoring")]
        if not runnable or d.get("is_error"):
            break
    hidden = proj / "_hidden"
    hidden.mkdir(exist_ok=True)
    shutil.copy(scen / "hidden" / "test_hidden.py", hidden)
    return {
        "ticks": ticks,
        "ledger": ledger(proj),
        "notes": ledger_notes(proj),
        # step files the Coordinator edited (Karagöz's single-step spec fix, 4b)
        "spec_edits": sorted(Path(f).stem for f in sh(
            ["git", "diff", "--name-only", start, "--", "plan/steps"], cwd=proj).stdout.split()),
        "own_tests": pytest_counts(proj, "tests"),
        "hidden_tests": pytest_counts(proj, "_hidden"),
        "commits": int(sh("git rev-list --count HEAD", cwd=proj).stdout.strip() or 0),
        "worktrees_left": sh("git worktree list", cwd=proj).stdout.count("\n"),
    }


def run_hacivat(run_dir, plugin, model):
    proj = run_dir / "proj"
    proj.mkdir(parents=True)
    d = claude(HACIVAT_PROMPT, proj, plugin, model, budget=30.0)
    (run_dir / "session.json").write_text(json.dumps(d, indent=1))
    plan = proj / "plan"
    return {
        "cost": d.get("total_cost_usd", 0), "turns": d.get("num_turns"),
        "wall_s": d["_wall_s"], "error": d.get("is_error"),
        "steps": len(list((plan / "steps").glob("*.md"))) if plan.exists() else 0,
        "ledger": ledger(proj),
        "result": (d.get("result") or "")[-1500:],
    }


def model_costs(run_dir):
    out = {}
    for f in sorted(run_dir.glob("*.json")):
        if f.name == "summary.json":
            continue
        for m, u in (json.loads(f.read_text()).get("modelUsage") or {}).items():
            agg = out.setdefault(m, {"cost": 0.0, "in": 0, "cache_read": 0,
                                     "cache_write": 0, "out": 0})
            agg["cost"] += u.get("costUSD", 0)
            agg["in"] += u.get("inputTokens", 0)
            agg["cache_read"] += u.get("cacheReadInputTokens", 0)
            agg["cache_write"] += u.get("cacheCreationInputTokens", 0)
            agg["out"] += u.get("outputTokens", 0)
    return out


# $/MTok: input, output, cache read, 5-minute cache write, 1-hour cache write
PRICES = {"opus-5-5": (4, 20, 0.20, 5, 8), "opus-5": (5, 25, 0.50, 6.25, 10),
          "sonnet-5": (2, 10, 0.20, 2.5, 4), "haiku-4-5": (1, 5, 0.10, 1.25, 2),
          "fable-5-1": (10, 50, 0.25, 12.5, 20)}


def price(model):
    for key in sorted(PRICES, key=len, reverse=True):
        if key in model:
            return PRICES[key]
    return None


def role_of(desc, agent_type):
    text = f"{agent_type} {desc}".lower()
    for role in ("observer", "worker", "critic"):
        if role in text:
            return role
    if "lens" in text or "eleştir" in text or "panel" in text:
        return "critic"
    return "other-subagent"


def agent_costs(proj, subagent_role=None):
    """Cost per role from the session transcripts Claude Code keeps on disk."""
    tdir = Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(proj))
    out = {}
    for f in tdir.rglob("*.jsonl"):
        meta = f.with_suffix(".meta.json")
        if "subagents" in f.parts:
            m = json.loads(meta.read_text()) if meta.exists() else {}
            role = subagent_role or role_of(m.get("description", ""), m.get("agentType", ""))
        else:
            role = "main"
        msgs = {}
        for line in f.read_text().splitlines():
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            msg = d.get("message") or {}
            if d.get("type") == "assistant" and msg.get("usage") and msg.get("id"):
                msgs[msg["id"]] = msg
        agg = out.setdefault(role, {"cost": 0.0, "calls": 0, "turns": 0, "out": 0, "cache_read": 0})
        agg["calls"] += 1 if role != "main" else 0
        for msg in msgs.values():
            u, p = msg["usage"], price(msg.get("model", ""))
            if not p:
                continue
            cw = u.get("cache_creation") or {}
            w5 = cw.get("ephemeral_5m_input_tokens", 0)
            w1 = cw.get("ephemeral_1h_input_tokens", u.get("cache_creation_input_tokens", 0) - w5)
            agg["cost"] += (u.get("input_tokens", 0) * p[0] + u.get("output_tokens", 0) * p[1]
                            + u.get("cache_read_input_tokens", 0) * p[2] + w5 * p[3] + w1 * p[4]) / 1e6
            agg["turns"] += 1
            agg["out"] += u.get("output_tokens", 0)
            agg["cache_read"] += u.get("cache_read_input_tokens", 0)
    for v in out.values():
        v["cost"] = round(v["cost"], 4)
    return out


def agent_list(proj):
    """Every sub-agent call in spawn order: type, step, model, effort, cost."""
    tdir = Path.home() / ".claude" / "projects" / re.sub(r"[^A-Za-z0-9]", "-", str(proj))
    out = []
    for meta in tdir.rglob("subagents/*.meta.json"):
        m = json.loads(meta.read_text())
        cost, turns, first, effort, model = 0.0, 0, None, None, m.get("model")
        msgs = {}
        for line in meta.with_suffix("").with_suffix(".jsonl").read_text().splitlines():
            d = json.loads(line)
            first = first or d.get("timestamp")
            g = d.get("message") or {}
            if d.get("type") == "assistant" and g.get("usage"):
                msgs[g["id"]] = g
                effort = d.get("effort") or effort
        for g in msgs.values():
            u, p = g["usage"], price(g.get("model", ""))
            model = g.get("model") or model
            if p:
                cw = u.get("cache_creation") or {}
                w5 = cw.get("ephemeral_5m_input_tokens", 0)
                w1 = cw.get("ephemeral_1h_input_tokens", u.get("cache_creation_input_tokens", 0) - w5)
                cost += (u.get("input_tokens", 0) * p[0] + u.get("output_tokens", 0) * p[1]
                         + u.get("cache_read_input_tokens", 0) * p[2] + w5 * p[3] + w1 * p[4]) / 1e6
        desc = m.get("description", "")
        # "Refactor round 1 step 02": the number after step/adım is the step
        step = (re.search(r"(?:step|ad[ıi]m)\s*#?0*(\d{1,2})(?!\d)", desc, re.I)
                or re.search(r"(?<!\d)(\d{1,2})(?!\d)(?!.*(?<!\d)\d{1,2}(?!\d))", desc))
        out.append({"t": first, "type": m.get("agentType"), "role": role_of(desc, m.get("agentType", "")),
                    "desc": desc, "step": step.group(1).zfill(2) if step else None,
                    "model": (model or "").replace("claude-", ""), "effort": effort,
                    "turns": len(msgs), "cost": round(cost, 4)})
    return sorted(out, key=lambda a: a["t"] or "")


def one(mode, label, i, model, max_ticks, scenario="stokcu", legacy=False, ref=None, shift=False):
    group = group_name(mode, scenario)
    run_dir = RESULTS / group / label / f"run-{i}"
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True)
    plugin = snapshot_plugin(RESULTS / group / label / "plugin", ref)
    t0 = time.time()
    res = run_karagoz(run_dir, plugin, model, max_ticks, SCENARIOS[scenario], legacy, shift) \
        if mode == "karagoz" else run_hacivat(run_dir, plugin, model)
    res["wall_total_s"] = round(time.time() - t0, 1)
    res["by_model"] = model_costs(run_dir)
    res["by_role"] = agent_costs(run_dir / "proj", "critic" if mode == "hacivat" else None)
    res["agents"] = agent_list(run_dir / "proj")
    res["total_cost"] = round(sum(v["cost"] for v in res["by_model"].values()), 4)
    (run_dir / "summary.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print(f"[{group}/{label}/run-{i}] ${res['total_cost']} "
          f"{res.get('hidden_tests', {}).get('tail', '')}", flush=True)
    return res


def group_name(mode, scenario):
    return mode if mode == "hacivat" or scenario == "stokcu" else f"{mode}-{scenario}"


def refactor_line(r):
    """Per step: the Workers it took (effort or model), and what the ledger says."""
    steps = {}
    for a in r.get("agents", []):
        if a["role"] == "worker" and a["step"]:
            tag = a["type"].split(":")[-1] if a["type"].startswith("karakam:") else a["model"]
            steps.setdefault(a["step"], []).append(tag.replace("worker-", ""))
    parts = [f"{s}: {'→'.join(w)}" for s, w in sorted(steps.items())]
    extra = sum(len(w) - 1 for w in steps.values())
    return (f"  workers per step: {'; '.join(parts)}  (refactor rounds: {extra})\n"
            f"  spec edits: {r.get('spec_edits') or '-'}  notes: {r.get('notes')}")


def report():
    for mode_dir in sorted(RESULTS.glob("*")):
        for label_dir in sorted(mode_dir.glob("*")):
            runs = [json.loads(s.read_text()) for s in sorted(label_dir.glob("run-*/summary.json"))]
            if not runs:
                continue
            print(f"\n## {mode_dir.name} / {label_dir.name}  ({len(runs)} runs)")
            for i, r in enumerate(runs, 1):
                models = ", ".join(f"{m.replace('claude-', '')}=${v['cost']:.2f}"
                                   for m, v in sorted(r["by_model"].items()))
                extra = ""
                if mode_dir.name.startswith("karagoz"):
                    extra = (f" ticks={len(r['ticks'])} ledger={r['ledger']} "
                             f"hidden={r['hidden_tests']['passed']}/"
                             f"{r['hidden_tests']['passed'] + r['hidden_tests']['failed']}"
                             f" commits={r['commits']}")
                else:
                    extra = f" steps={r['steps']} turns={r['turns']}"
                roles = ", ".join(f"{k}=${v['cost']:.2f}/{v['calls'] or v['turns']}"
                                  for k, v in sorted(r.get("by_role", {}).items()))
                print(f"- run {i}: ${r['total_cost']:.2f}, {r['wall_total_s']:.0f}s,{extra}\n"
                      f"  by model: {models}\n  by role ($/calls, main=$/turns): {roles}")
                if mode_dir.name.startswith("karagoz") and r.get("agents"):
                    print(refactor_line(r))
            print(f"- mean: ${sum(r['total_cost'] for r in runs) / len(runs):.2f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["karagoz", "hacivat", "report", "reanalyze"])
    ap.add_argument("--label", default="dev")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--model", default="claude-opus-5-5",
                    help="main-session model (Coordinator / Hacivat)")
    ap.add_argument("--max-ticks", type=int, default=6)
    ap.add_argument("--scenario", choices=sorted(SCENARIOS), default="stokcu",
                    help="karagoz only: which fixed plan to execute")
    ap.add_argument("--plugin-ref", help="git ref to benchmark instead of the working tree")
    ap.add_argument("--inject-fault", metavar="AGENT",
                    help="replace this agent's prompt with a sloppy first pass "
                         "(e.g. worker-low) to exercise the refactor ladder")
    ap.add_argument("--effort", default="medium", choices=["low", "medium", "high", "xhigh", "max"],
                    help="main-session effort (the handoff pins medium)")
    ap.add_argument("--effort-shift-down", action="store_true",
                    help="karagoz only: run every step one effort level lower (A/B)")
    ap.add_argument("--worker-model", metavar="MODEL",
                    help="run the Workers on this model instead of opus (e.g. sonnet)")
    ap.add_argument("--legacy-plan", action="store_true",
                    help="karagoz only: convert the plan to the pre-1.2 model-column contract")
    a = ap.parse_args()
    global MAIN_EFFORT
    MAIN_EFFORT = a.effort
    if a.mode == "report":
        return report()
    if a.mode == "reanalyze":
        for sfile in RESULTS.glob("*/*/run-*/summary.json"):
            r = json.loads(sfile.read_text())
            r["by_role"] = agent_costs(sfile.parent / "proj",
                                       "critic" if "/hacivat/" in str(sfile) else None)
            r["agents"] = agent_list(sfile.parent / "proj")
            sfile.write_text(json.dumps(r, indent=1, ensure_ascii=False))
        return report()
    plugin = RESULTS / group_name(a.mode, a.scenario) / a.label / "plugin"
    fresh = not plugin.exists()
    snapshot_plugin(plugin, a.plugin_ref)
    if a.inject_fault and fresh:
        inject_fault(plugin, a.inject_fault)
    if a.worker_model and fresh:
        use_worker_model(plugin, a.worker_model)
    with ThreadPoolExecutor(a.runs) as ex:
        list(ex.map(lambda i: one(a.mode, a.label, i, a.model, a.max_ticks,
                                  a.scenario, a.legacy_plan, a.plugin_ref, a.effort_shift_down),
                    range(1, a.runs + 1)))
    report()


if __name__ == "__main__":
    main()
