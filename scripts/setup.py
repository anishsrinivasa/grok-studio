#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml", "jsonschema"]
# ///
"""
Setup resolver: loads definitions + manifests, takes detection results and answers,
outputs per-role capability resolution, spec patch, and filled welcome message.
"""

import json
import sys
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional
import argparse
from datetime import datetime


def load_setup_definitions(plugin_root: Path) -> Dict[str, Any]:
    """Load setup/steps.yaml"""
    steps_path = plugin_root / "setup" / "steps.yaml"
    with open(steps_path) as f:
        return yaml.safe_load(f)


def load_role_manifests(plugin_root: Path) -> List[Dict[str, Any]]:
    """Load all role manifests from roles/*/manifest.json"""
    roles_dir = plugin_root / "roles"
    manifests = []
    for role_dir in sorted(roles_dir.iterdir()):
        if not role_dir.is_dir():
            continue
        manifest_path = role_dir / "manifest.json"
        if manifest_path.exists():
            with open(manifest_path) as f:
                manifest = json.load(f)
                manifest["_roleDir"] = str(role_dir)
                manifests.append(manifest)
    return manifests


def resolve_capability(
    role: Dict[str, Any],
    capability_id: str,
    detection_results: Dict[str, Any],
    answers: Dict[str, Any]
) -> Dict[str, Any]:
    """Resolve one capability for a role. Returns {status, value, reason}."""
    
    # Find capability in role manifest
    capability = None
    for cap in role.get("capabilities", {}).get("required", []):
        if cap["id"] == capability_id:
            capability = cap
            break
    if not capability:
        for cap in role.get("capabilities", {}).get("optional", []):
            if cap["id"] == capability_id:
                capability = cap
                break
    
    if not capability:
        return {"status": "unknown", "value": None, "reason": "capability not found"}
    
    # Check each option's requirements
    for option in capability.get("options", []):
        requirements = option.get("requirements", {})
        
        # Check connectors (map connector name to detection key)
        connectors_met = True
        for connector in requirements.get("connectors", []):
            # Map connector name to detection key
            if connector == "roblox-studio":
                check_key = "studio_running"
            elif connector == "figma":
                check_key = "figma_connector"
            elif connector == "blender":
                check_key = "cloud_blender"
            else:
                check_key = f"{connector}_connector"
            
            if detection_results.get(check_key) != "ok":
                connectors_met = False
                break
        
        # Check secrets
        secrets_met = True
        missing_secrets = []
        for secret in requirements.get("secrets", []):
            # Check both exact match and env var pattern
            secret_key = secret if secret in detection_results else secret.lower().replace("_", "")
            if detection_results.get(secret) != "present" and detection_results.get(secret_key) != "present":
                secrets_met = False
                missing_secrets.append(secret)
        
        # Check custom checks (these are simplified - just check if they pass)
        checks_met = True
        for check in requirements.get("checks", []):
            # Simplified: assume checks pass if related connector/service is ok
            check_name = check.replace(".py", "").replace("_", "")
            check_ok = False
            for key, value in detection_results.items():
                if check_name in key.lower() and value in ["ok", "up", "pass", "present"]:
                    check_ok = True
                    break
            if not check_ok:
                checks_met = False
                break
        
        if connectors_met and secrets_met and checks_met:
            return {
                "status": "enabled",
                "value": option["value"],
                "label": option["label"],
                "reason": None
            }
        elif option.get("isFallback"):
            reasons = []
            if not connectors_met:
                reasons.append("connector not available")
            if not secrets_met:
                reasons.append(f"missing: {', '.join(missing_secrets)}")
            return {
                "status": "fallback",
                "value": option["value"],
                "label": option["label"],
                "reason": "; ".join(reasons) if reasons else "using fallback"
            }
    
    # No option met requirements
    return {
        "status": "disabled",
        "value": None,
        "reason": "requirements not met"
    }


