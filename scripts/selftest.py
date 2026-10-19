#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["pyyaml", "jsonschema"]
# ///
"""
Headless selftest for grok-studio setup flow.
Simulates full setup with fixtures (has-Figma, no-Figma scenarios).
Prints welcome message and validates all components.

Usage:
    python3 scripts/selftest.py                 # Both scenarios
    python3 scripts/selftest.py --scenario has-figma
    python3 scripts/selftest.py --scenario no-figma
"""
import argparse
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent

def run_command(cmd, cwd=None):
    """Run a command and return exit code and output."""
    result = subprocess.run(
        cmd, shell=True, cwd=cwd or ROOT, capture_output=True, text=True
    )
    return result.returncode, result.stdout, result.stderr

def test_role_validation():
    """Test 1: Role validation."""
    print("\n=== Test 1: Role Validation ===")
    code, out, err = run_command("python3 scripts/roles.py validate")
    if code != 0:
        print(f"✗ Role validation failed:\n{err}")
        return False
    if "✓" in out and "8 roles" not in out:
        # Count roles
        role_count = out.count("Validating ")
        if role_count != 8:
            print(f"✗ Expected 8 roles, got {role_count}")
            return False
    print("✓ All 8 roles valid")
    return True

def test_setup_resolver(scenario_name, detection_fixture, answers_fixture):
    """Test 2: Setup resolver with fixtures."""
    print(f"\n=== Test 2: Setup Resolver ({scenario_name}) ===")
    
    # Write fixtures to temp files
    detection_file = ROOT / f"/tmp/test_detection_{scenario_name}.json"
    answers_file = ROOT / f"/tmp/test_answers_{scenario_name}.json"
    output_file = ROOT / f"/tmp/test_output_{scenario_name}.json"
    welcome_file = ROOT / f"/tmp/test_welcome_{scenario_name}.md"
    
    detection_file.write_text(json.dumps(detection_fixture, indent=2))
    answers_file.write_text(json.dumps(answers_fixture, indent=2))
    
    # Run resolver
    cmd = f"python3 scripts/setup.py --detection-results {detection_file} --answers {answers_file} --output {output_file} --welcome-output {welcome_file}"
    code, out, err = run_command(cmd)
    
    if code != 0:
        print(f"✗ Setup resolver failed ({scenario_name}):\n{err}")
        return False, None
    
    # Read welcome message
    if not welcome_file.exists():
        print(f"✗ Welcome message not generated ({scenario_name})")
        return False, None
        
    welcome_text = welcome_file.read_text()
    
    # Read output resolution
    if not output_file.exists():
        print(f"✗ Resolution output not generated ({scenario_name})")
        return False, None
    
    resolution = json.loads(output_file.read_text())
    
    print(f"✓ Setup resolver completed ({scenario_name})")
    return True, (welcome_text, resolution)

def test_spec_validation():
    """Test 3: Example spec validation."""
    print("\n=== Test 3: Example Spec Validation ===")
    code, out, err = run_command(
        'python3 -c "import json,jsonschema; jsonschema.validate(json.load(open(\'skills/game-spec/example.game-spec.json\')), json.load(open(\'skills/game-spec/schema.json\'))); print(\'valid\')"'
    )
    if code != 0 or "valid" not in out:
        print(f"✗ Example spec validation failed:\n{err}")
        return False
    print("✓ Example spec valid")
    return True

def print_welcome_analysis(scenario_name, welcome_text, resolution):
    """Analyze and print welcome message details."""
    print(f"\n=== Welcome Message Analysis ({scenario_name}) ===")
    print(welcome_text)
    print(f"\n--- Resolution Summary ({scenario_name}) ---")
    
    active_roles = []
    fallback_roles = []
    disabled_roles = []
    
    for role_id, role_info in resolution.get("roles", {}).items():
        status = role_info.get("status", "unknown")
        if status == "active":
            caps = role_info.get("capabilities", {})
            if any(cap.get("status") == "fallback" for cap in caps.values() if isinstance(cap, dict)):
                fallback_roles.append(role_id)
            else:
                active_roles.append(role_id)
        elif status == "disabled":
            disabled_roles.append((role_id, role_info.get("reason", "unknown")))
    
    print(f"Active roles (full capabilities): {len(active_roles)}")
    for role in active_roles:
        print(f"  - {role}")
    
    print(f"\nActive roles (fallback): {len(fallback_roles)}")
    for role in fallback_roles:
        print(f"  - {role}")
    
    print(f"\nDisabled roles: {len(disabled_roles)}")
    for role, reason in disabled_roles:
        print(f"  - {role}: {reason}")

def main():
    parser = argparse.ArgumentParser(description="Grok Studio selftest")
    parser.add_argument("--scenario", choices=["has-figma", "no-figma", "both"], default="both")
    args = parser.parse_args()
    
    print("=== Grok Studio Selftest ===\n")
    
    # Test 1: Role validation (always)
    if not test_role_validation():
        print("\n✗ Selftest failed at role validation")
        return 1
    
    # Test 3: Spec validation (always)
    if not test_spec_validation():
        print("\n✗ Selftest failed at spec validation")
        return 1
    
    scenarios_to_run = []
    
    if args.scenario == "both" or args.scenario == "has-figma":
        # Scenario 1: has-Figma
        detection_figma = {
            "studio_running": True,
            "bridge_healthy": True,
            "blender_available": True,
            "figma_connector": True,
            "open_cloud_key": True,
            "github_cli": True
        }
        answers_figma = {
            "figma_seat_type": "full",
            "x_posting_route": "drafts",
            "animation_planning": "decide-for-me",
            "approvals": {
                "upload_models": True,
                "publish_animations": True
            }
        }
        scenarios_to_run.append(("has-figma", detection_figma, answers_figma))
    
    if args.scenario == "both" or args.scenario == "no-figma":
        # Scenario 2: no-Figma
        detection_no_figma = {
            "studio_running": True,
            "bridge_healthy": True,
            "blender_available": True,
            "figma_connector": False,
            "open_cloud_key": True,
            "github_cli": False
        }
        answers_no_figma = {
            "figma_seat_type": None,
            "x_posting_route": "drafts",
            "animation_planning": "decide-for-me",
            "approvals": {
                "upload_models": True,
                "publish_animations": True
            }
        }
        scenarios_to_run.append(("no-figma", detection_no_figma, answers_no_figma))
    
    # Test 2: Setup resolver for each scenario
    all_passed = True
    results = []
    
    for scenario_name, detection, answers in scenarios_to_run:
        passed, result = test_setup_resolver(scenario_name, detection, answers)
        if not passed:
            all_passed = False
            print(f"\n✗ Selftest failed at setup resolver ({scenario_name})")
        else:
            results.append((scenario_name, result))
    
    if not all_passed:
        return 1
    
    # Print welcome messages
    for scenario_name, (welcome_text, resolution) in results:
        print_welcome_analysis(scenario_name, welcome_text, resolution)
    
    print("\n=== Selftest Summary ===")
    print("✓ Role validation passed")
    print("✓ Spec validation passed")
    for scenario_name, _ in results:
        print(f"✓ Setup resolver passed ({scenario_name})")
        print(f"✓ Welcome message generated ({scenario_name})")
    
    print("\n✓ All selftests passed")
    return 0

if __name__ == "__main__":
    sys.exit(main())
