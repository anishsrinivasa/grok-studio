#!/usr/bin/env python3
"""Validate the plugin: JSON files parse, SKILL.md / rules frontmatter are valid, names match.

Usage:  python3 scripts/validate.py
Uses PyYAML when installed (e.g. `uv run --with pyyaml python scripts/validate.py`); without it,
a small built-in parser reads the frontmatter forms this plugin uses.
"""
import json
import pathlib
import re
import sys

try:
    import yaml
except ImportError:  # no PyYAML on a clean machine: use the small parser below
    yaml = None


class FrontmatterError(ValueError):
    pass


def _scalar(v):
    v = v.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1]
    if v in ("true", "false"):
        return v == "true"
    return v


def simple_yaml(text):
    """The subset of YAML our frontmatter uses: `key: value`, quoted values, booleans,
    folded/literal blocks (`>`, `>-`, `|`, `|-`), `- item` lists and one nested mapping level."""
    lines = text.split("\n")
    data, i = {}, 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or line.lstrip().startswith("#"):
            i += 1
            continue
        if line[0] in " \t":
            raise FrontmatterError(f"unexpected indentation: {line!r}")
        if ":" not in line:
            raise FrontmatterError(f"expected `key: value`: {line!r}")
        key, rest = line.split(":", 1)
        key, rest = key.strip(), rest.strip()
        block = []
        i += 1
        while i < len(lines) and (not lines[i].strip() or lines[i][0] in " \t"):
            block.append(lines[i])
            i += 1
        while block and not block[-1].strip():
            block.pop()
        if rest in (">", ">-", "|", "|-"):
            body = [b.strip() for b in block]
            data[key] = (" ".join(b for b in body if b) if rest.startswith(">") else "\n".join(body))
        elif rest:
            if block:
                raise FrontmatterError(f"{key}: value followed by an indented block")
            data[key] = _scalar(rest)
        elif block and all(b.strip().startswith("- ") for b in block if b.strip()):
            data[key] = [_scalar(b.strip()[2:]) for b in block if b.strip()]
        elif block:
            data[key] = simple_yaml("\n".join(b.strip() for b in block))
        else:
            data[key] = None
    return data

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
        data = yaml.safe_load(m.group(1)) if yaml else simple_yaml(m.group(1))
    except (FrontmatterError, Exception) as e:  # yaml.YAMLError when PyYAML is present
        errors.append(f"{path}: invalid YAML frontmatter: {e}")
        return None
    if not isinstance(data, dict):
        errors.append(f"{path}: frontmatter is not a mapping")
        return None
    return data


# 1. JSON files
for p in sorted(ROOT.rglob("*.json")):
    if ".git" in p.parts or "node_modules" in p.parts:
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
BUILTIN = {"CURSOR_PLUGIN_ROOT"}
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
