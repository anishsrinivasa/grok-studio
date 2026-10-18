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


def audit(budget_by_name=None, names=None, check_single_material=True, check_flat_materials=True):
    """Report triangles, size in studs, scale, n-gons and holes for every mesh. Use before export.
    
    budget_by_name: {object name: max triangles}; names: only audit these objects.
    check_single_material: fail if any mesh has more than one material (pre-export check).
    check_flat_materials: fail if any material is not flat (has textures or complex nodes).
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
        elif check_single_material and len(obj.data.materials) > 1:
            issues.append(f"MULTIPLE MATERIALS ({len(obj.data.materials)}); must split before export")
        
        # Check for flat materials (only Principled BSDF with base color, no textures)
        if check_flat_materials:
            for mat in obj.data.materials:
                if not mat or not mat.node_tree:
                    continue
                bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
                if bsdf:
                    # Check if Base Color input has a texture/node connected
                    base_input = bsdf.inputs["Base Color"]
                    if base_input.is_linked:
                        issues.append(f"material {mat.name} has texture/nodes (not flat color)")
                        break
        
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


def split_by_material(obj):
    """Split a mesh object into one object per material, named <Object>_<Material>.
    
    Returns [(new_obj_name, material_name, sRGB_hex)] for all pieces. The original object
    is removed. Origins are kept at the parent limb's joint (the original object's origin),
    so animation still works. Intended for export: call this right before export_fbx.
    """
    if obj.type != 'MESH' or len(obj.data.materials) <= 1:
        return [(obj.name, obj.data.materials[0].name if obj.data.materials else "Material", "#808080")]
    
    original_name = obj.name
    original_location = obj.location.copy()
    original_rotation = obj.rotation_euler.copy()
    original_scale = obj.scale.copy()
    original_parent = obj.parent
    original_parent_type = obj.parent_type
    
    pieces = []
    depsgraph = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(depsgraph)
    mesh = eval_obj.to_mesh()
    
    try:
        for mat_idx, material in enumerate(obj.data.materials):
            mat_name = material.name if material else f"Material{mat_idx}"
            # Extract RGB from material
            hex_color = "#808080"
            if material and material.node_tree:
                bsdf = next((n for n in material.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
                if bsdf:
                    base_color = bsdf.inputs["Base Color"].default_value
                    # linear to sRGB
                    srgb = tuple(
                        c * 12.92 if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055
                        for c in base_color[:3]
                    )
                    hex_color = "#{:02x}{:02x}{:02x}".format(
                        int(srgb[0] * 255), int(srgb[1] * 255), int(srgb[2] * 255)
                    )
            
            # Create a new mesh with only faces using this material
            new_mesh = bpy.data.meshes.new(f"{original_name}_{mat_name}")
            verts = [v.co.copy() for v in mesh.vertices]
            edges = []
            faces = []
            face_to_verts = {}
            
            for poly in mesh.polygons:
                if poly.material_index == mat_idx:
                    face_to_verts[poly.index] = list(poly.vertices)
                    faces.append(list(poly.vertices))
            
            if not faces:
                continue
            
            new_mesh.from_pydata(verts, edges, faces)
            new_mesh.update()
            new_mesh.materials.append(material)
            
            new_obj = bpy.data.objects.new(f"{original_name}_{mat_name}", new_mesh)
            new_obj.location = original_location
            new_obj.rotation_euler = original_rotation
            new_obj.scale = original_scale
            new_obj.parent = original_parent
            new_obj.parent_type = original_parent_type
            
            for coll in obj.users_collection:
                coll.objects.link(new_obj)
            
            pieces.append((new_obj.name, mat_name, hex_color))
    
    finally:
        eval_obj.to_mesh_clear()
    
    # Remove original object
    bpy.data.objects.remove(obj, do_unlink=True)
    
    return pieces


def split_all_by_material(obj_names):
    """Split all multi-material objects in obj_names, return manifest data.
    
    Returns {
        "meshes": {mesh_name: {"parentLimb": parent_name, "color": hex, "material": mat_name}},
        "split": [(original_name, [(piece_name, mat_name, hex)])]
    }
    Modifies the scene: multi-material objects are replaced by single-material pieces.
    """
    manifest = {"meshes": {}, "split": []}
    all_new_names = []
    
    for name in obj_names:
        if name not in bpy.data.objects:
            continue
        obj = bpy.data.objects[name]
        if obj.type != 'MESH':
            all_new_names.append(name)
            continue
        
        parent_name = obj.parent.name if obj.parent else obj.name
        pieces = split_by_material(obj)
        
        if len(pieces) > 1:
            manifest["split"].append((name, pieces))
        
        for piece_name, mat_name, hex_color in pieces:
            all_new_names.append(piece_name)
            manifest["meshes"][piece_name] = {
                "parentLimb": parent_name,
                "color": hex_color,
                "material": mat_name,
            }
    
    return manifest, all_new_names


def export_fbx(filepath, obj_names, with_animation=False, split_materials=True):
    """Export the named objects to a Roblox-ready FBX.
    
    If split_materials=True (default), multi-material meshes are split into one mesh per
    material, and a manifest JSON is written next to the FBX mapping each mesh to its color
    and parent limb. Returns {"fbx": path, "manifest": path or None, "split": bool}.
    """
    manifest_data = None
    final_names = list(obj_names)
    
    if split_materials:
        manifest_data, final_names = split_all_by_material(obj_names)
        manifest_path = filepath.rsplit(".", 1)[0] + "_manifest.json"
        import json
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)
    
    bpy.ops.object.select_all(action='DESELECT')
    for name in final_names:
        if name in bpy.data.objects:
            bpy.data.objects[name].select_set(True)
    
    bpy.ops.export_scene.fbx(
        filepath=filepath,
        use_selection=True,
        apply_scale_options='FBX_SCALE_UNITS',
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
    
    result = {"fbx": filepath, "manifest": manifest_path if split_materials else None, "split": split_materials}
    return result