def resolve_role_capabilities(
    role: Dict[str, Any],
    detection_results: Dict[str, Any],
    answers: Dict[str, Any]
) -> Dict[str, Any]:
    """Resolve all capabilities for one role."""
    
    role_id = role["role"]["id"]
    capabilities = {}
    
    # Resolve required capabilities
    for cap in role.get("capabilities", {}).get("required", []):
        cap_id = cap["id"]
        # Check if user answered a question about this
        answer_key = f"{role_id}_{cap_id}"
        if answer_key in answers:
            # User chose explicitly
            capabilities[cap_id] = {
                "status": "enabled",
                "value": answers[answer_key],
                "reason": "user choice"
            }
        else:
            # Auto-resolve
            capabilities[cap_id] = resolve_capability(
                role, cap_id, detection_results, answers
            )
    
    # Resolve optional capabilities
    for cap in role.get("capabilities", {}).get("optional", []):
        cap_id = cap["id"]
        resolution = resolve_capability(role, cap_id, detection_results, answers)
        if resolution["status"] == "enabled":
            capabilities[cap_id] = resolution
        else:
            capabilities[cap_id] = {
                "status": "skipped",
                "value": None,
                "reason": resolution.get("reason", "optional capability not available")
            }
    
    # Determine overall role status
    all_required_met = all(
        capabilities.get(cap["id"], {}).get("status") in ["enabled", "fallback"]
        for cap in role.get("capabilities", {}).get("required", [])
    )
    
    role_status = "active" if all_required_met else "disabled"
    
    return {
        "roleId": role_id,
        "status": role_status,
        "capabilities": capabilities
    }


def generate_spec_patch(
    resolution: List[Dict[str, Any]],
    detection_results: Dict[str, Any],
    answers: Dict[str, Any]
) -> Dict[str, Any]:
    """Generate the patch to apply to game-spec.json"""
    
    patch = {
        "build": {
            "connectors": {},
            "approvals": {}
        }
    }
    
    # Connectors
    patch["build"]["connectors"]["studio"] = detection_results.get("studio_running") == "ok"
    patch["build"]["connectors"]["blender"] = detection_results.get("cloud_blender") == "ok"
    patch["build"]["connectors"]["figma"] = detection_results.get("figma_connector") == "ok"
    
    # Approvals
    patch["build"]["approvals"]["uploadModels"] = answers.get("upload_models", False)
    patch["build"]["approvals"]["publishAnimations"] = answers.get("publish_animations", False)
    patch["build"]["approvals"]["approvedAt"] = datetime.utcnow().isoformat() + "Z"
    
    return patch


def fill_welcome_template(
    template_path: Path,
    roles: List[Dict[str, Any]],
    resolution: List[Dict[str, Any]],
    detection_results: Dict[str, Any]
) -> str:
    """Fill welcome template with role and setup data."""
    
    with open(template_path) as f:
        template = f.read()
    
    # Prepare active and disabled roles
    active_roles = []
    disabled_roles = []
    
    for role_manifest in roles:
        role_id = role_manifest["role"]["id"]
        role_resolution = next((r for r in resolution if r["roleId"] == role_id), None)
        
        if not role_resolution:
            continue
        
        # Build integration string
        integrations = []
        for cap_id, cap_res in role_resolution.get("capabilities", {}).items():
            if cap_res["status"] in ["enabled", "fallback"]:
                integrations.append(cap_res.get("label", cap_res.get("value", "unknown")))
        
        role_data = {
            "name": role_manifest["role"]["name"],
            "description": role_manifest["role"]["description"],
            "keyCapabilities": role_manifest["display"]["keyCapabilities"],
            "integration": ", ".join(integrations) if integrations else "default"
        }
        
        if role_resolution["status"] == "active":
            active_roles.append(role_data)
        else:
            # Collect unmet requirements
            requirements = []
            for cap_id, cap_res in role_resolution.get("capabilities", {}).items():
                if cap_res["status"] == "disabled":
                    requirements.append(cap_res.get("reason", "unknown"))
            role_data["requirements"] = "; ".join(requirements) if requirements else "unknown"
            disabled_roles.append(role_data)
    
    # Build active roles section
    active_section = ""
    for role in active_roles:
        active_section += f"## {role['name']}\n"
        active_section += f"*{role['description']}*\n\n"
        active_section += f"**What {role['name']} can do:**\n"
        for cap in role['keyCapabilities']:
            active_section += f"- {cap}\n"
        active_section += f"\n**Using:** {role['integration']}\n\n---\n\n"
    
    # Build disabled roles section
    disabled_section = ""
    if disabled_roles:
        disabled_section += "\n**Disabled roles:**\n"
        for role in disabled_roles:
            disabled_section += f"- **{role['name']}**: {role['requirements']}\n"
        disabled_section += "\n"
    
    # Setup summary values
    studio_connection = "bridge" if detection_results.get("bridge_health") == "up" else "direct"
    place_info = detection_results.get("place_name", "unknown")
    blender_path = "cloud" if detection_results.get("cloud_blender") == "ok" else "unavailable"
    
    # Replace placeholders
    result = template.replace(
        "(Active roles will be inserted here by the setup resolver)",
        active_section.rstrip() + disabled_section
    )
    result = result.replace("{{studioConnection}}", studio_connection)
    result = result.replace("{{placeInfo}}", place_info)
    result = result.replace("{{blenderPath}}", blender_path)
    
    return result


