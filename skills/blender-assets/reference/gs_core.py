"""
gs_core.py - grok-studio's Blender core. Runs the same everywhere:
  * cloud: headless Blender via `cloud_blender.sh run` (asset_harness imports it), or
  * the user's PC: pasted into the Blender MCP `execute_blender_code` tool, also with
    BLENDER_MCP_SAFE_MODE=1. So this file imports only bpy, bmesh, mathutils, math, json
    and re; it never uses os/sys/open/numpy/exec, and it returns plain dicts.

MCP usage: every execute_blender_code call starts from an empty namespace, so send this
whole file followed by ONE call that prints its result on a marker line, e.g.
    print("GS_RESULT " + json.dumps(split_by_material("lava_rock")))
and read the GS_RESULT line (Blender's exporters print their own lines too). Write any file
the result describes (the manifest JSON) yourself.

Coordinates: Blender is Z-up, Roblox is Y-up. The FBX export below (axis_forward -Z,
axis_up Y) maps a Blender vector (x, y, z) to Roblox (x, z, -y) - see roblox_vec(). Manifests
are in Roblox axes and studs (1 Blender unit = 1 stud).

Docs: https://create.roblox.com/docs/art/blender ,
https://create.roblox.com/docs/art/modeling/export-requirements ,
https://create.roblox.com/docs/art/modeling/specifications (20,000 triangles per mesh).
"""
import json
import math
import re

import bmesh
import bpy
from mathutils import Vector

ROBLOX_TRI_LIMIT = 20_000
MANIFEST_VERSION = 1


# --------------------------------------------------------------------------- basics

def setup_scene_for_roblox():
    """Units compatible with studs (Unit System None, scale 1)."""
    scene = bpy.context.scene
    scene.unit_settings.system = "NONE"
    scene.unit_settings.scale_length = 1.0
    return "scene units set: 1 BU = 1 stud"


def roblox_vec(v, digits=4):
    """Blender (x, y, z) -> Roblox (x, y, z) as the FBX export maps it."""
    return [round(v[0], digits) + 0.0, round(v[2], digits) + 0.0, round(-v[1], digits) + 0.0]


def blender_vec(r):
    """Roblox (x, y, z) -> Blender Vector (inverse of roblox_vec)."""
    return Vector((r[0], -r[2], r[1]))


def linear_from_hex(hex_color):
    h = hex_color.lstrip("#")
    rgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    return tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb)


def hex_from_linear(rgb):
    out = []
    for c in rgb[:3]:
        c = min(max(c, 0.0), 1.0)
        s = c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055
        out.append(round(s * 255))
    return "#%02X%02X%02X" % tuple(out)


def ensure_dir(directory):
    """Create `directory` (and parents). Blender's FBX/.blend writers don't, Image.save does."""
    img = bpy.data.images.new("_gs_keep", 1, 1, alpha=False)
    try:
        img.filepath_raw = directory.rstrip("/\\") + "/.gs_keep.png"
        img.file_format = "PNG"
        img.save()
    finally:
        bpy.data.images.remove(img)
    return directory


def _parent_dir(path):
    return path.replace("\\", "/").rsplit("/", 1)[0]


# --------------------------------------------------------------------------- the asset collection

def asset_collection(asset_id):
    """Collection "Asset_<id>" holding every object of the asset (created and linked if missing)."""
    name = "Asset_" + asset_id
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
    if coll.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(coll)
    return coll


def link_to_asset(asset_id, obj):
    """Move an object into the asset collection (out of every other collection)."""
    coll = asset_collection(asset_id)
    for c in list(obj.users_collection):
        if c != coll:
            c.objects.unlink(obj)
    if obj.name not in coll.objects:
        coll.objects.link(obj)
    return obj


def asset_meshes(asset_id, names=None):
    if names:
        return [bpy.data.objects[n] for n in names if n in bpy.data.objects and bpy.data.objects[n].type == "MESH"]
    coll = bpy.data.collections.get("Asset_" + asset_id)
    return [o for o in coll.all_objects if o.type == "MESH"] if coll else []


# --------------------------------------------------------------------------- materials

