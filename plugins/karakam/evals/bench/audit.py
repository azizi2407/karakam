#!/usr/bin/env python3
"""Does an Observer report what its checklist doesn't name?

A step of the stokcu plan (02, KDV and TL formatting) is left "done" by a
Worker whose code passes every listed check but carries four defects that no
acceptance criterion or Observer check names:

  oran     a negative VAT rate is accepted (the worker prompt says ValueError)
  prec     the global Decimal context is set to 12 digits: big amounts crash,
           and every other module's arithmetic changes with it
  print    kdvli prints debug output to stdout (the CLI's output, in step 03)
  skip     the rounding-boundary test is skipped as "flaky", hiding
           ROUND_HALF_EVEN where the spec says ROUND_HALF_UP

The real karakam:observer-medium audits it, the way Karagöz briefs it. We
count which defects its reply and report mention.

  python3 audit.py --label base --plugin-ref 920af3e --runs 3
  python3 audit.py --label lean --runs 3
  python3 audit.py report
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import run

HERE = Path(__file__).resolve().parent
OUT = run.RESULTS / "audit"
PLAN = HERE / "karagoz" / "plan"
PLANTED = HERE / "audit" / "planted"
DEFECTS = {
    "oran": r"(negatif|negative)[^.\n]{0,60}(oran|rate)|(oran|rate)[^.\n]{0,60}(negatif|negative)",
    "prec": r"prec|getcontext|InvalidOperation|hassasiyet",
    "print": r"print|stdout",
    "skip": r"skip|atlan|HALF_EVEN",
}


def setup(proj):
    shutil.copytree(PLAN, proj / "plan")
    (proj / "plan" / "logs").mkdir()
    (proj / "plan" / "reports").mkdir()
    (proj / "stokcu").mkdir()
    (proj / "stokcu" / "__init__.py").write_text("")
    for c in ("git init -q .", "git config user.email bench@example.com",
              "git config user.name bench", "git add -A", "git commit -qm plan+01"):
        run.sh(c, cwd=proj)
    ledger = proj / "plan" / "progress.md"
    ledger.write_text(ledger.read_text().replace("| 01 | pending |", "| 01 | done |")
                      .replace("| 02 | pending |", "| 02 | in_progress |"))
    shutil.copy(PLANTED / "stokcu" / "fiyat.py", proj / "stokcu" / "fiyat.py")
    (proj / "tests").mkdir()
    shutil.copy(PLANTED / "tests" / "test_fiyat.py", proj / "tests" / "test_fiyat.py")
    shutil.copy(PLANTED / "log.md", proj / "plan" / "logs" / "02.md")


def one(label, i, plugin):
    run_dir = OUT / label / f"run-{i}"
    if run_dir.exists():
        shutil.rmtree(run_dir)
    proj = run_dir / "proj"
    proj.mkdir(parents=True)
    setup(proj)
    p = proj.resolve()
    msg = (f"Tree to audit (project root): {p}. Step file: {p}/plan/steps/02.md. "
           f"Worker log: {p}/plan/logs/02.md.")
    prompt = (f"Spawn the karakam:observer-medium agent in the foreground with exactly this "
              f"message: '{msg}' Wait for it, then reply with its answer verbatim.")
    r = subprocess.run(["claude", "-p", prompt, "--model", "haiku", "--plugin-dir", str(plugin),
                        "--output-format", "json", "--permission-mode", "acceptEdits",
                        "--allowed-tools", *run.TOOLS.split()],
                       cwd=proj, capture_output=True, text=True, timeout=1800)
    try:
        d = json.loads(r.stdout)
    except json.JSONDecodeError:
        d = {"result": "", "total_cost_usd": 0, "error": r.stderr[-2000:]}
    reports = "\n".join(f.read_text() for f in sorted((proj / "plan" / "reports").glob("*.md")))
    text = (d.get("result") or "") + "\n" + reports
    res = {"cost": d.get("total_cost_usd"), "verdict": "FAIL" if re.search(r"\bFAIL\b", text) else
           "PASS" if re.search(r"\bPASS\b", text) else "?",
           "found": {k: bool(re.search(v, text, re.I)) for k, v in DEFECTS.items()},
           "reply": d.get("result"), "report": reports}
    (run_dir / "summary.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print(f"[{label}/run-{i}] {res['verdict']} {res['found']} ${res['cost']:.2f}", flush=True)


def report():
    for lab in sorted(p for p in OUT.glob("*") if p.is_dir()):
        rs = [json.loads(f.read_text()) for f in sorted(lab.glob("run-*/summary.json"))]
        if not rs:
            continue
        found = {k: sum(r["found"][k] for r in rs) for k in DEFECTS}
        print(f"{lab.name}: {len(rs)} runs, verdicts {[r['verdict'] for r in rs]}, "
              f"found {found}, mean {sum(sum(r['found'].values()) for r in rs) / len(rs):.1f}/4, "
              f"${sum(r['cost'] for r in rs) / len(rs):.2f}/run")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", nargs="?", default="run", choices=["run", "report"])
    ap.add_argument("--label", default="dev")
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--plugin-ref")
    a = ap.parse_args()
    if a.mode == "report":
        return report()
    plugin = run.snapshot_plugin(OUT / a.label / "plugin", a.plugin_ref)
    with ThreadPoolExecutor(a.runs) as ex:
        list(ex.map(lambda i: one(a.label, i, plugin), range(1, a.runs + 1)))
    report()


if __name__ == "__main__":
    sys.exit(main())
