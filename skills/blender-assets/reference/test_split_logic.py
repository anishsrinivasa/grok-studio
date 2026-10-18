#!/usr/bin/env python3
"""
test_split_logic.py - split-by-material checks that need no Blender (plain Python 3.9+).

    python3 test_split_logic.py          (exit code 0 = PASS)

* colour maths: sRGB hex -> linear (flat_material) -> sRGB hex (manifest) is exact for all
  256 channel values, and rounds rather than truncates
* names: <Object>_<Material> parts are Roblox-safe
* one manifest filename everywhere: roblox_export, asset_harness, both skills, the Luau helper
* the Luau helper reads exactly the keys the Python manifest writes
* the Luau helper works: studio/test_manifest_importer.luau runs against a mock Roblox API
  when a `luau` CLI is on PATH (or in $LUAU); skipped otherwise
The Blender side (real split, FBX export, re-import) is smoke_test_split.py.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.normpath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)

import roblox_export as rx  # noqa: E402  (imports without bpy: helpers only)
import asset_harness as ah  # noqa: E402

FAILS = []


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        FAILS.append(msg)


def read(*parts):
    with open(os.path.join(*parts), encoding="utf-8") as f:
        return f.read()


def test_colour():
    print("colour space (Blender linear <-> Roblox sRGB):")
    bad = [v for v in range(256)
           if rx.linear_to_srgb_hex(rx.srgb_hex_to_linear(f"#{v:02X}{v:02X}{v:02X}")) != f"#{v:02X}{v:02X}{v:02X}"]
    check(not bad, f"hex -> linear -> hex exact for all 256 levels (bad: {bad[:5]})")
    check(rx.linear_to_srgb_hex((1.0, 1.0, 1.0)) == "#FFFFFF", "white stays #FFFFFF (no truncation to FE)")
    check(rx.linear_to_srgb_hex((0.5, 0.5, 0.5)) == "#BCBCBC", "linear 0.5 -> sRGB #BCBCBC (not #7F7F7F)")
    check(rx.linear_to_srgb_hex((1.5, -0.2, 0.0)) == "#FF0000", "out-of-range values are clamped")
    check(rx.linear_to_srgb_hex(rx.srgb_hex_to_linear("#f6c57f")) == "#F6C57F", "lower-case input -> #F6C57F")


def test_names():
    print("names:")
    check(rx.safe_name("Lion Fur.001") == "Lion_Fur_001", "spaces/dots -> underscores")
    check(rx.safe_name("") == "Material" and rx.safe_name("...") == "Material", "empty -> Material")
    check(rx.safe_name("Eye_Hi") == "Eye_Hi", "safe names unchanged")


def test_manifest_filename():
    print("manifest filename consistency:")
    check(rx.manifest_path_for(os.path.join("exports", "lion.fbx")) == os.path.join("exports", "lion_manifest.json"),
          "roblox_export.manifest_path_for: exports/<id>_manifest.json")
    root = tempfile.mkdtemp()
    try:
        os.makedirs(os.path.join(root, "games", "g"))
        p = ah.asset_paths("lion", slug="g", root=root)
        check(p["manifest"] == rx.manifest_path_for(p["fbx"]), "asset_harness.asset_paths()['manifest'] matches")
    finally:
        shutil.rmtree(root)
    check("exports/<id>_manifest.json" in read(HERE, "..", "SKILL.md"), "blender-assets SKILL.md names it")
    check("exports/<id>_manifest.json" in read(PLUGIN, "skills", "roblox-building", "SKILL.md"),
          "roblox-building SKILL.md names it")
    check("exports/<id>_manifest.json" in read(HERE, "studio", "manifest_importer.lua"), "Luau helper names it")


def test_luau_keys():
    print("manifest keys Python writes == keys Luau reads:")
    py = read(HERE, "roblox_export.py")
    lua = read(HERE, "studio", "manifest_importer.lua")
    for key in ("limb", "main", "color", "meshes", "limbs"):
        check(f'"{key}"' in py and re.search(rf"\.{key}\b", lua) is not None, f"key '{key}'")
    check(lua.rstrip().endswith("return M"), "Luau helper ends in `return M` (wrap or require it)")


def test_luau_runtime():
    print("Luau helper against a mock Roblox API:")
    luau = os.environ.get("LUAU") or shutil.which("luau")
    if not luau:
        print("  skip (no `luau` CLI; get luau-ubuntu.zip from github.com/luau-lang/luau/releases)")
        return
    test = read(HERE, "studio", "test_manifest_importer.luau")
    module = read(HERE, "studio", "manifest_importer.lua")
    with tempfile.NamedTemporaryFile("w", suffix=".luau", delete=False) as f:
        f.write(test.replace("--@@IMPORTER@@", "(function()\n" + module + "\nend)()"))
        path = f.name
    try:
        r = subprocess.run([luau, path], capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(path)
    print("    " + (r.stdout + r.stderr).strip().replace("\n", "\n    "))
    check(r.returncode == 0, "test_manifest_importer.luau PASS")


def test_no_clutter():
    print("repo hygiene:")
    for name in ("IMPLEMENTATION_SUMMARY.md", os.path.join("skills", "blender-assets", "SPLIT_BY_MATERIAL_README.md")):
        check(not os.path.exists(os.path.join(PLUGIN, name)), f"no {name}")


if __name__ == "__main__":
    for t in (test_colour, test_names, test_manifest_filename, test_luau_keys, test_luau_runtime, test_no_clutter):
        t()
    print("=== PASS ===" if not FAILS else f"=== FAIL ({len(FAILS)}) ===")
    sys.exit(1 if FAILS else 0)
