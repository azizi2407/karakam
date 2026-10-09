#!/usr/bin/env python3
"""Repository consistency checks — run before committing and in CI.

  python3 tools/check.py

Checks:
  - every Markdown frontmatter in the plugin parses as strict YAML and has the
    fields Claude Code needs (GitHub renders it with a strict parser, so a
    value like `description: a: b` breaks the page even though Claude Code
    tolerates it);
  - plugins/karakam/agents/ is up to date with tools/agents-src/;
  - the two handoff-contract.md copies, and the two jev.py copies, are
    byte-identical;
  - plugin.json and marketplace.json agree on name, version and description,
    and every JSON manifest parses;
  - README.md and README.tr.md have the same structure (headings, code blocks,
    table rows);
  - every eval case.yaml parses;
  - karagoz's scripts/stepgit.sh commits and reverts exactly a step's files,
    including new, deleted and never-existing paths, and `land` never discards
    a worktree whose commit or merge failed;
  - jev.py sends typed questions and turns Jev's answers into advice, against
    a local stand-in for the API, and exits 3 when Jev is unavailable.
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("tools/check.py needs PyYAML: pip install pyyaml")

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "karakam"
errors = []


def err(msg):
    errors.append(msg)


def frontmatter(path):
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None
    return yaml.safe_load(text.split("---", 2)[1])


# 1. frontmatter
REQUIRED = {"skills": {"name", "description"},
            "agents": {"name", "description", "model", "effort", "tools"}}
for kind, fields in REQUIRED.items():
    pattern = "skills/*/SKILL.md" if kind == "skills" else "agents/*.md"
    for f in sorted(PLUGIN.glob(pattern)):
        rel = f.relative_to(ROOT)
        try:
            fm = frontmatter(f)
        except yaml.YAMLError as e:
            err(f"{rel}: frontmatter is not valid YAML ({str(e).splitlines()[0]})")
            continue
        if not isinstance(fm, dict):
            err(f"{rel}: missing frontmatter")
            continue
        missing = fields - fm.keys()
        if missing:
            err(f"{rel}: frontmatter lacks {sorted(missing)}")
        expected = f.parent.name if kind == "skills" else f.stem
        if fm.get("name") != expected:
            err(f"{rel}: name {fm.get('name')!r} should be {expected!r}")

# 2. generated agents
r = subprocess.run([sys.executable, str(ROOT / "tools" / "build_agents.py"), "--check"],
                   capture_output=True, text=True)
if r.returncode:
    err("plugins/karakam/agents/ is stale — run python3 tools/build_agents.py\n    "
        + r.stdout.strip().replace("\n", "\n    "))

# 3. contract copies
a, b = (PLUGIN / "skills" / s / "references" / "handoff-contract.md" for s in ("hacivat", "karagoz"))
if a.read_bytes() != b.read_bytes():
    err("the two handoff-contract.md copies differ — they must be byte-identical")
a, b = (PLUGIN / "skills" / s / "scripts" / "jev.py" for s in ("hacivat", "karagoz"))
if a.read_bytes() != b.read_bytes():
    err("the two jev.py copies differ — they must be byte-identical")

# 4. manifests
try:
    plugin = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    market = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
except json.JSONDecodeError as e:
    err(f"manifest is not valid JSON: {e}")
else:
    entry = next((p for p in market.get("plugins", []) if p.get("name") == plugin.get("name")), None)
    if entry is None:
        err(f"marketplace.json has no entry for plugin {plugin.get('name')!r}")
    else:
        for key in ("version", "description"):
            if entry.get(key) != plugin.get(key):
                err(f"marketplace.json {key} {entry.get(key)!r} != plugin.json {plugin.get(key)!r}")

# 5. README parity (same number of headings at each level)
def outline(path):
    """Headings, code fences and table rows, in order — language-independent."""
    shape, fenced = [], False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("```"):
            fenced = not fenced
            shape.append("```")
        elif not fenced and line.startswith("#"):
            shape.append(line.split(" ", 1)[0])
        elif not fenced and line.startswith("|"):
            shape.append("|" * line.count("|"))
    return shape
if outline(ROOT / "README.md") != outline(ROOT / "README.tr.md"):
    err("README.md and README.tr.md differ in structure (headings, code blocks or table rows)")

# 6. eval cases
for case in sorted((PLUGIN / "evals").glob("*/case.yaml")):
    try:
        yaml.safe_load(case.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        err(f"{case.relative_to(ROOT)}: invalid YAML ({str(e).splitlines()[0]})")

# 7. stepgit.sh behaviour
STEPGIT = PLUGIN / "skills" / "karagoz" / "scripts" / "stepgit.sh"


def git(repo, *args):
    return subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)


def write(repo, name, text):
    path = Path(repo, name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def dirty(repo):
    write(repo, "mod.txt", "changed\n")
    Path(repo, "del.txt").unlink(missing_ok=True)
    write(repo, "new.txt", "new\n")
    write(repo, "staged.txt", "staged\n")
    git(repo, "add", "staged.txt")
    write(repo, "src/pkg/deep.py", "x = 1\n")
    write(repo, "other.txt", "user edit\n")  # outside the step: must survive


with tempfile.TemporaryDirectory() as repo:
    git(repo, "init", "-q")
    for k, v in (("user.email", "check@example.com"), ("user.name", "check"), ("commit.gpgsign", "false")):
        git(repo, "config", k, v)
    for name in ("mod.txt", "del.txt", "other.txt"):
        write(repo, name, name + "\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "init")
    step = ["mod.txt", "del.txt", "new.txt", "staged.txt", "src/pkg/deep.py", "never.txt"]
    run = lambda *a: subprocess.run(["bash", str(STEPGIT), *a], cwd=repo, capture_output=True, text=True)

    dirty(repo)
    r = run("revert", *step)
    status = git(repo, "status", "--porcelain").stdout.split()
    if r.returncode or status != ["M", "other.txt"] or Path(repo, "del.txt").read_text() != "del.txt\n":
        err(f"stepgit.sh revert left the tree wrong: exit {r.returncode}, status {status}, {r.stderr.strip()}")

    git(repo, "checkout", "-q", "--", "other.txt")
    dirty(repo)
    r = run("commit", "karagoz step 01: check", *step)
    committed = sorted(git(repo, "show", "--name-only", "--format=", "HEAD").stdout.split())
    if r.returncode or committed != sorted(step[:-1]) or \
            git(repo, "status", "--porcelain").stdout.split() != ["M", "other.txt"]:
        err(f"stepgit.sh commit committed {committed}, exit {r.returncode}, {r.stderr.strip()}")

    hook = Path(repo, ".git", "hooks", "pre-commit")
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    write(repo, "mod.txt", "again\n")
    r = run("commit", "failing", "mod.txt")
    if r.returncode == 0 or git(repo, "diff", "--cached", "--name-only").stdout.strip():
        err("stepgit.sh commit should fail cleanly (nothing left staged) when the commit is rejected")

    git(repo, "checkout", "-q", "--", "mod.txt")

    # land: success, failing commit (worktree kept), conflict (aborted, kept)
    hook.unlink()
    def worktree(n, name, text):
        wt = str(Path(repo, ".worktrees", n))
        git(repo, "worktree", "add", "-q", wt, "-b", f"karagoz-step-{n}")
        write(wt, name, text)
        return wt
    Path(repo, ".git", "info", "exclude").write_text(".worktrees/\n")
    wt = worktree("02", "w2.txt", "two\n")
    r = run("land", wt, "karagoz-step-02", "karagoz step 02: land", "w2.txt")
    if r.returncode or Path(wt).exists() or Path(repo, "w2.txt").read_text() != "two\n" \
            or "karagoz step 02" not in git(repo, "log", "-1", "--format=%s").stdout:
        err(f"stepgit.sh land should commit, merge and clean up: exit {r.returncode}, {r.stderr.strip()}")

    wt = worktree("03", "w3.txt", "three\n")
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    r = run("land", wt, "karagoz-step-03", "karagoz step 03: land", "w3.txt")
    hook.unlink()
    if r.returncode != 1 or not Path(wt, "w3.txt").exists() or Path(repo, "w3.txt").exists():
        err(f"stepgit.sh land must keep the worktree when the commit fails: exit {r.returncode}")

    wt = worktree("04", "mod.txt", "theirs\n")
    write(repo, "mod.txt", "ours\n")
    run("commit", "main edit", "mod.txt")
    r = run("land", wt, "karagoz-step-04", "karagoz step 04: land", "mod.txt")
    if r.returncode != 2 or not Path(wt).exists() or Path(repo, ".git", "MERGE_HEAD").exists() \
            or Path(repo, "mod.txt").read_text() != "ours\n":
        err(f"stepgit.sh land must abort a conflicting merge and keep the worktree: exit {r.returncode}")

# 8. jev.py against a stand-in API
import http.server
import os
import threading

JEV = PLUGIN / "skills" / "karagoz" / "scripts" / "jev.py"


class FakeJev(http.server.BaseHTTPRequestHandler):
    seen = []

    def do_POST(self):
        req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeJev.seen.append((self.headers.get("Authorization"), req))
        answers = {}
        for qid, q in req["questions"].items():
            if q["type"] == "noul":
                answers[qid] = {"type": "noul", "noul": 0.05 if "librar" in q["instructions"] else 0.9}
            elif "mechanical" in req["state"]:
                answers[qid] = {"type": "choice", "choice": "low",
                                "probabilities": {"low": 0.9, "medium": 0.07, "high": 0.03}}
            elif qid == "fault":
                answers[qid] = {"type": "choice", "choice": "spec",
                                "probabilities": {"worker": 0.2, "spec": 0.7, "plan": 0.1}}
            else:
                answers[qid] = {"type": "choice", "choice": "high",
                                "probabilities": {"low": 0.1, "medium": 0.3, "high": 0.6}}
        body = json.dumps({"answers": answers}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


server = http.server.HTTPServer(("127.0.0.1", 0), FakeJev)
threading.Thread(target=server.serve_forever, daemon=True).start()
env = {**os.environ, "TYPESAFE_API_KEY": "k", "TYPESAFE_BASE_URL": f"http://127.0.0.1:{server.server_port}/"}
env.pop("KARAKAM_JUDGE", None)
with tempfile.TemporaryDirectory() as d:
    plan = Path(d)
    (plan / "steps").mkdir()
    (plan / "methodology.md").write_text("# Goal\nA stdlib-only tool.\n")
    (plan / "steps" / "01.md").write_text("Rename the module: mechanical.\n")
    (plan / "steps" / "02.md").write_text("Write the parser.\n")
    (plan / "steps" / "03.md").write_text("Wire the CLI: mechanical.\n")
    (plan / "progress.md").write_text(
        "| step | status | depends_on | effort | critical | file | note |\n|---|---|---|---|---|---|---|\n"
        "| 01 | pending | - | high | no | steps/01.md | |\n| 02 | pending | 01 | medium | no | steps/02.md | |\n"
        "| 03 | pending | 02 | high | yes | steps/03.md | |\n")

    def jev(*args, **kw):
        return subprocess.run([sys.executable, str(JEV), *map(str, args)], capture_output=True, text=True,
                              env=kw.get("env", env))

    r = jev("effort", plan)
    lines = r.stdout.splitlines()
    if r.returncode != 0 or len(lines) != 3 or not lines[0].endswith("lower to low") \
            or not lines[1].endswith("raise to high") or not lines[2].endswith("keep"):
        err(f"jev.py effort: lower a plain high step, raise a likely-high one, keep a critical one; got {r.stdout}{r.stderr}")
    if FakeJev.seen[0][0] != "Bearer k" or FakeJev.seen[0][1]["model"] != "jev-latest":
        err(f"jev.py must send the key as a bearer token and name the model: {FakeJev.seen[0]}")
    r = jev("lenses", plan)
    if r.returncode != 0 or "stack/library-correctness: p=0.05 -> skip in round 1" not in r.stdout \
            or "step-ordering & dependencies: p=0.90 -> run" not in r.stdout:
        err(f"jev.py lenses: skip an irrelevant lens, run a relevant one; got {r.stdout}{r.stderr}")
    r = jev("triage", plan / "steps" / "02.md", "FAIL: the spec's regex can't match ISO dates")
    if r.returncode != 0 or not r.stdout.startswith("spec (worker=0.20 spec=0.70 plan=0.10)"):
        err(f"jev.py triage: print the pick and every probability; got {r.stdout}{r.stderr}")
    r = jev("rubric", plan)
    if r.returncode != 0 or json.loads(r.stdout or "{}").get("runnable_criteria") != 0.9:
        err(f"jev.py rubric: print the yes-probability per check as JSON; got {r.stdout}{r.stderr}")
    for name, extra in (("no key", {"TYPESAFE_API_KEY": ""}), ("KARAKAM_JUDGE=off", {"KARAKAM_JUDGE": "off"}),
                        ("unreachable", {"TYPESAFE_BASE_URL": "http://127.0.0.1:9/"})):
        r = jev("effort", plan, env={**env, **extra})
        if r.returncode != 3 or not r.stdout.startswith("jev unavailable"):
            err(f"jev.py must exit 3 with 'jev unavailable' when {name}; got {r.returncode} {r.stdout}{r.stderr}")
server.shutdown()

if errors:
    print("\n".join(f"✗ {e}" for e in errors))
    sys.exit(1)
print("✓ all checks passed")
