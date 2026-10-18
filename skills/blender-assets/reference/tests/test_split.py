"""
test_split.py - Blender checks for gs_core's split / manifest (no Studio, no network).

    bash cloud_blender.sh run tests/test_split.py

Prints one line per check and `GS_RESULT {"ok": ...}`; exit code 1 on any failure.
Covers: no loose verts (piece bounds), exact sRGB hex round trip, single-material meshes keep
their colour, children of a split object keep their world transform (re-parented to the main
piece), by_object limbs (names, main, joint, limbs table), axis mapping, re-split/re-export
gives the same manifest, and that merge mode still merges across objects.
"""
import json
import os
import sys
import tempfile

import bmesh
import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import gs_core as g  # noqa: E402

RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append({"name": name, "ok": bool(ok), "detail": detail})
    print("%s %s %s" % ("PASS" if ok else "FAIL", name, detail))


def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def cube(name, loc, mats, top_index=None, size=2.0, coll=None):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=size)
    for f in bm.faces:
        f.material_index = top_index if (top_index is not None and f.normal.z > 0.5) else 0
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    o = bpy.data.objects.new(name, me)
    o.location = loc
    (coll or g.asset_collection("t")).objects.link(o)
    return o


def mats():
    red = bpy.data.materials[g.flat_material("Red", "#FF0000")]
    blue = bpy.data.materials[g.flat_material("Blue", "#0000FF")]
    return red, blue


