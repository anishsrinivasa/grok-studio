#!/usr/bin/env python3
"""Validate game-spec DONE claims: every declared asset at 'placed' status must have
machine-checkable gate records (import results, asset IDs, etc.).

Usage: python3 scripts/validate-spec-gates.py <game-slug>

Checks:
- Assets (items[]) at status 'placed' must have import gate records in
  reports/<id>_import.json (for Blender/generated meshes).
- Animations at status 'published' must have assetId fields.
- VFX at status 'verified' must have corresponding assets or configs.
"""
import argparse
import json
import pathlib
import sys

def validate_asset_gates(spec, game_dir):
    """Check that every 'placed' asset has gate records."""
    errors = []
    warnings = []
    
    assets = spec.get("assets", {}).get("items", [])
    reports_dir = game_dir / "reports"
    
    for asset in assets:
        asset_id = asset.get("id", "")
        status = asset.get("status", "")
        source = asset.get("source", "")
        
        if status == "placed":
            # Assets from Creator Store don't need gate records (manual insert)
            if source == "creator-store":
                if not asset.get("assetId"):
                    warnings.append(
                        f"Asset '{asset_id}' is 'placed' from creator-store but missing assetId"
                    )
                continue
            
            # Blender/generate_mesh/generate_procedural_model need import gate records
            import_record = reports_dir / f"{asset_id}_import.json"
            if not import_record.exists():
                errors.append(
                    f"Asset '{asset_id}' status='placed' but no gate record at "
                    f"{import_record.relative_to(game_dir)}"
                )
            else:
                # Verify the gate record has required fields
                try:
                    gate_data = json.loads(import_record.read_text())
                    if not gate_data.get("audit", {}).get("pass"):
                        warnings.append(
                            f"Asset '{asset_id}' gate record exists but audit did not pass"
                        )
                    if not gate_data.get("postImportCheck", {}).get("pass"):
                        warnings.append(
                            f"Asset '{asset_id}' gate record exists but postImportCheck did not pass"
                        )
                except (json.JSONDecodeError, OSError) as e:
                    errors.append(f"Asset '{asset_id}' gate record is invalid: {e}")
    
    return errors, warnings


def validate_animation_gates(spec):
    """Check that every 'published' animation has an assetId."""
    errors = []
    
    animations = spec.get("animations", [])
    for anim in animations:
        anim_id = anim.get("id", "")
        status = anim.get("status", "")
        
        if status in ("published", "wired"):
            if not anim.get("assetId"):
                errors.append(
                    f"Animation '{anim_id}' status='{status}' but missing assetId field"
                )
    
    return errors


def validate_vfx_gates(spec):
    """Check that VFX effects reference existing assets or configs."""
    errors = []
    
    vfx = spec.get("vfx", [])
    for effect in vfx:
        effect_id = effect.get("id", "")
        status = effect.get("status", "")
        
        if status == "verified":
            # VFX should reference texture asset IDs or particle configs
            if not effect.get("config") and not effect.get("textureAssetId"):
                errors.append(
                    f"VFX '{effect_id}' status='verified' but missing config or textureAssetId"
                )
    
    return errors


def main():
    parser = argparse.ArgumentParser(description="Validate game-spec gate records")
    parser.add_argument("slug", help="Game slug (directory name under games/)")
    args = parser.parse_args()
    
    workspace = pathlib.Path(__file__).resolve().parent.parent
    game_dir = workspace / "games" / args.slug
    spec_path = game_dir / "game-spec.json"
    
    if not spec_path.exists():
        print(f"Error: {spec_path} not found", file=sys.stderr)
        return 1
    
    try:
        spec = json.loads(spec_path.read_text())
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON in {spec_path}: {e}", file=sys.stderr)
        return 1
    
    all_errors = []
    all_warnings = []
    
    # Run checks
    asset_errors, asset_warnings = validate_asset_gates(spec, game_dir)
    all_errors.extend(asset_errors)
    all_warnings.extend(asset_warnings)
    
    anim_errors = validate_animation_gates(spec)
    all_errors.extend(anim_errors)
    
    vfx_errors = validate_vfx_gates(spec)
    all_errors.extend(vfx_errors)
    
    # Report
    if all_warnings:
        print("⚠️  Warnings:")
        for w in all_warnings:
            print(f"  - {w}")
        print()
    
    if all_errors:
        print("✗ Gate validation FAILED:")
        for e in all_errors:
            print(f"  - {e}")
        print()
        print("Fix: Every specialist DONE at a terminal status (placed, published, verified)")
        print("     must be backed by machine-checkable artifacts:")
        print("       - Assets 'placed': import gate record in reports/<id>_import.json")
        print("       - Animations 'published': assetId field populated")
        print("       - VFX 'verified': config or textureAssetId present")
        return 1
    
    print("✓ All gate checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
