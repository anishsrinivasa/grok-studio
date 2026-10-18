# Split-by-Material Export Pipeline

## Overview

This implementation adds automatic splitting of multi-material Blender meshes before FBX export, solving the problem where Roblox Studio imports multi-material objects as single-colored MeshParts, losing detail.

## Problem Solved

**Before**: A lion model with Head (Fur, Cream, Nose, Eye materials) exported as one MeshPart with only one color. Bots then stacked ~20 box Parts to fake the missing details, which didn't align with geometry.

**After**: The Head is automatically split into Head_Fur, Head_Cream, Head_Nose, Head_Eye during export. Each piece keeps its origin at the parent limb's joint (for animation), and a manifest records colors and relationships. Studio applies the manifest to set correct colors and weld pieces together.

## Implementation

### Blender Side (Python)

**`roblox_export.py`** - Core export functions:
- `split_by_material(obj)` - Splits one mesh into pieces, one per material
- `split_all_by_material(obj_names)` - Splits all objects and generates manifest
- `export_fbx(filepath, obj_names, split_materials=True)` - Export with automatic splitting
- `audit(..., check_single_material=True, check_flat_materials=True)` - Pre-export validation

**`asset_harness.py`** - Updated to use new export:
- `export_asset(paths, split_materials=True)` - Returns manifest path

**Manifest format** (`exports/<id>_manifest.json`):
```json
{
  "meshes": {
    "Head_Fur": {"parentLimb": "Head", "color": "#8B6F47", "material": "Fur"},
    "Head_Eye": {"parentLimb": "Head", "color": "#FFFFFF", "material": "Eye"}
  },
  "split": [["Head", [["Head_Fur", "Fur", "#8B6F47"], ...]]]
}
```

### Studio Side (Luau)

**`studio/manifest_importer.lua`** - Post-import helper:
- `applyManifest(model, manifestData)` - Sets colors and welds pieces to limbs
- `validateImport(model, manifestData)` - Post-import check that verifies:
  - All manifest meshes exist
  - Colors are correct
  - Split pieces are welded to parent limbs
  - No non-hitbox overlay Parts were added

### Harnesses

1. **Pre-export (Python)**: `audit()` fails if:
   - Any mesh has more than one material
   - Any material has textures or complex nodes (not flat)
   - Triangle count exceeds limits

2. **Post-import (Luau)**: `validateImport()` fails if:
   - Manifest meshes are missing
   - Colors don't match
   - Split pieces aren't welded
   - Overlay Parts were added

3. **Visual check**: Skills instruct bots to compare Edit-mode `screen_capture` against the Blender render before marking the model placed.

## Usage

### For Bots (Cloud Mode)

```python
# In a job script
from asset_harness import *

a = open_asset("lion_head")
# ... model the head with multiple materials ...

# Audit before export - will fail if multi-material
print(audit(names=asset_object_names(a)))

# Export - splits automatically and creates manifest
result = export_asset(a)
print(f"Exported: {result['fbx']}")
print(f"Manifest: {result['manifest']}")
```

### In Studio (Builder)

```lua
-- After importing the FBX
local HttpService = game:GetService("HttpService")
local manifestJson = ... -- Read the manifest JSON file
local manifestData = HttpService:JSONDecode(manifestJson)

-- Paste manifest_importer.lua contents here or require it
local importer = ... -- the module

-- Apply colors and weld pieces
local result = importer.applyManifest(importedModel, manifestData)
if result.status ~= "OK" then
    warn("Apply failed:", result.errors)
end

-- Validate
local validation = importer.validateImport(importedModel, manifestData)
if validation.status == "PASS" then
    print("✓ Import validation PASSED")
else
    warn("✗ Import validation FAILED:", validation.errors)
end
```

## Testing

**Structure test** (no Blender required):
```bash
python3 skills/blender-assets/reference/test_split_logic.py
```

**Full smoke test** (requires Blender or bpy wheel):
```bash
# With cloud_blender.sh
bash skills/blender-assets/reference/cloud_blender.sh run \
  skills/blender-assets/reference/smoke_test_split.py

# Or with bpy wheel
python3 skills/blender-assets/reference/smoke_test_split.py
```

The smoke test:
1. Creates a test cube with 3 materials (Red, Green, Blue)
2. Verifies audit fails on unsplit object
3. Splits by material
4. Verifies audit passes on split objects
5. Exports with manifest
6. Re-imports FBX and confirms one material per mesh

## Skill Updates

**`skills/blender-assets/SKILL.md`**:
- Documents split-by-material as default pipeline
- Adds manifest application to "Placing" section
- Updates audit step to mention new checks
- Adds Edit-mode vs render comparison to review loop
- Notes that faking details with overlay Parts is never allowed

**`skills/roblox-building/SKILL.md`**:
- Documents manifest application when placing Blender models
- References the Luau helper and validation check

**`skills/roblox-animations/SKILL.md`**:
- No changes needed (doesn't mention overlay Parts)

## Files Changed

- `skills/blender-assets/reference/roblox_export.py` - Core splitting logic
- `skills/blender-assets/reference/asset_harness.py` - Updated export_asset
- `skills/blender-assets/reference/studio/manifest_importer.lua` - NEW: Studio helper
- `skills/blender-assets/reference/smoke_test_split.py` - NEW: Full smoke test
- `skills/blender-assets/reference/test_split_logic.py` - NEW: Structure test
- `skills/blender-assets/SKILL.md` - Documented new pipeline
- `skills/roblox-building/SKILL.md` - Documented manifest application

## Design Decisions

1. **Split by material, not by color**: More robust for painted models where multiple faces might share a color but different materials.

2. **Origins preserved**: Split pieces keep their origin at the parent limb's joint, so Motor6Ds and animations still work without adjustment.

3. **Manifest records relationships**: The JSON manifest makes it easy for Studio code to reconstruct the hierarchy without parsing names or guessing.

4. **Audit enforces before export**: Multi-material meshes are caught by audit before export, giving bots clear feedback on what to fix.

5. **Post-import validation in Luau**: Studio can verify the import was successful without round-tripping to Python.

6. **Default behavior**: `split_materials=True` is the default in `export_fbx` and `export_asset`, so bots get the correct behavior without explicit flags.

## Migration

Existing code continues to work:
- `export_fbx(path, names)` still works (split_materials defaults to True)
- `audit(names=names)` still works (new checks default to True)
- Old FBX exports without manifests can still be imported (manifest is optional)

New behavior:
- Multi-material objects are automatically split during export
- Audit fails on multi-material meshes (fixable by splitting or reducing to one material)
- Audit warns about textured materials (fixable by using flat_material)