def test_colour_round_trip():
    reset()
    bad = []
    for v in range(256):
        h = "#%02X%02X%02X" % (v, 255 - v, v // 2)
        if g.material_info(bpy.data.materials[g.flat_material("C", h)])[1] != h:
            bad.append(h)
    check("colour_round_trip", not bad, bad[:5])


def test_bounds_single_children():
    reset()
    red, blue = mats()
    limb = cube("Limb", (0, 0, 5), [red, blue], top_index=1)
    single = cube("Single", (5, 0, 0), [blue])
    child = cube("Child", (0, 0, 3), [red])
    bpy.context.view_layer.update()
    empty = bpy.data.objects.new("Socket", None)
    g.asset_collection("t").objects.link(empty)
    for c in (child, empty):
        c.parent = limb
        c.matrix_parent_inverse = limb.matrix_world.inverted()
    empty.location = (0, 0, 4)  # local, under the inverse: world (0, 0, 9)
    bpy.context.view_layer.update()
    before = {c.name: c.matrix_world.translation.copy() for c in (child, empty)}
    r = g.split_by_material("t", [limb])
    bpy.context.view_layer.update()
    m = g.asset_manifest("t")
    parts = dict((p["name"], p) for p in m["parts"])
    check("piece_bounds_own_faces", parts["t_Blue"]["size"] == [2.0, 0.0, 2.0] and parts["t_Red"]["size"] == [2.0, 2.0, 2.0],
          [parts["t_Blue"]["size"], parts["t_Red"]["size"]])
    loose = [o.name for o in bpy.data.objects if o.type == "MESH"
             and len(o.data.vertices) != len(set(v for p in o.data.polygons for v in p.vertices))]
    check("no_loose_verts", not loose, loose)
    check("single_material_keeps_colour", parts["Single"]["hex"] == "#0000FF", parts["Single"]["hex"])
    moved = dict((n, round((bpy.data.objects[n].matrix_world.translation - before[n]).length, 4)) for n in before)
    parents = dict((n, bpy.data.objects[n].parent.name if bpy.data.objects[n].parent else None) for n in before)
    check("children_reparented_to_main", all(p == "t_Red" for p in parents.values()), parents)
    check("children_keep_world_transform", all(d < 1e-4 for d in moved.values()), moved)
    check("split_reports_reparented", len(r["reparented"]) == 2, r["reparented"])


def test_axes():
    v = g.roblox_vec(Vector((1.0, 2.0, 3.0)))
    back = g.blender_vec(v)
    check("axis_mapping_measured", v == [-1.0, 3.0, 2.0], v)
    check("axis_round_trip", tuple(round(c, 6) for c in back) == (1.0, 2.0, 3.0), tuple(back))


def build_creature():
    reset()
    red, blue = mats()
    body = cube("Body", (0, 0, 3), [red, blue], top_index=1, size=2.0)
    head = cube("Head", (0, 2, 4), [red, blue], top_index=1, size=1.0)  # head at Blender +Y
    bpy.context.view_layer.update()
    head.parent = body
    head.matrix_parent_inverse = body.matrix_world.inverted()
    bpy.context.view_layer.update()
    leg = cube("Leg", (1, 0, 1), [red], size=1.0)
    return body, head, leg


def test_by_object():
    build_creature()
    r = g.split_by_material("t", by_object=True)
    m = g.asset_manifest("t")
    names = sorted(p["name"] for p in m["parts"])
    check("by_object_names", names == ["Body_Blue", "Body_Red", "Head_Blue", "Head_Red", "Leg_Red"], names)
    limbs = m.get("limbs", {})
    check("by_object_limbs_table", sorted(limbs) == ["Body", "Head", "Leg"], sorted(limbs))
    check("by_object_main_is_biggest", limbs.get("Body", {}).get("main") == "Body_Red" and limbs.get("Head", {}).get("main") == "Head_Red",
          dict((k, v["main"]) for k, v in limbs.items()))
    check("by_object_limb_parent", limbs.get("Head", {}).get("parent") == "Body" and limbs.get("Body", {}).get("parent") is None,
          dict((k, v["parent"]) for k, v in limbs.items()))
    want = g.roblox_vec(Vector((0, 2, 4)) - Vector(m["pivot"]["blender"]))  # Head's origin
    check("joint_in_roblox_axes", limbs.get("Head", {}).get("joint") == want, [limbs.get("Head", {}).get("joint"), want])
    head_part = [p for p in m["parts"] if p["name"] == "Head_Red"][0]
    check("head_forward_is_plus_z", head_part["position"][2] > 0, head_part["position"])
    check("per_part_limb_fields", all("limb" in p and "main" in p and "joint" in p for p in m["parts"]))
    check("split_returns_limbs", r["limbs"].get("Leg") == "Leg_Red", r["limbs"])


def test_merge_mode_and_idempotent():
    build_creature()
    g.split_by_material("t")
    m1 = g.asset_manifest("t")
    names = sorted(p["name"] for p in m1["parts"])
    check("merge_mode_merges_across_objects", names == ["t_Blue", "t_Red"], names)
    check("merge_mode_has_no_limbs", "limbs" not in m1)
    g.split_by_material("t")
    m2 = g.asset_manifest("t")
    check("resplit_same_manifest", json.dumps(m1, sort_keys=True) == json.dumps(m2, sort_keys=True))
    d = tempfile.mkdtemp(prefix="gs-test-")
    names = [p["name"] for p in m2["parts"]]
    g.export_fbx(d + "/t.fbx", names)
    a = open(d + "/t.fbx", "rb").read()
    g.export_fbx(d + "/t.fbx", names)
    b = open(d + "/t.fbx", "rb").read()
    check("reexport_same_size", len(a) == len(b) and len(bpy.data.objects) == 2, [len(a), len(b), len(bpy.data.objects)])


for t in (test_colour_round_trip, test_bounds_single_children, test_axes, test_by_object, test_merge_mode_and_idempotent):
    try:
        t()
    except Exception as e:  # report and keep going
        check(t.__name__, False, "raised %r" % e)

ok = all(r["ok"] for r in RESULTS)
print("GS_RESULT " + json.dumps({"ok": ok, "failed": [r["name"] for r in RESULTS if not r["ok"]], "checks": len(RESULTS)}))
if not ok:
    raise SystemExit(1)
