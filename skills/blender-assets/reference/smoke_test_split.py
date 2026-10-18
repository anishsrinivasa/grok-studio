"""
smoke_test_split.py - headless end-to-end test of the split-by-material export pipeline.

    bash cloud_blender.sh run smoke_test_split.py        (exit code 0 = PASS)

Builds a small rig the way the Builder does (limbs joined from closed primitives, origins
at the joints, a child limb, palette hexes that are not 0/255), plus edge cases (one
connected mesh painted per face, a duplicate material slot, an unused slot, smooth shading
+ UVs, a Bevel modifier), then runs export_fbx with split_materials=True and checks:

  * the step-5 audit notes multi-material meshes as "split at export" and stays OK
  * every exported mesh has exactly one material; FBX re-import confirms it
  * piece names are <Object>_<Material>; each limb has exactly one main piece
  * manifest colours are the sRGB palette hexes exactly (linear -> sRGB, rounded)
  * origins (world matrix) of every piece equal the original limb's joint
  * no loose vertices; each piece's bounds are its own geometry; triangle totals preserved
  * children of a split limb are re-parented to the limb's main piece, world pose kept
  * UVs, smooth shading, vertex groups and the Armature modifier survive the split
  * the pre-export audit is OK
  * exporting a second time is idempotent (same pieces, limbs and colours)
"""
import json
import os
import sys
import tempfile

import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from roblox_export import (  # noqa: E402
    audit, export_fbx, flat_material, manifest_path_for, setup_scene_for_roblox, triangle_count,
)

PALETTE = {"Fur": "#F6C57F", "Saddle": "#8FD6F0", "Eye": "#3B2A40", "EyeHi": "#FFFFFF",
           "Nose": "#9C4B66", "Red": "#FF0000", "Green": "#00FF00", "Blue": "#0000FF"}
FAILS = []


def check(cond, msg):
    print(("  ok   " if cond else "  FAIL ") + msg)
    if not cond:
        FAILS.append(msg)


def mat(name):
    return bpy.data.materials[flat_material(name, PALETTE[name])]


def join_limb(name, parts, joint):
    """parts: [(primitive op, location, scale, material name)] -> one mesh, origin at joint."""
    objs = []
    for op, loc, scale, mname in parts:
        op(location=loc)
        o = bpy.context.active_object
        o.scale = scale
        o.data.materials.append(mat(mname))
        objs.append(o)
    bpy.ops.object.select_all(action='DESELECT')
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    bpy.ops.object.join()
    o = bpy.context.active_object
    o.name = o.data.name = name
    bpy.context.scene.cursor.location = joint
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    return o


