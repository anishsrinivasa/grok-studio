#!/usr/bin/env python3
"""fill_luau.py - fill the settings block of a grok-studio .luau script, write a ready
execute_luau body (no hand-pasting of manifests into 10-15 KB scripts).

    python3 fill_luau.py <script.luau> <out.luau> NAME=<luau value> ... NAME@=<file> ...

NAME=<value>   replaces `local NAME = ...` (one line) with the value as Luau source, e.g.
               'MODEL_PATH="Workspace.lava_rock"'  'MODE="cleanup"'  'CAM_POS=Vector3.new(0, 4002, 8)'
NAME@=<file>   puts the file's text into the long string `local NAME = [==[ ... ]==]`,
               e.g. MANIFEST_JSON@=exports/<id>.manifest.json  CAMERA_JSON@=cam.json
Fails if a NAME has no slot. On Grok Bot pass the result to execute_luau as "$file:<out.luau>".

Examples:
  python3 fill_luau.py apply_manifest.luau /tmp/apply.luau MANIFEST_JSON@=exports/rock.manifest.json 'MODEL_PATH="Workspace.rock"'
  python3 fill_luau.py capture_booth.luau /tmp/booth.luau 'MODEL_PATH="Workspace.rock"' CAMERA_JSON@=cam.json 'BACKDROP="#FF00FF"' 'BOOTH_PARENT="Workspace.GS_Tests"'
"""
import json
import re
import sys


def fill(text, assignments):
    for item in assignments:
        if "@=" in item:
            name, path = item.split("@=", 1)
            with open(path, encoding="utf-8") as f:
                value = f.read().strip()
            level = 2
            while ("]" + "=" * level + "]") in value:
                level += 1
            pat = re.compile(r"(local %s(?:\s*:\s*[\w?]+)?\s*=\s*)\[(=*)\[.*?\]\2\]" % re.escape(name), re.S)
            eq = "=" * level
            text, n = pat.subn(lambda m: f"{m.group(1)}[{eq}[\n{value}\n]{eq}]", text, count=1)
        else:
            name, value = item.split("=", 1)
            pat = re.compile(r"^(local %s(?:\s*:\s*[\w?]+)?\s*=\s*)[^\n]*?(\s*--[^\n]*)?$" % re.escape(name), re.M)
            text, n = pat.subn(lambda m: m.group(1) + value + (m.group(2) or ""), text, count=1)
        if n != 1:
            raise SystemExit(f"fill_luau: no `local {name} = ...` slot in the script")
    return text


def main(argv):
    if len(argv) < 3 or argv[0] in ("-h", "--help"):
        raise SystemExit(__doc__)
    src, out, items = argv[0], argv[1], argv[2:]
    with open(src, encoding="utf-8") as f:
        text = fill(f.read(), items)
    with open(out, "w", encoding="utf-8") as f:
        f.write(text)
    print(json.dumps({"out": out, "bytes": len(text.encode()), "filled": [i.split("=", 1)[0].rstrip("@") for i in items]}))


if __name__ == "__main__":
    main(sys.argv[1:])
