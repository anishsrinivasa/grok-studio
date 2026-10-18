"""
roblox_export.py - Blender helpers for Roblox-ready low-poly assets.

Cloud/headless: `cloud_blender.sh run job.py` puts this folder on sys.path, so a job just
does `from roblox_export import *` (or uses asset_harness, which re-exports these).
Local Blender MCP: paste the functions you need into `execute_blender_code`.
Tested headless with Blender 5.2.2 (blender -b) and earlier with the bpy 5.0.1 wheel
(scene setup, audit, apply, material, FBX export).

Conventions (see https://create.roblox.com/docs/art/blender):
  * Scene units: Unit System = None, so 1 Blender unit == 1 stud.
  * Up axis: Blender is Z-up, Roblox is Y-up; the FBX exporter converts (axis_up='Y').
  * Export: FBX, Path Mode = Copy + Embed Textures, Apply Scalings = FBX Unit Scale,
    no leaf bones, bake animation only when exporting animation
    (https://create.roblox.com/docs/art/modeling/export-requirements).
  * Hard limit: 20,000 triangles per mesh
    (https://create.roblox.com/docs/art/modeling/specifications).
"""
import json
import os
import re

try:
    import bpy
    import bmesh
except ImportError:  # plain Python: colour/name helpers only (unit tests)
    bpy = bmesh = None

ROBLOX_TRI_LIMIT = 20_000


def setup_scene_for_roblox():
    """Units compatible with studs (Unit System None, scale 1)."""
    scene = bpy.context.scene
    scene.unit_settings.system = 'NONE'
    scene.unit_settings.scale_length = 1.0
    return "scene units set: 1 BU = 1 stud"


def triangle_count(obj) -> int:
    """Evaluated (modifiers applied) triangle count of a mesh object."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    mesh = eval_obj.to_mesh()
    try:
        bm = bmesh.new()
        bm.from_mesh(mesh)
        tris = sum(len(f.verts) - 2 for f in bm.faces)
        bm.free()
        return tris
    finally:
        eval_obj.to_mesh_clear()


def _non_manifold_edges(obj) -> int:
    """Edges that are not shared by exactly two faces (holes, fins). 0 = watertight."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    try:
        return sum(1 for e in bm.edges if not e.is_manifold)
    finally:
        bm.free()


def _material_is_flat(mat):
    """True when the material is a single flat colour (no image textures, nothing driving Base Color)."""
    if mat is None or not mat.node_tree:
        return True
    if any(n.type == "TEX_IMAGE" for n in mat.node_tree.nodes):
        return False
    bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
    return not (bsdf and bsdf.inputs["Base Color"].is_linked)


def audit(budget_by_name=None, names=None, check_single_material=False, check_flat_materials=True):
    """Report triangles, size in studs, scale, n-gons, holes and materials for every mesh.

    budget_by_name: {object name: max triangles}; names: only audit these objects.
    check_single_material: False (default, the step-5 audit): a mesh with several materials is
        fine and is noted as "[N materials, split at export]" because export_fbx splits it.
        True (the pre-export audit export_fbx runs after splitting): more than one material
        slot is an issue ("MULTIPLE MATERIALS").
    check_flat_materials: flag materials that use image textures or drive Base Color with nodes
        (their manifest colour would not match what Roblox shows).
    Returns text, one line per mesh. Every line must end in OK; lines that list issues must be
    fixed (or the issue accepted on purpose) before export. Split pieces may be open where two
    materials met; that is noted, not an issue, when the source mesh was watertight.
    """
    budget_by_name = budget_by_name or {}
    report = []
    for obj in bpy.context.scene.objects:
        if obj.type != 'MESH' or (names and obj.name not in names):
            continue
        tris = triangle_count(obj)
        budget = budget_by_name.get(obj.name, ROBLOX_TRI_LIMIT)
        ngons = sum(1 for p in obj.data.polygons if len(p.vertices) > 4)
        holes = _non_manifold_edges(obj)
        issues, notes = [], []
        if tris > ROBLOX_TRI_LIMIT:
            issues.append(f"OVER ROBLOX LIMIT ({tris} > {ROBLOX_TRI_LIMIT})")
        elif tris > budget:
            issues.append(f"over budget ({tris} > {budget})")
        if any(abs(s - 1.0) > 1e-4 for s in obj.scale):
            issues.append(f"unapplied scale {tuple(round(s, 3) for s in obj.scale)}")
        if ngons:
            issues.append(f"{ngons} n-gons (triangulate or quad)")
        if holes:
            if holes <= int(obj.get(PROP_SEAM_EDGES, 0)):
                notes.append("open at material seams")
            else:
                issues.append(f"{holes} non-manifold edges (not watertight)")
        mats = _used_materials(obj)
        if not obj.data.materials or not mats:
            issues.append("no material")
        elif check_single_material and len(obj.data.materials) > 1:
            issues.append(f"MULTIPLE MATERIALS ({len(obj.data.materials)} slots); split before export")
        elif len(mats) > 1:
            notes.append(f"{len(mats)} materials, split at export")
        if check_flat_materials:
            textured = [m.name for m in mats if not _material_is_flat(m)]
            if textured:
                issues.append(f"not flat (textures/nodes): {', '.join(textured)}")
        dims = tuple(round(d, 2) for d in obj.dimensions)
        line = f"{obj.name}: {tris} tris, dims(studs)={dims} "
        if notes:
            line += "[" + "; ".join(notes) + "] "
        report.append(line + ("; ".join(issues) or "OK"))
    return "\n".join(report)