def main():
    parser = argparse.ArgumentParser(description="Grok Studio setup resolver")
    parser.add_argument("--plugin-root", type=Path, default=Path.cwd(),
                      help="Path to plugin root")
    parser.add_argument("--detection-results", type=Path,
                      help="JSON file with detection results")
    parser.add_argument("--answers", type=Path,
                      help="JSON file with user answers")
    parser.add_argument("--output", type=Path,
                      help="Output JSON file")
    parser.add_argument("--welcome-output", type=Path,
                      help="Output file for welcome message")
    parser.add_argument("--self-check", action="store_true",
                      help="Run self-check with test data")
    
    args = parser.parse_args()
    
    if args.self_check:
        # Self-check mode: generate test data
        print("Running self-check...")
        test_detection = {
            "studio_running": "ok",
            "bridge_health": "up",
            "cloud_blender": "ok",
            "figma_connector": "error",
            "open_cloud_key": "present",
            "GROK_STUDIO_BRIDGE_KEY": "present",
            "place_name": "TestPlace"
        }
        test_answers = {
            "upload_models": True,
            "publish_animations": True,
            "designer_ui_design_path": "studio-direct",
            "marketing_x_posting": "drafts_only",
            "animator_animation_planning": "decide_for_me"
        }
        
        detection_path = Path("/tmp/test_detection.json")
        answers_path = Path("/tmp/test_answers.json")
        output_path = Path("/tmp/test_output.json")
        
        with open(detection_path, "w") as f:
            json.dump(test_detection, f, indent=2)
        with open(answers_path, "w") as f:
            json.dump(test_answers, f, indent=2)
        
        args.detection_results = detection_path
        args.answers = answers_path
        args.output = output_path
        args.welcome_output = Path("/tmp/test_welcome.md")
    elif not args.detection_results or not args.answers or not args.output:
        parser.error("--detection-results, --answers, and --output are required (or use --self-check)")
    
    # Load inputs
    with open(args.detection_results) as f:
        detection_results = json.load(f)
    
    with open(args.answers) as f:
        answers = json.load(f)
    
    # Load definitions and manifests
    setup_defs = load_setup_definitions(args.plugin_root)
    roles = load_role_manifests(args.plugin_root)
    
    # Resolve capabilities for each role
    resolution = []
    for role in roles:
        role_resolution = resolve_role_capabilities(role, detection_results, answers)
        resolution.append(role_resolution)
    
    # Generate spec patch
    spec_patch = generate_spec_patch(resolution, detection_results, answers)
    
    # Generate welcome message
    welcome_template_path = args.plugin_root / "setup" / "welcome-template.md"
    welcome_message = fill_welcome_template(
        welcome_template_path, roles, resolution, detection_results
    )
    
    # Output
    output = {
        "resolution": resolution,
        "specPatch": spec_patch,
        "welcomeMessage": welcome_message
    }
    
    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)
    
    if args.welcome_output:
        with open(args.welcome_output, "w") as f:
            f.write(welcome_message)
    
    if args.self_check:
        print(f"✓ Self-check passed")
        print(f"  Output: {args.output}")
        print(f"  Welcome: {args.welcome_output}")
        print(f"\nResolution summary:")
        for r in resolution:
            print(f"  {r['roleId']}: {r['status']}")
        sys.exit(0)
    
    print(f"✓ Setup resolution complete")
    print(f"  Output: {args.output}")
    if args.welcome_output:
        print(f"  Welcome: {args.welcome_output}")


if __name__ == "__main__":
    main()
