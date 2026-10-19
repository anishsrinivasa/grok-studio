#!/usr/bin/env python3
"""console_classify.py - classify a Studio play-test console (get_console_output) the same way
every time: the readiness gate's G4 and the playtest loop.

    python3 console_classify.py <console.txt> [--marker GROK_STUDIO_SMOKE_OK] [--prefix GS_E2E]

<console.txt> is the get_console_output result saved to a file (MCP write_to_file); the
tool-result fence lines around it are ignored. Prints one JSON object:
    {"pass": bool, "markers": {...}, "fail": [...], "warn": [...], "expected": [...],
     "ignoredLines": n, "notes": [...]}
Exit code 0 = pass (every --marker present, zero fail lines), 1 = fail.

Rules (setup-bridge, "Reading the G4 console"):
- ignore: [Roblox]... and CorePackages... lines and their stack-trace lines, Studio-plugin
  chatter ("Animation Spoofer ...", "[robloxstudio-mcp] ...", "[Assistant]..."), blank lines
- expected: DataStore StudioAccessToApisNotAllowed / "Studio access to APIs is not allowed"
  and the game's own "persistence disabled" / "will NOT be saved" notes
- fail: a stack-trace line of a place script ("ServerScriptService.X:12", "Workspace.Y.Z:3
  function f"), "Script '...', Line n", "attempt to ...", "Infinite yield possible",
  "Requested module experienced an error", "Error running" / "Error: " / "error:" lines that
  aren't ignored. A plain log line that merely mentions a path (e.g.
  "[LionService] Registered Workspace.Map.Lion") is NOT a failure.
- warn: other game-side problems: "ContentId ... failed", "Failed to load", "is not a valid
  member", "Asset type does not match", "HTTP 4xx/5xx", "warning" lines from the place.
--prefix limits fail/warn to lines that mention that name (e.g. only your own test scripts);
other fail lines are reported under "otherFail" and don't fail the run.
"""
import argparse
import json
import re
import sys

SERVICES = r"(?:ServerScriptService|ReplicatedStorage|ReplicatedFirst|StarterPlayer|StarterGui|StarterPack|ServerStorage|Workspace|Players|Lighting|SoundService)"
STACK = re.compile(rf"^{SERVICES}\.[\w. ]+:\d+(?:\s+function\s+\S+)?\s*$")
ERROR_AT = re.compile(rf"^{SERVICES}\.[\w. ]+:\d+:\s")       # "ServerScriptService.Main:12: attempt to ..."
FAIL = [re.compile(p, re.I) for p in (
    r"Script '.*', Line \d+", r"\battempt to\b", r"Infinite yield possible",
    r"Requested module experienced an error", r"^Error running", r"^Stack Begin", r"\berror:\s",
    r"^\s*Error\b",
)]
IGNORE = [re.compile(p) for p in (
    r"^\[Roblox\]", r"^CorePackages\.", r"^CoreGui\.", r"^CoreScripts?\b", r"Animation Spoofer",
    r"^\[robloxstudio-mcp\]", r"^\[Assistant\]", r"^\[MCP\]", r"^<\/?cursor_untrusted", r"^Plugin_\d+",
    r"^cloud_\d+\.", r"^user_\w+\.rbxmx?",
)]
EXPECTED = [re.compile(p, re.I) for p in (
    r"StudioAccessToApisNotAllowed", r"Studio access to APIs is not allowed",
    r"persistence disabled", r"will NOT be saved", r"DataStore.*(?:Studio|not allowed)",
)]
WARN = [re.compile(p, re.I) for p in (
    r"ContentId:.*failed", r"Failed to load", r"is not a valid member", r"Asset type does not match",
    r"HTTP [45]\d\d", r"\bwarn(?:ing)?\b", r"not found", r"deprecated",
)]


def classify(text, markers, prefix=None):
    out = {"pass": False, "markers": {m: False for m in markers}, "fail": [], "otherFail": [],
           "warn": [], "expected": [], "ignoredLines": 0, "notes": []}
    in_core_trace = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            in_core_trace = False
            continue
        for m in markers:
            if m in line:
                out["markers"][m] = True
        if any(p.search(line) for p in IGNORE):
            in_core_trace = line.startswith(("[Roblox]", "CorePackages."))
            out["ignoredLines"] += 1
            continue
        if in_core_trace and re.match(r"^[\w.]+:\d+", line):
            out["ignoredLines"] += 1
            continue
        in_core_trace = False
        if any(p.search(line) for p in EXPECTED):
            out["expected"].append(line)
            continue
        if any(m in line for m in markers):
            continue
        is_fail = bool(STACK.match(line) or ERROR_AT.match(line) or any(p.search(line) for p in FAIL))
        if is_fail:
            (out["fail"] if (not prefix or prefix in line) else out["otherFail"]).append(line)
        elif any(p.search(line) for p in WARN):
            if not prefix or prefix in line or "ContentId" in line:
                out["warn"].append(line)
    out["warn"] = sorted(set(out["warn"]), key=out["warn"].index)
    out["expected"] = sorted(set(out["expected"]), key=out["expected"].index)
    if out["expected"]:
        out["notes"].append("DataStores need Game Settings > Security > Enable Studio Access to API Services "
                            "(expected in Studio; not a failure)")
    if any("Asset type does not match" in w for w in out["warn"]):
        out["notes"].append("an asset id of the wrong type is used in the place (e.g. a Decal id where an "
                            "Image/Texture id is expected): find it with a property scan")
    out["pass"] = all(out["markers"].values()) and not out["fail"]
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("console")
    ap.add_argument("--marker", action="append", default=[])
    ap.add_argument("--prefix")
    a = ap.parse_args()
    with open(a.console, encoding="utf-8", errors="replace") as f:
        r = classify(f.read(), a.marker, a.prefix)
    print(json.dumps(r, indent=1))
    return 0 if r["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
