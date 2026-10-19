"""
smoke_test.py - setup's readiness gate: can this Blender build, split, audit, export and render?

Cloud (headless):
    bash cloud_blender.sh run smoke_test.py [-- --out /workspace/grok-studio/.smoke]
    bash cloud_blender.sh run smoke_test.py -- --capture <studio capture png>   # G2 compare
User's Blender (Blender MCP, safe mode has no file API): send gs_core.py followed by
    print("GS_RESULT " + json.dumps(smoke_build("C:/Users/<you>/grok-studio/.smoke")))
read the GS_RESULT line, and write the returned manifest yourself.

Builds a 2-material block in its own collection (nothing else in the scene is touched),
splits it into 2 parts, audits, exports gs_smoke.fbx + gs_smoke.manifest.json and renders a
128 px image plus the Gate D three-quarter compare render (gs_smoke_compare_three_quarter.png,
camera in gs_smoke_camera.json, backdrop in the result) for setup's G2 Studio comparison. Prints one `GS_RESULT {json}` line with the paths; exit code 1 if anything
failed. Target: under 30 s (about 3 s on a laptop).
"""
import json
import os
import time

T0 = time.time()

import bpy  # noqa: E402

import compare_images  # noqa: E402
import gs_core  # noqa: E402
from asset_harness import GS_ROOT, job_args  # noqa: E402


def _remove_smoke(r):
    """smoke_build(keep=True) leaves its parts for the compare render; remove them now."""
    coll = bpy.data.collections.get("Asset_gs_smoke") or bpy.data.collections.get("gs_smoke")
    names = list(r.get("parts") or [])
    if coll is not None:
        names += [o.name for o in coll.all_objects]
    for name in set(names):
        o = bpy.data.objects.get(name)
        if o is not None:
            data = o.data
            bpy.data.objects.remove(o, do_unlink=True)
            if data is not None and getattr(data, "users", 1) == 0 and isinstance(data, bpy.types.Mesh):
                bpy.data.meshes.remove(data)
    for mat_name in ("GS_SmokeRed", "GS_SmokeBlue"):
        m = bpy.data.materials.get(mat_name)
        if m is not None and m.users == 0:
            bpy.data.materials.remove(m)
    if coll is not None and len(coll.all_objects) == 0:
        bpy.data.collections.remove(coll)


def compare_only(out_dir, capture):
    """G2 after the Studio capture: score it against the compare render (Gate D rules)."""
    with open(os.path.join(out_dir, "gs_smoke.manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)
    r = compare_images.compare_images(os.path.join(out_dir, "gs_smoke_compare_three_quarter.png"), capture,
                                      palette=compare_images.palette_from_manifest(manifest))
    print("GS_RESULT " + json.dumps(r))
    if not r.get("pass"):
        raise SystemExit(1)


def main():
    args = job_args()
    out_dir = os.path.abspath(args.get("out") or os.path.join(GS_ROOT, ".smoke"))
    os.makedirs(out_dir, exist_ok=True)
    if args.get("capture"):
        return compare_only(out_dir, os.path.abspath(args["capture"]))
    before = sorted(o.name for o in bpy.data.objects)

    r = gs_core.smoke_build(out_dir.replace("\\", "/"), keep=True)

    manifest_path = os.path.join(out_dir, "gs_smoke.manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(r.get("manifest"), f, indent=2)
    # G2's Studio comparison: the same three-quarter render + booth camera Gate D uses.
    compare = None
    try:
        if r.get("manifest"):
            compare = compare_images.render_compare(
                r["manifest"], "three_quarter", os.path.join(out_dir, "gs_smoke_compare_three_quarter.png"))
            with open(os.path.join(out_dir, "gs_smoke_camera.json"), "w", encoding="utf-8") as f:
                json.dump(compare["studio"], f)
    finally:
        _remove_smoke(r)
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
        "compare": compare and {"png": compare["png"], "studio": compare["studio"], "backdrop": compare["backdrop"],
                                "camera_json": os.path.join(out_dir, "gs_smoke_camera.json")},
    }))
    if not ok:
        raise SystemExit(1)


main()
