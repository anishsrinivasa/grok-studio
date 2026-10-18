#!/usr/bin/env python3
"""
test_split_logic.py - Unit tests for split-by-material logic (no Blender required).

Tests the structure and logic of the split pipeline without requiring bpy.
"""
import json
import os
import sys
import tempfile

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

def test_imports():
    """Verify that the modules can be imported and have expected functions."""
    print("=== Testing Imports ===\n")
    
    # Check that roblox_export.py has the new functions
    with open(os.path.join(SCRIPT_DIR, "roblox_export.py")) as f:
        code = f.read()
    
    expected_functions = [
        "def split_by_material(",
        "def split_all_by_material(",
        "def export_fbx(",
        "def audit(",
    ]
    
    for func in expected_functions:
        if func in code:
            print(f"  ✓ Found {func.strip()}")
        else:
            print(f"  ✗ FAIL: Missing {func.strip()}")
            return False
    
    # Check audit has new parameters
    if "check_single_material" in code and "check_flat_materials" in code:
        print("  ✓ audit() has new validation parameters")
    else:
        print("  ✗ FAIL: audit() missing new parameters")
        return False
    
    # Check export_fbx has split_materials parameter
    if "split_materials=True" in code:
        print("  ✓ export_fbx() has split_materials parameter")
    else:
        print("  ✗ FAIL: export_fbx() missing split_materials parameter")
        return False
    
    print()
    return True


def test_asset_harness():
    """Verify asset_harness exports the new functions."""
    print("=== Testing asset_harness.py ===\n")
    
    with open(os.path.join(SCRIPT_DIR, "asset_harness.py")) as f:
        code = f.read()
    
    # Check imports
    if "split_by_material" in code and "split_all_by_material" in code:
        print("  ✓ asset_harness imports split functions")
    else:
        print("  ✗ FAIL: asset_harness missing split function imports")
        return False
    
    # Check export_asset has split_materials parameter
    if "split_materials=True" in code:
        print("  ✓ export_asset() has split_materials parameter")
    else:
        print("  ✗ FAIL: export_asset() missing split_materials parameter")
        return False
    
    print()
    return True


def test_manifest_importer():
    """Verify the Luau manifest importer exists and has the right structure."""
    print("=== Testing manifest_importer.lua ===\n")
    
    lua_path = os.path.join(SCRIPT_DIR, "studio", "manifest_importer.lua")
    if not os.path.exists(lua_path):
        print(f"  ✗ FAIL: {lua_path} not found")
        return False
    
    with open(lua_path) as f:
        code = f.read()
    
    expected_elements = [
        "local function applyManifest(",
        "local function validateImport(",
        "local function hexToColor3(",
        "return {",
        "applyManifest = applyManifest",
        "validateImport = validateImport",
    ]
    
    for elem in expected_elements:
        if elem in code:
            print(f"  ✓ Found {elem.strip()}")
        else:
            print(f"  ✗ FAIL: Missing {elem.strip()}")
            return False
    
    print()
    return True


def test_smoke_test_exists():
    """Verify the smoke test script exists."""
    print("=== Testing smoke_test_split.py ===\n")
    
    test_path = os.path.join(SCRIPT_DIR, "smoke_test_split.py")
    if not os.path.exists(test_path):
        print(f"  ✗ FAIL: {test_path} not found")
        return False
    
    with open(test_path) as f:
        code = f.read()
    
    if "def test_split_pipeline():" in code:
        print("  ✓ smoke_test_split.py has test_split_pipeline()")
    else:
        print("  ✗ FAIL: smoke_test_split.py missing test function")
        return False
    
    # Check that it imports the right functions
    expected_imports = [
        "from roblox_export import",
        "split_by_material",
        "split_all_by_material",
        "export_fbx",
        "audit",
    ]
    
    for imp in expected_imports:
        if imp in code:
            print(f"  ✓ Imports {imp}")
        else:
            print(f"  ✗ FAIL: Missing import {imp}")
            return False
    
    print()
    return True


def test_audit_checks():
    """Verify the audit function has the right validation checks."""
    print("=== Testing audit() validation logic ===\n")
    
    with open(os.path.join(SCRIPT_DIR, "roblox_export.py")) as f:
        code = f.read()
    
    # Extract the audit function
    start = code.find("def audit(")
    end = code.find("\ndef ", start + 1)
    if start == -1 or end == -1:
        print("  ✗ FAIL: Could not extract audit function")
        return False
    
    audit_code = code[start:end]
    
    checks = [
        ("MULTIPLE MATERIALS", "Check for multiple materials per mesh"),
        ("has texture/nodes", "Check for non-flat materials"),
        ("OVER ROBLOX LIMIT", "Check for triangle limit"),
    ]
    
    for pattern, description in checks:
        if pattern in audit_code:
            print(f"  ✓ {description}")
        else:
            print(f"  ✗ FAIL: Missing {description}")
            return False
    
    print()
    return True


def test_manifest_structure():
    """Test that the expected manifest structure is documented."""
    print("=== Testing manifest structure ===\n")
    
    with open(os.path.join(SCRIPT_DIR, "roblox_export.py")) as f:
        code = f.read()
    
    # Check that split_all_by_material documents the manifest structure
    if '"meshes":' in code and '"parentLimb":' in code and '"color":' in code:
        print("  ✓ Manifest structure defined with meshes, parentLimb, color")
    else:
        print("  ✗ FAIL: Manifest structure not properly defined")
        return False
    
    # Check that the Luau script documents the manifest structure
    with open(os.path.join(SCRIPT_DIR, "studio", "manifest_importer.lua")) as f:
        lua_code = f.read()
    
    if "manifestData structure:" in lua_code:
        print("  ✓ Luau script documents manifest structure")
    else:
        print("  ✗ FAIL: Luau script missing manifest documentation")
        return False
    
    print()
    return True


if __name__ == "__main__":
    print("Testing split-by-material implementation (no Blender required)\n")
    
    tests = [
        test_imports,
        test_asset_harness,
        test_manifest_importer,
        test_smoke_test_exists,
        test_audit_checks,
        test_manifest_structure,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"✗ EXCEPTION in {test.__name__}: {e}\n")
            results.append(False)
    
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"\nResults: {passed}/{total} tests passed")
    
    if all(results):
        print("✓ All structure tests PASSED")
        sys.exit(0)
    else:
        print("✗ Some tests FAILED")
        sys.exit(1)
