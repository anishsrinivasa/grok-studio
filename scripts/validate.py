#!/usr/bin/env python3
"""Validate the plugin: JSON files parse, SKILL.md / rules frontmatter are valid, names match.

Usage:  uv run --with pyyaml python scripts/validate.py      (or plain python3 if PyYAML is installed)
"""
import json
import pathlib
import re
import sys

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML missing: run `uv run --with pyyaml python scripts/validate.py`")

ROOT = pathlib.Path(__file__).resolve().parent.parent
NAME_RE = re.compile(r"^[a-z0-9]([a-z0-9.-]*[a-z0-9])?$")
errors = []


def frontmatter(path):
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        errors.append(f"{path}: missing YAML frontmatter")
        return None
    try:
        data = yaml.safe_load(m.group(1))
    except yaml.YAMLError as e:
        errors.append(f"{path}: invalid YAML frontmatter: {e}")
        return None
    if not isinstance(data, dict):
        errors.append(f"{path}: frontmatter is not a mapping")
        return None
    return data


# 1. JSON files
for p in sorted(ROOT.rglob("*.json")):
    if ".git" in p.parts:
        continue
    try:
        json.loads(p.read_text(encoding="utf-8"))
        print(f"ok   json      {p.relative_to(ROOT)}")
    except json.JSONDecodeError as e:
        errors.append(f"{p}: invalid JSON: {e}")

# 2. Manifest
manifest = json.loads((ROOT / ".cursor-plugin/plugin.json").read_text())
if not NAME_RE.match(manifest.get("name", "")):
    errors.append(".cursor-plugin/plugin.json: name missing or not kebab-case")

# 3. Every ${VAR} used in mcp.json must be declared in manifest variables (or be a built-in).
BUILTIN = {"CURSOR_PLUGIN_ROOT", "CLAUDE_PLUGIN_ROOT"}
declared = set((manifest.get("variables") or {}).get("properties", {}).keys())
for var in re.findall(r"\$\{([A-Z0-9_]+)\}", (ROOT / "mcp.json").read_text()):
    if var not in BUILTIN | declared:
        errors.append(f"mcp.json uses ${{{var}}} but it is not declared in manifest variables")

# 4. Skills
skills = sorted((ROOT / "skills").glob("*/SKILL.md"))
if not skills:
    errors.append("no skills found")
for p in skills:
    fm = frontmatter(p)
    if fm is None:
        continue
    name, desc = fm.get("name"), fm.get("description")
    if not isinstance(name, str) or not NAME_RE.match(name):
        errors.append(f"{p}: 'name' missing or not kebab-case")
    elif name != p.parent.name:
        errors.append(f"{p}: name '{name}' != folder '{p.parent.name}'")
    if not isinstance(desc, str) or len(desc) < 40:
        errors.append(f"{p}: 'description' missing or too short")
    elif len(desc) > 1024:
        errors.append(f"{p}: 'description' longer than 1024 chars")
    print(f"ok   skill     {p.relative_to(ROOT)}  ({name})")

# 5. Rules
for p in sorted((ROOT / "rules").glob("*.mdc")):
    fm = frontmatter(p)
    if fm is None:
        continue
    if not isinstance(fm.get("description"), str):
        errors.append(f"{p}: rule needs a 'description'")
    if "alwaysApply" in fm and not isinstance(fm["alwaysApply"], bool):
        errors.append(f"{p}: alwaysApply must be boolean")
    print(f"ok   rule      {p.relative_to(ROOT)}")

if errors:
    print("\nFAILED:")
    for e in errors:
        print("  - " + e)
    sys.exit(1)
print("\nAll checks passed.")
