"""
smoke_test.py - setup's readiness gate: can this Blender build, split, audit, export and render?

Cloud (headless):
    bash cloud_blender.sh run smoke_test.py [-- --out /workspace/grok-studio/.smoke]
User's Blender (Blender MCP, safe mode has no file API): send gs_core.py followed by
    print("GS_RESULT " + json.dumps(smoke_build("C:/Users/<you>/grok-studio/.smoke")))
read the GS_RESULT line, and write the returned manifest yourself.

Builds a 2-material block in its own collection (nothing else in the scene is touched),
splits it into 2 parts, audits, exports gs_smoke.fbx + gs_smoke.manifest.json and renders a
128 px image. Prints one `GS_RESULT {json}` line with the paths; exit code 1 if anything
failed. Target: under 30 s (about 3 s on a laptop).
"""
import json
import os
import time

T0 = time.time()

import bpy  # noqa: E402

import gs_core  # noqa: E402
from asset_harness import GS_ROOT, job_args  # noqa: E402


def main():
    args = job_args()
    out_dir = os.path.abspath(args.get("out") or os.path.join(GS_ROOT, ".smoke"))
    os.makedirs(out_dir, exist_ok=True)
    before = sorted(o.name for o in bpy.data.objects)

    r = gs_core.smoke_build(out_dir.replace("\\", "/"))

    manifest_path = os.path.join(out_dir, "gs_smoke.manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(r.get("manifest"), f, indent=2)
    fbx = r.get("fbx") or ""
    fbx_bytes = os.path.getsize(fbx) if fbx and os.path.exists(fbx) else 0
    render = r.get("render") or ""
    render_ok = bool(render) and os.path.exists(render) and os.path.getsize(render) > 0
    untouched = sorted(o.name for o in bpy.data.objects) == before
    seconds = round(time.time() - T0, 2)
    ok = bool(r.get("ok")) and fbx_bytes > 0 and render_ok and untouched and seconds < 30
    print("GS_RESULT " + json.dumps({
        "ok": ok, "seconds": seconds, "blender": bpy.app.version_string, "engine": r.get("engine"),
        "fbx": fbx, "fbxBytes": fbx_bytes, "manifest": manifest_path, "render": render,
        "parts": r.get("parts"), "audit": r.get("audit"), "sceneUntouched": untouched,
    }))
    if not ok:
        raise SystemExit(1)


main()