def build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    setup_scene_for_roblox()
    cube, sphere = bpy.ops.mesh.primitive_cube_add, bpy.ops.mesh.primitive_uv_sphere_add
    body = join_limb("Body", [(cube, (0, 0, 4), (1.5, 3, 1.2), "Fur"),
                              (cube, (0, 0, 5.3), (1.4, 1, 0.1), "Saddle")], (0, 0, 4))
    head = join_limb("Head", [(sphere, (0, 3.5, 5.5), (1, 1, 1), "Fur"),
                              (sphere, (0.4, 4.3, 5.8), (0.2, 0.2, 0.2), "Eye"),
                              (sphere, (-0.4, 4.3, 5.8), (0.2, 0.2, 0.2), "Eye"),
                              (sphere, (0.45, 4.45, 5.9), (0.06, 0.06, 0.06), "EyeHi"),
                              (cube, (0, 4.5, 5.3), (0.2, 0.1, 0.1), "Nose")], (0, 2.8, 5.2))
    for p in head.data.polygons:
        p.use_smooth = True
    head.data.materials.append(mat("Eye"))      # duplicate slot of a used material
    head.data.materials.append(mat("Saddle"))   # unused slot
    for p in head.data.polygons:                # move half the eye faces to the duplicate slot
        if head.data.materials[p.material_index].name == "Eye" and p.index % 2:
            p.material_index = len(head.data.materials) - 2
    head.parent = body
    head.matrix_parent_inverse = body.matrix_world.inverted()
    # One connected cube painted per face (pieces open at the seams) with a Bevel modifier.
    cube(size=2, location=(5, 0, 1))
    paint = bpy.context.active_object
    paint.name = "Crate"
    for m in ("Red", "Green", "Blue"):
        paint.data.materials.append(mat(m))
    for p in paint.data.polygons:
        p.material_index = p.index % 3
    bev = paint.modifiers.new("Bevel", "BEVEL")
    bev.width, bev.segments, bev.limit_method = 0.1, 1, 'NONE'
    # Single-material prop: must keep its name and get its real colour (not a placeholder).
    cube(size=1, location=(-5, 0, 0.5))
    prop = bpy.context.active_object
    prop.name = "Stone"
    prop.data.materials.append(mat("Nose"))
    # Skinned limb: Armature modifier + vertex groups must survive (weights stay usable).
    bpy.ops.object.armature_add(location=(0, -6, 0))
    rig = bpy.context.active_object
    rig.name = "Rig"
    arm = join_limb("Arm", [(cube, (0, -6, 1), (0.3, 0.3, 1), "Fur"),
                            (cube, (0, -6, 2.1), (0.35, 0.35, 0.1), "Saddle")], (0, -6, 0))
    vg = arm.vertex_groups.new(name="Bone")
    vg.add([v.index for v in arm.data.vertices], 1.0, 'REPLACE')
    arm.modifiers.new("Armature", "ARMATURE").object = rig
    arm.parent = rig
    arm.matrix_parent_inverse = rig.matrix_world.inverted()
    return ["Body", "Head", "Crate", "Stone", "Rig", "Arm"]


def snapshot(names):
    snap = {}
    for n in names:
        o = bpy.data.objects[n]
        if o.type != 'MESH':
            continue
        snap[n] = {"world": o.matrix_world.copy(), "tris": triangle_count(o),
                   "uv": bool(o.data.uv_layers), "smooth": any(p.use_smooth for p in o.data.polygons),
                   "dims": o.dimensions.copy()}
    return snap