def flat_material(name, hex_color, roughness=0.8, metallic=0.0, roblox_material=None):
    """Principled BSDF material from a hex colour. roblox_material (e.g. "Wood", "Neon")
    is stored on the material and ends up in the manifest; default is SmoothPlastic."""
    lin = linear_from_hex(hex_color)
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    if not mat.node_tree:  # Blender 5.x materials always have nodes; older ones need this
        mat.use_nodes = True
    nodes = mat.node_tree.nodes
    # Find the shader by type, never by name (node names are localized).
    bsdf = next((n for n in nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        bsdf = nodes.new("ShaderNodeBsdfPrincipled")
        out = next((n for n in nodes if n.type == "OUTPUT_MATERIAL"), None) or nodes.new("ShaderNodeOutputMaterial")
        mat.node_tree.links.new(bsdf.outputs[0], out.inputs[0])
    bsdf.inputs["Base Color"].default_value = (*lin, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    # Workbench previews (review renders) read the viewport colour, not the node.
    mat.diffuse_color = (*lin, 1.0)
    mat.roughness = roughness
    mat.metallic = metallic
    if roblox_material:
        mat["roblox_material"] = roblox_material
    return mat.name


def material_info(mat):
    """(name, hex, Roblox material) for a material slot (None -> grey Default)."""
    if mat is None:
        return "Default", "#A3A2A5", "SmoothPlastic"
    rgb = tuple(mat.diffuse_color)[:3]
    metallic = mat.metallic
    if mat.node_tree:
        bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf:
            rgb = tuple(bsdf.inputs["Base Color"].default_value)[:3]
            metallic = bsdf.inputs["Metallic"].default_value
    rbx = mat.get("roblox_material") or ("Metal" if metallic >= 0.5 else "SmoothPlastic")
    return mat.name, hex_from_linear(rgb), str(rbx)


# --------------------------------------------------------------------------- checks

def triangle_count(obj):
    """Evaluated (modifiers applied) triangle count of a mesh object."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    mesh = eval_obj.to_mesh()
    try:
        return sum(len(p.vertices) - 2 for p in mesh.polygons)
    finally:
        eval_obj.to_mesh_clear()


def _non_manifold_edges(obj):
    """Edges not shared by exactly two faces (holes, fins). 0 = watertight."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    try:
        return sum(1 for e in bm.edges if not e.is_manifold)
    finally:
        bm.free()


def audit(budget_by_name=None, names=None, allow_open=False):
    """Triangles, size in studs, scale, n-gons, holes and material for every mesh.

    budget_by_name: {object name: max triangles}; names: only these objects.
    allow_open=True after split_by_material (a part cut out of a closed mesh is open by
    design; Roblox renders it fine). Every line ends in OK or lists issues to fix.
    """
    budget_by_name = budget_by_name or {}
    report = []
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH" or (names and obj.name not in names):
            continue
        tris = triangle_count(obj)
        budget = budget_by_name.get(obj.name, ROBLOX_TRI_LIMIT)
        ngons = sum(1 for p in obj.data.polygons if len(p.vertices) > 4)
        holes = _non_manifold_edges(obj)
        issues = []
        if tris > ROBLOX_TRI_LIMIT:
            issues.append("OVER ROBLOX LIMIT (%d > %d)" % (tris, ROBLOX_TRI_LIMIT))
        elif tris > budget:
            issues.append("over budget (%d > %d)" % (tris, budget))
        if any(abs(s - 1.0) > 1e-4 for s in obj.scale):
            issues.append("unapplied scale %s" % (tuple(round(s, 3) for s in obj.scale),))
        if ngons:
            issues.append("%d n-gons (triangulate or quad)" % ngons)
        if holes and not allow_open:
            issues.append("%d non-manifold edges (not watertight)" % holes)
        if not obj.data.materials:
            issues.append("no material")
        dims = tuple(round(d, 2) for d in obj.dimensions)
        report.append("%s: %d tris, dims(studs)=%s %s" % (obj.name, tris, dims, "; ".join(issues) or "OK"))
    return "\n".join(report)


def audit_ok(report):
    return bool(report) and all(line.rstrip().endswith("OK") for line in report.splitlines())


def apply_transforms(obj_names):
    """Apply rotation+scale so Roblox sees scale (1,1,1)."""
    bpy.ops.object.select_all(action="DESELECT")
    for name in obj_names:
        bpy.data.objects[name].select_set(True)
    bpy.context.view_layer.objects.active = bpy.data.objects[obj_names[0]]
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    return "applied transforms on %s" % obj_names


# --------------------------------------------------------------------------- split + manifest

def _safe_name(text):
    return re.sub(r"[^A-Za-z0-9_]+", "", text.replace(" ", "_").replace("-", "_")) or "Mat"


def split_by_material(asset_id, obj_or_names=None, merge_same_material=True):
    """One object per material: Roblox MeshParts carry one Color/Material each.

    Splits every mesh of the asset (or obj_or_names: an object, a name, or a list) by
    material, with modifiers applied, and rebuilds the pieces as objects named
    <id>_<Material> in the asset collection. Pieces sharing a material are merged into one
    object (merge_same_material=False keeps them apart as <id>_<Material>_2, ...). Each new
    object has rotation 0, scale 1 and its origin at its bounding-box centre.
    Don't use it on skinned meshes (rigs): it would detach them from the armature.
    Returns {"parts": [names], "removed": [old names]}.
    """
    if obj_or_names is None:
        objs = asset_meshes(asset_id)
    elif isinstance(obj_or_names, str):
        objs = [bpy.data.objects[obj_or_names]]
    elif isinstance(obj_or_names, bpy.types.Object):
        objs = [obj_or_names]
    else:
        objs = [bpy.data.objects[o] if isinstance(o, str) else o for o in obj_or_names]
    objs = [o for o in objs if o.type == "MESH"]
    if not objs:
        raise ValueError("split_by_material: no mesh objects for asset %r" % asset_id)

    depsgraph = bpy.context.evaluated_depsgraph_get()
    buckets, mats, order = {}, {}, []
    for obj in objs:
        ev = obj.evaluated_get(depsgraph)
        me = ev.to_mesh()
        bm = bmesh.new()
        bm.from_mesh(me)
        ev.to_mesh_clear()
        bm.transform(obj.matrix_world)  # world space: bakes location/rotation/scale
        slots = [s.material for s in obj.material_slots]
        for mi in sorted({f.material_index for f in bm.faces}):
            mat = slots[mi] if mi < len(slots) else None
            key = mat.name if mat else "Default"
            piece = bm.copy()
            bmesh.ops.delete(piece, geom=[f for f in piece.faces if f.material_index != mi], context="FACES")
            for f in piece.faces:
                f.material_index = 0
            if key not in buckets:
                buckets[key] = []
                order.append(key)
            buckets[key].append(piece)
            mats[key] = mat
        bm.free()

    removed = []
    coll = asset_collection(asset_id)
    for obj in objs:
        removed.append(obj.name)
        data = obj.data
        bpy.data.objects.remove(obj, do_unlink=True)
        if data is not None and data.users == 0:
            bpy.data.meshes.remove(data)

    parts = []
    for key in order:
        pieces = buckets[key]
        groups = [pieces] if merge_same_material else [[p] for p in pieces]
        for gi, group in enumerate(groups):
            merged = bmesh.new()
            for piece in group:
                tmp = bpy.data.meshes.new("_gs_tmp")
                piece.to_mesh(tmp)
                piece.free()
                merged.from_mesh(tmp)  # appends
                bpy.data.meshes.remove(tmp)
            lo = Vector((min(v.co.x for v in merged.verts), min(v.co.y for v in merged.verts), min(v.co.z for v in merged.verts)))
            hi = Vector((max(v.co.x for v in merged.verts), max(v.co.y for v in merged.verts), max(v.co.z for v in merged.verts)))
            centre = (lo + hi) / 2
            bmesh.ops.translate(merged, vec=-centre, verts=merged.verts)
            name = "%s_%s" % (asset_id, _safe_name(key)) + ("_%d" % (gi + 1) if gi else "")
            mesh = bpy.data.meshes.new(name)
            merged.to_mesh(mesh)
            merged.free()
            if mats[key] is not None:
                mesh.materials.append(mats[key])
            obj = bpy.data.objects.new(name, mesh)
            obj.location = centre
            coll.objects.link(obj)
            parts.append(obj.name)
    return {"parts": parts, "removed": removed}


def _world_bounds(objs):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    lo = Vector((math.inf, math.inf, math.inf))
    hi = Vector((-math.inf, -math.inf, -math.inf))
    per = {}
    for obj in objs:
        ev = obj.evaluated_get(depsgraph)
        me = ev.to_mesh()
        mw = obj.matrix_world
        olo = Vector((math.inf, math.inf, math.inf))
        ohi = Vector((-math.inf, -math.inf, -math.inf))
        for v in me.vertices:
            w = mw @ v.co
            olo = Vector((min(olo.x, w.x), min(olo.y, w.y), min(olo.z, w.z)))
            ohi = Vector((max(ohi.x, w.x), max(ohi.y, w.y), max(ohi.z, w.z)))
        ev.to_mesh_clear()
        per[obj.name] = (olo, ohi)
        lo = Vector((min(lo.x, olo.x), min(lo.y, olo.y), min(lo.z, olo.z)))
        hi = Vector((max(hi.x, ohi.x), max(hi.y, ohi.y), max(hi.z, ohi.z)))
    return lo, hi, per


def asset_manifest(asset_id, names=None, anchored=True, can_collide=True, collision="Box"):
    """Describe the asset for Studio: what apply_manifest.luau / post_import_check.luau use.

    Pivot = bottom centre of the asset's bounds. Part positions are the centres of the parts'
    bounding boxes relative to that pivot; sizes and positions are in Roblox axes, studs.
    collision: Roblox CollisionFidelity name (Default, Hull, Box,
    PreciseConvexDecomposition) or "none" (CanCollide off).
    """
    objs = asset_meshes(asset_id, names)
    if not objs:
        raise ValueError("asset_manifest: no mesh objects for asset %r" % asset_id)
    lo, hi, per = _world_bounds(objs)
    pivot = Vector(((lo.x + hi.x) / 2, (lo.y + hi.y) / 2, lo.z))
    parts, total, biggest = [], 0, (None, -1.0)
    for obj in objs:
        olo, ohi = per[obj.name]
        size_b = ohi - olo
        centre = (olo + ohi) / 2
        mat = obj.material_slots[0].material if obj.material_slots else None
        mname, hexc, rbx = material_info(mat)
        tris = triangle_count(obj)
        total += tris
        size_r = [round(size_b.x, 4), round(size_b.z, 4), round(size_b.y, 4)]
        volume = max(size_b.x, 0.01) * max(size_b.y, 0.01) * max(size_b.z, 0.01)
        if volume > biggest[1]:
            biggest = (obj.name, volume)
        multi = len({p.material_index for p in obj.data.polygons}) > 1
        parts.append({
            "name": obj.name, "material": mname, "hex": hexc, "robloxMaterial": rbx,
            "size": size_r, "position": roblox_vec(centre - pivot), "triangles": tris,
            "rotated": any(abs(a) > 1e-4 for a in obj.rotation_euler) or any(abs(s - 1) > 1e-4 for s in obj.scale),
            "multiMaterial": multi,
        })
    size_b = hi - lo
    return {
        "version": MANIFEST_VERSION,
        "id": asset_id,
        "fbx": asset_id + ".fbx",
        "units": "studs",
        "axes": "Roblox: +X right, +Y up, -Z forward (Blender x, z, -y)",
        "size": [round(size_b.x, 4), round(size_b.z, 4), round(size_b.y, 4)],
        "pivot": {"description": "bottom centre of the asset bounds", "blender": [round(c, 4) for c in pivot]},
        "triangles": total,
        "primaryPart": biggest[0],
        "anchored": bool(anchored),
        "canCollide": bool(can_collide) and collision != "none",
        "collisionFidelity": "Box" if collision == "none" else collision,
        "parts": parts,
    }


# --------------------------------------------------------------------------- export

def export_fbx(filepath, obj_names, with_animation=False):
    """Export the named objects to a Roblox-ready FBX (creates the folder; keeps the selection)."""
    ensure_dir(_parent_dir(filepath))
    view_layer = bpy.context.view_layer
    prev_sel = [o for o in view_layer.objects if o.select_get()]
    prev_active = view_layer.objects.active
    bpy.ops.object.select_all(action="DESELECT")
    for name in obj_names:
        bpy.data.objects[name].select_set(True)
    try:
        bpy.ops.export_scene.fbx(
            filepath=filepath,
            use_selection=True,
            apply_scale_options="FBX_SCALE_UNITS",  # "FBX Unit Scale"
            axis_forward="-Z",
            axis_up="Y",
            apply_unit_scale=True,
            use_mesh_modifiers=True,
            mesh_smooth_type="FACE",
            add_leaf_bones=False,
            bake_anim=with_animation,
            bake_anim_use_all_actions=False,
            bake_anim_use_nla_strips=False,
            path_mode="COPY",
            embed_textures=True,
        )
    finally:
        bpy.ops.object.select_all(action="DESELECT")
        for o in prev_sel:
            if o.name in view_layer.objects:
                o.select_set(True)
        view_layer.objects.active = prev_active
    return "exported %s -> %s" % (obj_names, filepath)


# --------------------------------------------------------------------------- smoke test

def smoke_build(directory, asset_id="gs_smoke", keep=False):
    """Readiness check: a 2-material block -> split -> audit -> FBX + manifest + one render.

    Safe in the user's open Blender: it builds in its own collection and removes everything
    it made afterwards (keep=True leaves it). Writes <directory>/<id>.fbx and
    <directory>/<id>_render.png. Returns the manifest instead of writing it (no file API here).
    """
    scene = bpy.context.scene
    coll = asset_collection(asset_id)
    red = bpy.data.materials[flat_material("GS_SmokeRed", "#D9443A")]
    blue = bpy.data.materials[flat_material("GS_SmokeBlue", "#3A6FD9", roblox_material="Neon")]
    mesh = bpy.data.meshes.new(asset_id + "_Block")
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=2.0)
    bmesh.ops.translate(bm, vec=Vector((0, 0, 1)), verts=bm.verts)
    for f in bm.faces:
        f.material_index = 1 if f.normal.z > 0.5 else 0
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(red)
    mesh.materials.append(blue)
    obj = bpy.data.objects.new(asset_id + "_Block", mesh)
    coll.objects.link(obj)
    block_name = obj.name  # split_by_material removes this object

    result = {"ok": False, "directory": directory}
    made_parts = []
    try:
        result["auditBefore"] = audit(names=[block_name])
        split = split_by_material(asset_id)
        made_parts = split["parts"]
        result["parts"] = made_parts
        result["audit"] = audit(names=made_parts, allow_open=True)
        fbx = directory.rstrip("/\\") + "/" + asset_id + ".fbx"
        export_fbx(fbx, made_parts)
        result["fbx"] = fbx
        result["manifest"] = asset_manifest(asset_id, collision="Box")

        png = directory.rstrip("/\\") + "/" + asset_id + "_render.png"
        hidden = [o for o in scene.objects if o.name not in made_parts and not o.hide_render]
        cam_data = bpy.data.cameras.new("_gs_smoke_cam")
        cam = bpy.data.objects.new("_gs_smoke_cam", cam_data)
        coll.objects.link(cam)
        prev = (scene.camera, scene.render.filepath, scene.render.resolution_x, scene.render.resolution_y,
                scene.render.film_transparent)
        prev_engine = scene.render.engine
        try:
            # Workbench works headless even without a GPU (software GL); fall back if absent.
            for engine in ("BLENDER_WORKBENCH", "BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "CYCLES"):
                try:
                    scene.render.engine = engine
                    break
                except TypeError:
                    continue
            for o in hidden:
                o.hide_render = True
            cam.location = Vector((5.0, -5.0, 4.5))
            cam.rotation_euler = (Vector((0, 0, 1)) - cam.location).to_track_quat("-Z", "Y").to_euler()
            scene.camera = cam
            scene.render.resolution_x = scene.render.resolution_y = 128
            scene.render.film_transparent = True
            scene.render.image_settings.file_format = "PNG"
            scene.render.filepath = png
            bpy.ops.render.render(write_still=True)
            result["render"] = png
            result["engine"] = scene.render.engine
        finally:
            for o in hidden:
                o.hide_render = False
            (scene.camera, scene.render.filepath, scene.render.resolution_x, scene.render.resolution_y,
             scene.render.film_transparent) = prev
            try:
                scene.render.engine = prev_engine
            except TypeError:
                pass
            bpy.data.objects.remove(cam, do_unlink=True)
            bpy.data.cameras.remove(cam_data)

        m = result["manifest"]
        result["ok"] = (
            len(made_parts) == 2
            and audit_ok(result["audit"])
            and audit_ok(result["auditBefore"])
            and sorted(p["hex"] for p in m["parts"]) == ["#3A6FD9", "#D9443A"]
            and m["size"] == [2.0, 2.0, 2.0]
        )
    finally:
        if not keep:
            for name in made_parts + [block_name]:
                o = bpy.data.objects.get(name)
                if o is not None:
                    data = o.data
                    bpy.data.objects.remove(o, do_unlink=True)
                    if data is not None and data.users == 0:
                        bpy.data.meshes.remove(data)
            for m_ in (red, blue):
                if m_.users == 0:
                    bpy.data.materials.remove(m_)
            if len(coll.all_objects) == 0:
                bpy.data.collections.remove(coll)
    return result
