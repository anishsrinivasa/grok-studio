#!/usr/bin/env python3
"""setup_state.py - small, deterministic helpers for /setup-bridge (Python 3.8+ stdlib only).

Runs on the Grok Bot cloud computer. Every command prints one JSON line.

  migrate                      Remove studio ids saved by older versions: `studio_id` and
                               `studio` from .bridge.json, `build.studioId` from every
                               games/*/game-spec.json. Studio ids change on every Studio
                               restart; only the place id is kept.
  bot-list                     List every Bot to create (one per roles/<id>/, name from its manifest).
  bot-text <role>              Print the instructions a Bot should have (its file without the
                               --- frontmatter). role: lead | coder | designer | builder | animator
  bot-diff <role> <file>       Compare a Bot's current instructions (its description, saved to
                               <file>) with the expected text. Whitespace-only differences
                               (line endings, indentation, blank lines, trailing spaces) do NOT
                               count. Prints {"same": true|false, ...}.
  needs-full-gate [--full] [--repaired]
                               Should this run do the full readiness gate (G2 asset upload,
                               G3 UI build, G4 playtest)? Yes on the first install, when the
                               plugin's skills/agents changed since the last full pass, when
                               the last full gate failed, when --repaired (setup fixed
                               something this run) or --full.
  record-gate --ok|--fail      Remember the result of a full gate for this plugin content.

Paths: GS_ROOT (default /workspace/grok-studio); the plugin is GS_ROOT/plugin, or the
repository this script lives in.
"""
import glob
import hashlib
import json
import os
import re
import sys
import tempfile
import time

GS = os.environ.get("GS_ROOT", "/workspace/grok-studio")
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(GS, "plugin") if os.path.isdir(os.path.join(GS, "plugin", "skills")) else HERE
STATE = os.path.join(GS, ".setup-state.json")
BRIDGE = os.path.join(GS, ".bridge.json")

def _discover_roles():
    """Every role folder under roles/ becomes a Bot. Lead keeps its bot prompt file."""
    files, names = {}, {}
    rdir = os.path.join(PLUGIN, "roles")
    for rid in sorted(os.listdir(rdir)) if os.path.isdir(rdir) else []:
        man = os.path.join(rdir, rid, "manifest.json")
        if not os.path.isfile(man):
            continue
        try:
            names[rid] = json.load(open(man, encoding="utf-8"))["role"]["name"]
        except Exception:
            names[rid] = rid
        files[rid] = "skills/setup-bridge/lead-bot.md" if rid == "lead" else f"roles/{rid}/agent.md"
    return files, names


ROLE_FILES, ROLE_NAMES = _discover_roles()


def out(obj, code=0):
    print(json.dumps(obj))
    sys.exit(code)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def write_json_atomic(path, data, mode=None):
    d = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp-")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    if mode is not None:
        os.chmod(tmp, mode)
    os.replace(tmp, path)


def strip_frontmatter(text):
    text = text.replace("\r\n", "\n")
    m = re.match(r"^---\n.*?\n---\n", text, re.S)
    return (text[m.end():] if m else text).strip() + "\n"


def normalize(text):
    """Whitespace-insensitive form: every run of whitespace becomes one space."""
    return " ".join(text.split())


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def expected_text(role):
    if role not in ROLE_FILES:
        out({"error": f"unknown role {role!r}", "roles": sorted(ROLE_FILES)}, 2)
    return strip_frontmatter(read(os.path.join(PLUGIN, ROLE_FILES[role])))


def plugin_content_hash():
    files = sorted(glob.glob(os.path.join(PLUGIN, "skills", "*", "SKILL.md"))
                   + glob.glob(os.path.join(PLUGIN, "agents", "*.md"))
                   + [os.path.join(PLUGIN, ROLE_FILES["lead"])])
    h = hashlib.sha256()
    for p in files:
        h.update(os.path.relpath(p, PLUGIN).replace("\\", "/").encode())
        h.update(normalize(read(p)).encode("utf-8"))
    return h.hexdigest()[:16]


def load_state():
    try:
        return json.loads(read(STATE))
    except (OSError, ValueError):
        return {}


def cmd_migrate():
    removed = []
    if os.path.exists(BRIDGE):
        try:
            data = json.loads(read(BRIDGE))
        except ValueError:
            data = None  # KEY=... lines or broken: leave it to connect-studio
        if isinstance(data, dict):
            gone = [k for k in ("studio_id", "studio") if k in data]
            if gone:
                for k in gone:
                    del data[k]
                write_json_atomic(BRIDGE, data, mode=0o600)
                removed.append({"file": BRIDGE, "fields": gone})
    for spec in sorted(glob.glob(os.path.join(GS, "games", "*", "game-spec.json"))):
        try:
            data = json.loads(read(spec))
        except ValueError:
            continue
        build = data.get("build") if isinstance(data, dict) else None
        if isinstance(build, dict) and "studioId" in build:
            del build["studioId"]
            write_json_atomic(spec, data)
            removed.append({"file": spec, "fields": ["build.studioId"]})
    out({"migrated": bool(removed), "removed": removed})


def cmd_bot_list():
    out([{"role": r, "name": ROLE_NAMES[r], "file": ROLE_FILES[r]} for r in ROLE_FILES])


def cmd_bot_text(role):
    sys.stdout.write(expected_text(role))


def cmd_bot_diff(role, current_path):
    want = expected_text(role)
    have = read(current_path)
    same = normalize(want) == normalize(have)
    out({"role": role, "same": same, "expected_sha": sha(normalize(want)),
         "current_sha": sha(normalize(have)), "file": ROLE_FILES[role]})


def cmd_needs_full_gate(args):
    st = load_state()
    content = plugin_content_hash()
    reasons = []
    if "--full" in args:
        reasons.append("asked (--full)")
    if "--repaired" in args:
        reasons.append("setup repaired something this run")
    if not st.get("last_full_gate_at"):
        reasons.append("no full gate has passed yet")
    elif st.get("plugin_content") != content:
        reasons.append("plugin skills/agents changed since the last full gate")
    elif not st.get("last_full_gate_ok"):
        reasons.append("the last full gate failed")
    out({"full": bool(reasons), "reasons": reasons, "plugin_content": content,
         "last_full_gate_at": st.get("last_full_gate_at")})


def cmd_record_gate(args):
    if "--ok" not in args and "--fail" not in args:
        out({"error": "pass --ok or --fail"}, 2)
    st = load_state()
    st.update(plugin_content=plugin_content_hash(), last_full_gate_ok="--ok" in args,
              last_full_gate_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    os.makedirs(GS, exist_ok=True)
    write_json_atomic(STATE, st)
    out(st)


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd, rest = argv[0], argv[1:]
    if cmd == "migrate":
        cmd_migrate()
    elif cmd == "bot-list":
        cmd_bot_list()
    elif cmd == "bot-text" and len(rest) == 1:
        cmd_bot_text(rest[0])
    elif cmd == "bot-diff" and len(rest) == 2:
        cmd_bot_diff(rest[0], rest[1])
    elif cmd == "needs-full-gate":
        cmd_needs_full_gate(rest)
    elif cmd == "record-gate":
        cmd_record_gate(rest)
    else:
        out({"error": f"bad command: {' '.join(argv)}", "help": "setup_state.py --help"}, 2)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
