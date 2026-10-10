#!/usr/bin/env python3
"""Repository consistency checks — run before committing and in CI.

  python3 tools/check.py

Checks:
  - every Markdown frontmatter in the plugin parses as strict YAML and has the
    fields Claude Code needs (GitHub renders it with a strict parser, so a
    value like `description: a: b` breaks the page even though Claude Code
    tolerates it);
  - plugins/karakam/agents/ is up to date with tools/agents-src/;
  - the two handoff-contract.md copies are byte-identical;
  - plugin.json and marketplace.json agree on name, version and description,
    and every JSON manifest parses;
  - README.md and README.tr.md have the same structure (headings, code blocks,
    table rows);
  - every eval case.yaml parses;
  - karagoz's scripts/stepgit.sh commits and reverts exactly a step's files,
    including new, deleted and never-existing paths, and `land` never discards
    a worktree whose commit or merge failed.
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
            "agents": {"name", "description", "model", "effort"}}
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
        if kind == "agents" and ("tools" in fm) == ("disallowedTools" in fm):
            err(f"{rel}: frontmatter needs exactly one of tools / disallowedTools")
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

if errors:
    print("\n".join(f"✗ {e}" for e in errors))
    sys.exit(1)
print("✓ all checks passed")
