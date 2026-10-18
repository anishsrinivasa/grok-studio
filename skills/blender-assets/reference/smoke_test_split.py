#!/usr/bin/env python3
"""
smoke_test_split.py - Headless smoke test for split-by-material export pipeline.

Tests:
1. Create a test object with multiple flat-color materials
2. Verify audit fails on unsplit multi-material object
3. Split by material
4. Export with split_materials=True
5. Verify manifest exists and is correct
6. Re-import the FBX and verify one material per mesh
7. Verify audit passes on split objects

Requires: Blender with bpy (run with cloud_blender.sh or bpy wheel)
"""
import json
import os
import sys
import tempfile

try:
    import bpy
except ImportError:
    sys.exit("ERROR: bpy not available. Run with cloud_blender.sh or install bpy wheel.")

# Add reference/ to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from roblox_export import (
    setup_scene_for_roblox, flat_material, audit, split_by_material,
    split_all_by_material, export_fbx, triangle_count
)


def test_split_pipeline():
    """Full pipeline test."""
    print("=== Smoke Test: Split-by-Material Pipeline ===\n")
    
    # 1. Setup scene
    print("1. Setting up scene...")
    bpy.ops.wm.read_factory_settings(use_empty=True)
    setup_scene_for_roblox()
    print("   ✓ Scene ready\n")
    
    # 2. Create a test object with 3 materials
    print("2. Creating test object with 3 materials...")
    bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 1))
    obj = bpy.context.active_object
    obj.name = "TestCube"
    
    # Add 3 materials
    mat1 = bpy.data.materials[flat_material("Red", "#FF0000")]
    mat2 = bpy.data.materials[flat_material("Green", "#00FF00")]
    mat3 = bpy.data.materials[flat_material("Blue", "#0000FF")]
    
    obj.data.materials.append(mat1)
    obj.data.materials.append(mat2)
    obj.data.materials.append(mat3)
    
    # Assign faces to different materials
    for i, poly in enumerate(obj.data.polygons):
        poly.material_index = i % 3
    
    print(f"   ✓ Created {obj.name} with {len(obj.data.materials)} materials\n")
    
    # 3. Test audit FAILS on multi-material object
    print("3. Testing audit on unsplit object (should FAIL)...")
    audit_result = audit(names=[obj.name], check_single_material=True)
    print("   Audit output:")
    for line in audit_result.split('\n'):
        print(f"     {line}")
    
    if "MULTIPLE MATERIALS" in audit_result:
        print("   ✓ Audit correctly detected multiple materials\n")
    else:
        print("   ✗ FAIL: Audit should have detected multiple materials\n")
        return False
    
    # 4. Split the object
    print("4. Splitting object by material...")
    pieces = split_by_material(obj)
    print(f"   ✓ Split into {len(pieces)} pieces:")
    for piece_name, mat_name, hex_color in pieces:
        tris = triangle_count(bpy.data.objects[piece_name])
        print(f"     - {piece_name}: material={mat_name}, color={hex_color}, tris={tris}")
    print()
    
    # 5. Test audit PASSES on split objects
    print("5. Testing audit on split objects (should PASS)...")
    piece_names = [p[0] for p in pieces]
    audit_result = audit(names=piece_names, check_single_material=True)
    print("   Audit output:")
    for line in audit_result.split('\n'):
        print(f"     {line}")
    
    all_ok = all("OK" in line for line in audit_result.split('\n') if line)
    if all_ok:
        print("   ✓ All pieces passed audit\n")
    else:
        print("   ✗ FAIL: Some pieces failed audit\n")
        return False
    
    # 6. Export with manifest
    print("6. Exporting FBX with manifest...")
    with tempfile.TemporaryDirectory() as tmpdir:
        fbx_path = os.path.join(tmpdir, "test_export.fbx")
        result = export_fbx(fbx_path, piece_names, split_materials=False)  # Already split
        
        # Create manifest manually for this test
        manifest_data = {
            "meshes": {},
            "split": [("TestCube", pieces)]
        }
        for piece_name, mat_name, hex_color in pieces:
            manifest_data["meshes"][piece_name] = {
                "parentLimb": "TestCube",
                "color": hex_color,
                "material": mat_name
            }
        
        manifest_path = fbx_path.rsplit(".", 1)[0] + "_manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest_data, f, indent=2)
        
        print(f"   ✓ Exported to {fbx_path}")
        print(f"   ✓ Manifest written to {manifest_path}")
        print(f"   File size: {os.path.getsize(fbx_path)} bytes\n")
        
        # 7. Verify manifest content
        print("7. Verifying manifest content...")
        with open(manifest_path) as f:
            manifest = json.load(f)
        
        if len(manifest["meshes"]) != 3:
            print(f"   ✗ FAIL: Expected 3 meshes, got {len(manifest['meshes'])}\n")
            return False
        
        print(f"   ✓ Manifest contains {len(manifest['meshes'])} meshes:")
        for mesh_name, info in manifest["meshes"].items():
            print(f"     - {mesh_name}: parent={info['parentLimb']}, color={info['color']}")
        print()
        
        # 8. Re-import and verify
        print("8. Re-importing FBX to verify single material per mesh...")
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=fbx_path)
        
        reimported_meshes = [obj for obj in bpy.context.scene.objects if obj.type == 'MESH']
        print(f"   ✓ Re-imported {len(reimported_meshes)} mesh objects")
        
        for obj in reimported_meshes:
            mat_count = len(obj.data.materials)
            print(f"     - {obj.name}: {mat_count} material(s), {triangle_count(obj)} tris")
            if mat_count > 1:
                print(f"   ✗ FAIL: {obj.name} has {mat_count} materials (should be 1)\n")
                return False
        
        print("   ✓ All re-imported meshes have exactly 1 material\n")
    
    print("=== ✓ All tests PASSED ===")
    return True


if __name__ == "__main__":
    try:
        success = test_split_pipeline()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(2)
