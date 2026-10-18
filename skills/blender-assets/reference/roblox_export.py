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
import bpy
import bmesh

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


def audit(budget_by_name=None, names=None):
    """Report triangles, size in studs, scale, n-gons and holes for every mesh. Use before export.

    budget_by_name: {object name: max triangles}; names: only audit these objects.
    Returns text; every line ends in OK or lists the issues. Lines with issues must be fixed
    (or the issue accepted on purpose) before export.
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
        issues = []
        if tris > ROBLOX_TRI_LIMIT:
            issues.append(f"OVER ROBLOX LIMIT ({tris} > {ROBLOX_TRI_LIMIT})")
        elif tris > budget:
            issues.append(f"over budget ({tris} > {budget})")
        if any(abs(s - 1.0) > 1e-4 for s in obj.scale):
            issues.append(f"unapplied scale {tuple(round(s, 3) for s in obj.scale)}")
        if ngons:
            issues.append(f"{ngons} n-gons (triangulate or quad)")
        if holes:
            issues.append(f"{holes} non-manifold edges (not watertight)")
        if not obj.data.materials:
            issues.append("no material")
        dims = tuple(round(d, 2) for d in obj.dimensions)
        report.append(f"{obj.name}: {tris} tris, dims(studs)={dims} " + ("; ".join(issues) or "OK"))
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
    h = hex_color.lstrip('#')
    rgb = tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    # sRGB -> linear for the BSDF base color
    lin = tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb)
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


def export_fbx(filepath, obj_names, with_animation=False):
    """Export the named objects to a Roblox-ready FBX."""
    bpy.ops.object.select_all(action='DESELECT')
    for name in obj_names:
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
    return f"exported {obj_names} -> {filepath}"