def apply_transforms(obj_names):
    """Apply rotation+scale so Roblox sees scale (1,1,1)."""
    bpy.ops.object.select_all(action='DESELECT')
    for name in obj_names:
        bpy.data.objects[name].select_set(True)
    bpy.context.view_layer.objects.active = bpy.data.objects[obj_names[0]]
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
    return f"applied transforms on {obj_names}"


def flat_material(name, hex_color, roughness=0.8, metallic=0.0):
    """Simple Principled BSDF material from a hex color (imports as MeshPart color/texture)."""
    lin = srgb_hex_to_linear(hex_color)  # palette hex is sRGB; the BSDF wants linear
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
    return mat.name


# --------------------------------------------------------------------------- colours / names

# Custom properties written on split pieces, so a second export (or a re-opened .blend) still
# knows which limb each piece belongs to and which piece carries the limb's joint.
PROP_LIMB = "gs_limb"
PROP_MAIN = "gs_main"
PROP_SEAM_EDGES = "gs_seam_edges"
MANIFEST_SUFFIX = "_manifest.json"


def linear_to_srgb_hex(rgb):
    """Blender stores colours scene-linear; Roblox Color3 / hex are sRGB. -> '#RRGGBB'."""
    out = []
    for c in rgb[:3]:
        c = min(max(float(c), 0.0), 1.0)
        s = c * 12.92 if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055
        out.append(min(255, max(0, round(s * 255))))
    return "#{:02X}{:02X}{:02X}".format(*out)


def srgb_hex_to_linear(hex_color):
    """'#RRGGBB' (sRGB, what Roblox and palettes use) -> linear (r, g, b) for Blender."""
    h = hex_color.lstrip('#')
    rgb = tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    return tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb)


def material_hex(mat):
    """sRGB '#RRGGBB' of a flat material: Principled Base Color, else the viewport colour."""
    if mat is None:
        return "#A3A2A5"  # Roblox default part grey
    if mat.node_tree:
        bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf is not None:
            return linear_to_srgb_hex(bsdf.inputs["Base Color"].default_value)
    return linear_to_srgb_hex(mat.diffuse_color)


def safe_name(text):
    """Roblox-friendly instance name part: letters, digits and underscores only."""
    return re.sub(r"[^A-Za-z0-9_]+", "_", text or "").strip("_") or "Material"


def manifest_path_for(fbx_path):
    """exports/<id>.fbx -> exports/<id>_manifest.json (the name Studio-side helpers expect)."""
    return os.path.splitext(fbx_path)[0] + MANIFEST_SUFFIX


def _used_materials(obj):
    """Distinct materials actually used by the mesh's faces, in slot order (None = empty slot)."""
    slots = obj.material_slots
    if not slots:
        return []
    used_idx = sorted({min(p.material_index, len(slots) - 1) for p in obj.data.polygons})
    seen, out = set(), []
    for i in used_idx:
        mat = slots[i].material
        key = mat.name if mat else None
        if key not in seen:
            seen.add(key)
            out.append(mat)
    return out


# --------------------------------------------------------------------------- split by material

def _baked_mesh(obj):
    """Mesh data with every modifier except Armature applied (so seams match what you see,
    and skinned meshes keep their weights). Returns (mesh, baked: bool)."""
    if not any(m.type != 'ARMATURE' for m in obj.modifiers):
        return obj.data, False
    toggled = []
    for m in obj.modifiers:
        if m.type == 'ARMATURE' and m.show_viewport:
            m.show_viewport = False
            toggled.append(m)
    try:
        depsgraph = bpy.context.evaluated_depsgraph_get()
        eval_obj = obj.evaluated_get(depsgraph)
        mesh = bpy.data.meshes.new_from_object(eval_obj, preserve_all_data_layers=True,
                                               depsgraph=depsgraph)
    finally:
        for m in toggled:
            m.show_viewport = True
    return mesh, True


