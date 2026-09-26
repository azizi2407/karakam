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
  - README.md and README.tr.md have the same section structure;
  - every eval case.yaml parses.
"""
import json
import subprocess
import sys
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
    heads, fenced = [], False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("```"):
            fenced = not fenced
        elif not fenced and line.startswith("#"):
            heads.append(line.split(" ", 1)[0])
    return heads
if outline(ROOT / "README.md") != outline(ROOT / "README.tr.md"):
    err("README.md and README.tr.md have different heading structures")

# 6. eval cases
for case in sorted((PLUGIN / "evals").glob("*/case.yaml")):
    try:
        yaml.safe_load(case.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        err(f"{case.relative_to(ROOT)}: invalid YAML ({str(e).splitlines()[0]})")

if errors:
    print("\n".join(f"✗ {e}" for e in errors))
    sys.exit(1)
print("✓ all checks passed")
