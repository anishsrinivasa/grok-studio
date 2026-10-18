"""
test_compare.py - compare_images on REAL Studio captures of the 2-colour smoke block.

    bash cloud_blender.sh run tests/test_compare.py

Fixtures (Oct 2026, live Studio, asset 78707418989252 = gs_smoke.fbx via Open Cloud):
  smoke_render_three_quarter.png  render_compare(manifest, "three_quarter") in Blender
  smoke_capture_ok.png            Studio capture after apply_manifest with the pivot fix
  smoke_capture_tilted.png        Studio capture with the importer's tilted pivot: the booth's
                                  PivotTo turned the block 90° and hid the Neon-blue top
The old hue histogram passed the tilted capture (0.735) and failed the good one (0.66).
  lion_render_three_quarter.png / lion_capture_ok.png / lion.manifest.json: the lion split
                                  (asset 106184897832197) after the axis + pivot fixes; the
                                  pastel colours come out much lighter in Studio
  lion_render_three_quarter_mirrored.png  the render flipped, as the old axis mapping gave
  lamp_*                          a 4-colour lamp post (asset 124423443376871): Metal iron
                                  renders navy, Neon glass pale, Slate stone light
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import compare_images as ci  # noqa: E402

F = os.path.join(HERE, "fixtures")
PALETTE = ["#D9443A", "#3A6FD9"]
render = os.path.join(F, "smoke_render_three_quarter.png")
good = ci.compare_images(render, os.path.join(F, "smoke_capture_ok.png"), palette=PALETTE)
bad = ci.compare_images(render, os.path.join(F, "smoke_capture_tilted.png"), palette=PALETTE)
lion_m = json.load(open(os.path.join(F, "lion.manifest.json")))
lion_pal = ci.palette_from_manifest(lion_m)
lion_cap = os.path.join(F, "lion_capture_ok.png")
lion = ci.compare_images(os.path.join(F, "lion_render_three_quarter.png"), lion_cap, palette=lion_pal)
# The pre-fix axis mapping rendered the Blender side mirrored (X and Z flipped).
lion_mirror = ci.compare_images(os.path.join(F, "lion_render_three_quarter_mirrored.png"), lion_cap, palette=lion_pal)
lamp_m = json.load(open(os.path.join(F, "lamp.manifest.json")))
lamp = ci.compare_images(os.path.join(F, "lamp_render_three_quarter.png"), os.path.join(F, "lamp_capture_ok.png"),
                         palette=ci.palette_from_manifest(lamp_m))
checks = [
    ("lamp_capture_passes", lamp["pass"], [lamp["silhouette"]["iouNormalized"], lamp["palette"]]),
    ("lion_capture_passes", lion["pass"], [lion["silhouette"], lion["palette"]["agreement"]]),
    ("lion_mirrored_render_fails", not lion_mirror["pass"], lion_mirror["silhouette"]),
    ("good_capture_passes", good["pass"], good["palette"]),
    ("tilted_capture_fails", not bad["pass"], bad["palette"]),
    ("tilted_reports_missing_blue", bad["palette"]["missing"] == ["#3A6FD9"], bad["palette"]["missing"]),
    ("palette_from_manifest", ci.palette_from_manifest({"parts": [{"hex": "#d9443a"}, {"hex": "#D9443A"}, {"hex": "#3A6FD9"}]}) == PALETTE, ""),
]
for name, ok, detail in checks:
    print("%s %s %s" % ("PASS" if ok else "FAIL", name, json.dumps(detail)))
ok = all(c[1] for c in checks)
print("GS_RESULT " + json.dumps({"ok": ok, "failed": [c[0] for c in checks if not c[1]]}))
if not ok:
    raise SystemExit(1)