def _keep_faces(mesh, slot_indices):
    """Delete faces whose material slot is not in slot_indices, plus the loose verts/edges left."""
    bm = bmesh.new()
    bm.from_mesh(mesh)
    try:
        last = max(len(mesh.materials) - 1, 0)
        drop = [f for f in bm.faces if min(f.material_index, last) not in slot_indices]
        bmesh.ops.delete(bm, geom=drop, context='FACES_ONLY')
        loose_e = [e for e in bm.edges if not e.link_faces]
        bmesh.ops.delete(bm, geom=loose_e, context='EDGES')
        loose_v = [v for v in bm.verts if not v.link_faces]
        bmesh.ops.delete(bm, geom=loose_v, context='VERTS')
        for f in bm.faces:
            f.material_index = 0
        bm.to_mesh(mesh)
    finally:
        bm.free()
    mesh.update()


def _record(obj, limb, main):
    mat = obj.material_slots[0].material if obj.material_slots else None
    return {"name": obj.name, "limb": limb, "main": main,
            "material": mat.name if mat else None, "color": material_hex(mat)}


def split_by_material(obj):
    """Split a mesh object into one object per material, named <Object>_<Material>.

    * Each piece keeps the original object's transform, parent, modifiers (Armature),
      vertex groups, UVs and shading, so its origin stays at the limb's joint and it
      animates exactly like the original. Only that material's faces are kept; loose
      vertices are removed, so each piece's bounds are its own geometry.
    * The piece made from the first used material slot is the limb's MAIN piece (the one
      the Animator puts the Motor6D on; the others are welded to it in Studio). Override
      with the custom property obj["gs_main_material"] = "<material name>".
    * Children of the original are re-parented to the main piece (world transform kept).
    * Duplicate slots of the same material become one piece; unused slots are ignored.
    * Objects with one material are not renamed; they are their own main piece.

    The original object is removed. Returns a list of records
    {"name", "limb", "main", "material", "color"} (color = sRGB "#RRGGBB").
    Safe to call again on its own output (pieces remember their limb via custom properties).
    """
    if obj.type != 'MESH':
        return []
    limb = obj.get(PROP_LIMB, obj.name)
    mats = _used_materials(obj)
    if len(mats) <= 1:
        # Already single-material: drop unused slots so the FBX carries exactly one material.
        if len(obj.data.materials) > 1 and mats:
            keep = mats[0]
            if obj.data.users > 1:
                obj.data = obj.data.copy()
            for p in obj.data.polygons:
                p.material_index = 0
            obj.data.materials.clear()
            obj.data.materials.append(keep)
        obj[PROP_LIMB] = limb
        obj[PROP_MAIN] = bool(obj.get(PROP_MAIN, True))
        return [_record(obj, limb, bool(obj[PROP_MAIN]))]

    main_name = obj.get("gs_main_material")
    main_mat = next((m for m in mats if m and m.name == main_name), mats[0])
    src_holes = _non_manifold_edges(obj)
    base, baked = _baked_mesh(obj)
    slots = obj.material_slots
    pieces, main_obj = [], None
    try:
        for mat in mats:
            idx = {i for i, s in enumerate(slots)
                   if (s.material.name if s.material else None) == (mat.name if mat else None)}
            mesh = base.copy()
            _keep_faces(mesh, idx)
            if not mesh.polygons:
                bpy.data.meshes.remove(mesh)
                continue
            mesh.materials.clear()
            mesh.materials.append(mat)
            piece = obj.copy()  # transform, parent (+inverse), modifiers, constraints, props
            piece.data = mesh
            if baked:
                for m in [m for m in piece.modifiers if m.type != 'ARMATURE']:
                    piece.modifiers.remove(m)
            if piece.material_slots:
                piece.material_slots[0].link = 'DATA'
            piece.name = f"{limb}_{safe_name(mat.name if mat else 'Material')}"
            mesh.name = piece.name
            for coll in obj.users_collection:
                coll.objects.link(piece)
            piece[PROP_LIMB] = limb
            piece[PROP_MAIN] = (mat == main_mat)
            if src_holes == 0:
                piece[PROP_SEAM_EDGES] = _non_manifold_edges(piece)
            if mat == main_mat:
                main_obj = piece
            pieces.append(piece)
    finally:
        if baked:
            bpy.data.meshes.remove(base)

    for child in list(obj.children):
        world = child.matrix_world.copy()
        child.parent = main_obj
        child.matrix_world = world

    old_mesh = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)
    if old_mesh.users == 0:
        bpy.data.meshes.remove(old_mesh)
    return [_record(p, limb, bool(p[PROP_MAIN])) for p in pieces]


