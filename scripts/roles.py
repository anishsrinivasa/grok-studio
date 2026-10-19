#!/usr/bin/env python3
"""
Role discovery and validation for grok-studio.
Discovers roles from manifests, validates them, and generates setup data.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
import argparse


def discover_roles(plugin_root: Path) -> List[Dict[str, Any]]:
    """Discover all roles from manifest files in roles/*/manifest.json"""
    roles_dir = plugin_root / "roles"
    if not roles_dir.exists():
        return []
    
    roles = []
    for role_dir in sorted(roles_dir.iterdir()):
        if not role_dir.is_dir():
            continue
        manifest_path = role_dir / "manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path) as f:
                    manifest = json.load(f)
                manifest["_manifestPath"] = str(manifest_path)
                manifest["_roleDir"] = str(role_dir)
                roles.append(manifest)
            except json.JSONDecodeError as e:
                print(f"Error parsing {manifest_path}: {e}", file=sys.stderr)
    
    return roles


def validate_manifest(manifest: Dict[str, Any], schema_path: Path) -> List[str]:
    """Validate a role manifest against the schema. Returns list of errors."""
    try:
        import jsonschema
        with open(schema_path) as f:
            schema = json.load(f)
        # Remove internal fields before validation
        clean_manifest = {k: v for k, v in manifest.items() if not k.startswith('_')}
        jsonschema.validate(clean_manifest, schema)
        return []
    except ImportError:
        return ["jsonschema not available, skipping validation"]
    except jsonschema.ValidationError as e:
        return [f"Validation error: {e.message}"]
    except Exception as e:
        return [f"Validation error: {str(e)}"]


def validate_role_files(role: Dict[str, Any]) -> List[str]:
    """Check that referenced files exist."""
    errors = []
    role_dir = Path(role["_roleDir"])
    
    # Check agent instructions
    agent_file = role_dir / role["agentInstructions"]["file"]
    if not agent_file.exists():
        errors.append(f"Missing agent instructions: {agent_file}")
    
    # Check skills
    plugin_root = role_dir.parent.parent
    for skill in role.get("skills", []):
        skill_path = plugin_root / skill["path"] / "SKILL.md"
        if not skill_path.exists():
            errors.append(f"Missing skill: {skill_path}")
    
    # Check example if present
    if "example" in role and "file" in role["example"]:
        example_file = role_dir / role["example"]["file"]
        if not example_file.exists():
            errors.append(f"Missing example: {example_file}")
    
    return errors


def check_spec_field_conflicts(roles: List[Dict[str, Any]]) -> List[str]:
    """Check for conflicting spec field ownership."""
    field_owners = {}
    conflicts = []
    
    for role in roles:
        role_id = role["role"]["id"]
        for field in role["ownership"]["specFields"]:
            if field in field_owners:
                conflicts.append(
                    f"Spec field '{field}' claimed by both {field_owners[field]} and {role_id}"
                )
            else:
                field_owners[field] = role_id
    
    return conflicts


def validate_all_roles(plugin_root: Path) -> int:
    """Validate all roles and return exit code."""
    roles = discover_roles(plugin_root)
    
    if not roles:
        print("No roles found", file=sys.stderr)
        return 1
    
    print(f"Found {len(roles)} roles")
    
    schema_path = plugin_root / "roles" / "role-manifest.schema.json"
    all_valid = True
    
    for role in roles:
        role_id = role["role"]["id"]
        print(f"\nValidating {role_id}...")
        
        # Validate against schema
        if schema_path.exists():
            schema_errors = validate_manifest(role, schema_path)
            if schema_errors:
                all_valid = False
                for error in schema_errors:
                    print(f"  ✗ {error}", file=sys.stderr)
            else:
                print(f"  ✓ Schema valid")
        
        # Validate files exist
        file_errors = validate_role_files(role)
        if file_errors:
            all_valid = False
            for error in file_errors:
                print(f"  ✗ {error}", file=sys.stderr)
        else:
            print(f"  ✓ All files exist")
    
    # Check for conflicts
    conflicts = check_spec_field_conflicts(roles)
    if conflicts:
        all_valid = False
        print("\nSpec field conflicts:", file=sys.stderr)
        for conflict in conflicts:
            print(f"  ✗ {conflict}", file=sys.stderr)
    
    if all_valid:
        print("\n✓ All roles valid")
        return 0
    else:
        print("\n✗ Validation failed", file=sys.stderr)
        return 1


def list_roles(plugin_root: Path, format: str = "table") -> None:
    """List all discovered roles."""
    roles = discover_roles(plugin_root)
    
    if format == "json":
        print(json.dumps([{
            "id": r["role"]["id"],
            "name": r["role"]["name"],
            "description": r["role"]["description"]
        } for r in roles], indent=2))
    else:
        print(f"{'ID':<12} {'Name':<20} {'Description'}")
        print("-" * 80)
        for role in roles:
            role_id = role["role"]["id"]
            name = role["role"]["name"]
            desc = role["role"]["description"]
            print(f"{role_id:<12} {name:<20} {desc[:45]}")


def generate_setup_questions(plugin_root: Path) -> None:
    """Generate setup questions from all role manifests."""
    roles = discover_roles(plugin_root)
    
    questions = []
    for role in roles:
        role_id = role["role"]["id"]
        for q in role.get("setupQuestions", []):
            q["role"] = role_id
            questions.append(q)
    
    print(json.dumps(questions, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Grok Studio role management")
    parser.add_argument("--plugin-root", type=Path, default=Path.cwd(),
                      help="Path to plugin root (default: current directory)")
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    subparsers.add_parser("validate", help="Validate all role manifests")
    
    list_parser = subparsers.add_parser("list", help="List all roles")
    list_parser.add_argument("--format", choices=["table", "json"], default="table")
    
    subparsers.add_parser("setup-questions", help="Generate setup questions from all roles")
    
    args = parser.parse_args()
    
    if args.command == "validate":
        sys.exit(validate_all_roles(args.plugin_root))
    elif args.command == "list":
        list_roles(args.plugin_root, args.format)
    elif args.command == "setup-questions":
        generate_setup_questions(args.plugin_root)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