def main():
    print("=== smoke_test_split ===")
    names = build()
    before = snapshot(names)

    print("step-5 audit (before export):")
    text = audit(names=[n for n in names if n != "Rig"])
    print("    " + text.replace("\n", "\n    "))
    for line in text.splitlines():
        if line.startswith(("Body", "Head", "Crate", "Arm")):
            check("split at export" in line, f"audit notes multi-material: {line.split(':')[0]}")
    check(all(line.endswith("OK") for line in text.splitlines()), "step-5 audit lines end in OK")

    tmp = tempfile.mkdtemp(prefix="gs-split-")
    fbx = os.path.join(tmp, "testrig.fbx")
    res = export_fbx(fbx, names)
    print("pre-export audit (after split):")
    print("    " + res["audit"].replace("\n", "\n    "))
    check(all(line.endswith("OK") for line in res["audit"].splitlines()), "pre-export audit all OK")
    check(res["manifest"] == manifest_path_for(fbx) and res["manifest"].endswith("testrig_manifest.json"),
          "manifest written as <fbx stem>_manifest.json")
    man = json.load(open(res["manifest"]))
    print(json.dumps(man["limbs"], indent=1))

    expect_pieces = {"Body": {"Body_Fur", "Body_Saddle"},
                     "Head": {"Head_Fur", "Head_Eye", "Head_EyeHi", "Head_Nose"},
                     "Crate": {"Crate_Red", "Crate_Green", "Crate_Blue"}, "Stone": {"Stone"},
                     "Arm": {"Arm_Fur", "Arm_Saddle"}}
    expect_main = {"Body": "Body_Fur", "Head": "Head_Fur", "Crate": "Crate_Red", "Stone": "Stone",
                   "Arm": "Arm_Fur"}
    check(man["colorSpace"] == "sRGB", "manifest colorSpace sRGB")
    for limb, pieces in expect_pieces.items():
        got = man["limbs"].get(limb, {})
        check(set(got.get("pieces", [])) == pieces, f"{limb} pieces {sorted(got.get('pieces', []))}")
        check(got.get("main") == expect_main[limb], f"{limb} main piece = {got.get('main')}")
        check(sum(man["meshes"][p]["main"] for p in got.get("pieces", [])) == 1, f"{limb} has one main")
        tris = sum(triangle_count(bpy.data.objects[p]) for p in got.get("pieces", []))
        if limb != "Crate":  # Crate's Bevel is applied per piece; seams change its count
            check(tris == before[limb]["tris"], f"{limb} triangles preserved ({tris})")

    for piece, info in man["meshes"].items():
        o = bpy.data.objects[piece]
        src = before[info["limb"]]
        mname = info["material"]
        check(len(o.data.materials) == 1, f"{piece}: one material slot")
        check(info["color"] == PALETTE[mname], f"{piece}: color {info['color']} == palette {PALETTE[mname]}")
        same = all(abs(a - b) < 1e-5 for ra, rb in zip(o.matrix_world, src["world"]) for a, b in zip(ra, rb))
        check(same, f"{piece}: origin/transform == {info['limb']} joint")
        used = {v for p in o.data.polygons for v in p.vertices}
        check(len(used) == len(o.data.vertices), f"{piece}: no loose vertices")
        if info["limb"] == "Head":
            check(bool(o.data.uv_layers) == src["uv"], f"{piece}: UV map kept")
            check(all(p.use_smooth for p in o.data.polygons), f"{piece}: smooth shading kept")
    check(bpy.data.objects["Head_Eye"].dimensions.y < 0.5 * before["Head"]["dims"].y,
          "Head_Eye bounds are the eyes only, not the whole head")
    check(man["limbs"]["Head"]["joint"] == [0.0, 5.2, -2.8], f"Head joint in Roblox axes {man['limbs']['Head']['joint']}")
    check(man["meshes"]["Head_Fur"]["parent"] == "Body_Fur", "child limb re-parented to main piece")
    head = bpy.data.objects["Head_Fur"]
    check((head.matrix_world.translation - before["Head"]["world"].translation).length < 1e-5,
          "child limb kept its world position")
    for piece in ("Arm_Fur", "Arm_Saddle"):
        o = bpy.data.objects[piece]
        check(o.parent and o.parent.name == "Rig" and "Bone" in o.vertex_groups
              and any(m.type == 'ARMATURE' and m.object and m.object.name == "Rig" for m in o.modifiers),
              f"{piece}: skinning kept (parent Rig, vertex group, Armature modifier)")
    check("Rig" in res["objects"], "armature passed through to the FBX")
    check("Body" not in bpy.data.objects and "Head" not in bpy.data.objects, "originals removed")

    print("second export (idempotent):")
    res2 = export_fbx(fbx, res["objects"])
    man2 = json.load(open(res2["manifest"]))
    check(man2["limbs"] == man["limbs"], "same limbs/main pieces on re-export")
    check({k: v["color"] for k, v in man2["meshes"].items()} == {k: v["color"] for k, v in man["meshes"].items()},
          "same colours on re-export")

    print("FBX re-import:")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.fbx(filepath=fbx)
    meshes = {o.name: o for o in bpy.context.scene.objects if o.type == 'MESH'}
    check(set(meshes) == set(man["meshes"]), f"FBX meshes == manifest meshes ({len(meshes)})")
    check(all(len(o.data.materials) == 1 for o in meshes.values()), "every FBX mesh has 1 material")

    print("=== PASS ===" if not FAILS else f"=== FAIL ({len(FAILS)}) ===")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
