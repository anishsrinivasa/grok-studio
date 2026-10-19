#!/usr/bin/env python3
"""studio_payload.py - write the execute_luau code that builds and verifies a spec in Studio.

    python3 studio_payload.py <Board>.spec.json <out.luau> [--name ScreenGuiName]
        [--parent StarterGui] [--images images.json] [--verify-only] [--delete]

Saves hand-assembling penpot-ui steps 4-5 (wrapping PenpotUIBuilder.luau and
PenpotUIVerifier.luau, pasting the spec and images). Pass the file as the `code` of
execute_luau (Edit): on Grok Bot, CallDynamicTool replaces "$file:/abs/path.luau" with the
file. The call returns one JSON line: {"build": <report>, "verify": "PASS (n checks...)",
"status": "PASS"|"FAIL", "errors": [...]}.

--verify-only skips the build. --delete removes <parent>.<name>, only if it has the
PenpotBoardId attribute the builder sets (setup's G3 cleanup), and builds nothing.
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def long_string(text):
    level = 1
    while ("]" + "=" * level + "]") in text:
        level += 1
    eq = "=" * level
    return f"[{eq}[\n{text}]{eq}]"


def module(path):
    with open(path, encoding="utf-8") as f:
        src = f.read()
    return "(function()\n" + src.replace("--!strict", "", 1) + "\nend)()"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("spec")
    ap.add_argument("out")
    ap.add_argument("--name", help="ScreenGui name (default: the board name)")
    ap.add_argument("--parent", default="StarterGui", help="a service name, default StarterGui")
    ap.add_argument("--images", help="images.json from save_images.py")
    ap.add_argument("--verify-only", action="store_true")
    ap.add_argument("--delete", action="store_true")
    a = ap.parse_args()

    with open(a.spec, encoding="utf-8") as f:
        spec_text = f.read()
    spec = json.loads(spec_text)
    name = a.name or spec["board"]["name"]
    images = "{}"
    if a.images:
        with open(a.images, encoding="utf-8") as f:
            images = json.dumps(json.load(f))
    q = json.dumps  # Luau accepts JSON string literals for these plain names

    if a.delete:
        code = f"""local parent = game:GetService({q(a.parent)})
local s = parent:FindFirstChild({q(name)})
if s and s:GetAttribute("PenpotBoardId") ~= nil then s:Destroy() return '{{"deleted": true}}' end
return '{{"deleted": false, "reason": "missing or not built by PenpotUIBuilder"}}'
"""
    else:
        build = "" if a.verify_only else f"""
local Builder = {module(os.path.join(HERE, "PenpotUIBuilder.luau"))}
local _, report = Builder.build(spec, {{ parent = parent, name = {q(name)}, images = images }})
out.build = report
"""
        code = f"""local HttpService = game:GetService("HttpService")
local spec = HttpService:JSONDecode({long_string(spec_text)})
local images = HttpService:JSONDecode({long_string(images)})
local parent = game:GetService({q(a.parent)})
local out = {{}}
{build}
local Verifier = {module(os.path.join(HERE, "PenpotUIVerifier.luau"))}
local r = Verifier.verify(parent:FindFirstChild({q(name)}), spec)
out.verify = Verifier.report(r)
out.status = r.status
out.errors = r.errors
return HttpService:JSONEncode(out)
"""
    with open(a.out, "w", encoding="utf-8") as f:
        f.write(code)
    print(json.dumps({"out": os.path.abspath(a.out), "screen": f"{a.parent}.{name}", "bytes": len(code.encode())}))


if __name__ == "__main__":
    sys.exit(main())