def split_all_by_material(obj_names):
    """Split every multi-material mesh in obj_names. Returns (manifest, final_object_names).

    manifest = {
      "version": 1, "colorSpace": "sRGB",
      "meshes": {piece: {"limb", "main", "material", "color", "parent"}},
      "limbs":  {limb: {"main": piece, "pieces": [piece, ...], "joint": [x, y, z]}},
    }
    "parent" is the Blender parent object of the piece after splitting (None at top level).
    "joint" is the limb origin (the pivot every piece shares) in Roblox axes and studs,
    relative to the Blender world origin, i.e. (x, z, -y).
    Non-mesh objects (armatures, empties) are passed through in final_object_names.
    """
    records, final = [], []
    for name in obj_names:
        obj = bpy.data.objects.get(name)
        if obj is None:
            continue
        if obj.type != 'MESH':
            final.append(name)
            continue
        recs = split_by_material(obj)
        records.extend(recs)
        final.extend(r["name"] for r in recs)

    manifest = {"version": 1, "colorSpace": "sRGB", "meshes": {}, "limbs": {}}
    for r in records:
        obj = bpy.data.objects[r["name"]]  # parent read now: earlier splits may have re-parented it
        manifest["meshes"][r["name"]] = {
            "limb": r["limb"], "main": r["main"], "material": r["material"],
            "color": r["color"], "parent": obj.parent.name if obj.parent else None,
        }
        t = obj.matrix_world.translation  # Blender Z-up -> Roblox Y-up, as the FBX export does
        joint = [round(t.x, 4) + 0.0, round(t.z, 4) + 0.0, round(-t.y, 4) + 0.0]  # no -0.0
        limb = manifest["limbs"].setdefault(r["limb"], {"main": None, "pieces": [], "joint": joint})
        limb["pieces"].append(r["name"])
        if r["main"]:
            limb["main"] = r["name"]
    for limb, info in manifest["limbs"].items():
        if info["main"] is None:  # e.g. the main piece was deleted by hand after a first split
            info["main"] = info["pieces"][0]
            manifest["meshes"][info["main"]]["main"] = True
    return manifest, final


def export_fbx(filepath, obj_names, with_animation=False, split_materials=True):
    """Export the named objects to a Roblox-ready FBX.

    split_materials=True (default): split multi-material meshes first (split_all_by_material,
    this changes the open scene), run the pre-export audit, refuse to export if any mesh still
    has more than one material, and write <fbx stem>_manifest.json next to the FBX.
    Returns {"fbx", "manifest" (path or None), "objects", "audit"}.
    """
    final_names = list(obj_names)
    manifest_path = None
    audit_text = ""
    if split_materials:
        manifest, final_names = split_all_by_material(obj_names)
        meshes = [n for n in final_names if bpy.data.objects[n].type == 'MESH']
        audit_text = audit(names=meshes, check_single_material=True)
        bad = [line for line in audit_text.splitlines() if "MULTIPLE MATERIALS" in line]
        if bad:
            raise RuntimeError("pre-export audit failed:\n" + "\n".join(bad))
        manifest["fbx"] = os.path.basename(filepath)
        manifest_path = manifest_path_for(filepath)
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

    bpy.ops.object.select_all(action='DESELECT')
    for name in final_names:
        if name in bpy.data.objects:
            bpy.data.objects[name].select_set(True)

    bpy.ops.export_scene.fbx(
        filepath=filepath,
        use_selection=True,
        apply_scale_options='FBX_SCALE_UNITS',  # "FBX Unit Scale"
        axis_forward='-Z',
        axis_up='Y',
        apply_unit_scale=True,
        use_mesh_modifiers=True,
        mesh_smooth_type='FACE',
        add_leaf_bones=False,
        bake_anim=with_animation,
        bake_anim_use_all_actions=False,
        bake_anim_use_nla_strips=False,
        path_mode='COPY',
        embed_textures=True,
    )
    return {"fbx": filepath, "manifest": manifest_path, "objects": final_names, "audit": audit_text}
