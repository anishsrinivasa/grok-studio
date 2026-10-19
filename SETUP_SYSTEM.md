# Setup System - Runnable Components

## ✅ Working Now

### 1. Role Discovery and Validation
```bash
# List all discovered roles
uv run scripts/roles.py list

# Validate all role manifests
uv run scripts/roles.py validate

# Generate setup questions from all roles
uv run scripts/roles.py setup-questions
```

**Output:** 8 roles discovered (lead, coder, designer, builder, animator, vfx, sfx, marketing), all validate successfully.

### 2. Setup Resolver
```bash
# Run self-check with test data
uv run scripts/setup.py --self-check

# Run with real detection results and answers
uv run scripts/setup.py \
  --detection-results detection.json \
  --answers answers.json \
  --output resolution.json \
  --welcome-output welcome.md
```

**Inputs:**
- `detection.json` - Auto-detection results from checks
- `answers.json` - User answers to capability questions

**Outputs:**
- `resolution.json` - Per-role capability resolution + spec patch
- `welcome.md` - Filled welcome message

**Self-check results:** All 8 roles resolve to "active" with test data. Welcome message generates correctly with dynamic role information.

### 3. Setup Definitions
- `setup/steps.yaml` - Declarative setup flow
  - Auto-detect checks (Studio, bridge, Blender, connectors, secrets)
  - Manual step templates (install Studio, enable settings, create API key)
  - Capability questions (merged with role manifests)
  - Approval questions (uploads, publishing)
  - Readiness gate definitions

- `setup/welcome-template.md` - Welcome message template
  - Filled by `scripts/setup.py` with role data and setup summary

### 4. Role Manifests
Each role in `roles/<id>/manifest.json` declares:
- Ownership (spec fields, Studio subtrees, files)
- Task types (for automatic planning and routing)
- Capabilities (required/optional, with requirements and fallbacks)
- Setup questions (contribution to guided setup)
- Agent instructions file reference
- Skills used
- Examples

**Source of truth:** `roles/<id>/agent.md` is canonical.

### 5. Validation
```bash
# Validate example spec against schema (includes new vfx field)
python3 -c "import json,jsonschema;jsonschema.validate(json.load(open('skills/game-spec/example.game-spec.json')),json.load(open('skills/game-spec/schema.json')));print('✓ valid')"
```

---

## 🔨 To Be Implemented (Lead Skill)

The Lead needs to execute this flow in `skills/setup-bridge/SKILL.md` or a new setup executor:

### Setup Flow Execution

1. **Auto-Detection Phase:**
   ```python
   detection_results = {}
   
   # Run each check from setup/steps.yaml autoDetectChecks
   for check in checks:
       if check.get("command"):
           result = run_command(check["command"])
           detection_results[check["id"]] = "ok" if matches_pattern(result, check["successPattern"]) else "error"
       elif check.get("env_var"):
           detection_results[check["id"]] = "present" if os.getenv(check["env_var"]) else "missing"
       elif check.get("mcp_call"):
           # Call MCP tool and check response
           pass
   ```

2. **Manual Steps (only show what's needed):**
   ```python
   for step in manual_steps:
       if needs_step(step, detection_results):
           if host_has_ui_widgets:
               # Use RequestUserForm or step card widget
               show_step_card(step["what"], step["why"], step["location"])
               wait_for_done_confirmation()
           else:
               # Numbered checklist fallback
               print(f"Step: {step['what']}")
               print(f"Why: {step['why']}")
               print(f"Location: {step['location']}")
               input("Press Enter when done...")
           
           # Verify
           if step.get("verifyCheck"):
               re_run_check(step["verifyCheck"])
   ```

3. **Capability Questions:**
   ```python
   answers = {}
   
   # Merge questions from setup/steps.yaml and role manifests
   all_questions = load_capability_questions() + load_role_setup_questions()
   
   for q in all_questions:
       if host_has_question_widget:
           # Use in-chat question widget
           answers[q["id"]] = ask_question_widget(
               prompt=q["prompt"],
               options=q["options"],
               type=q["type"],  # choice, yes-no, multi-select
               default=q["default"]
           )
       else:
           # Numbered list fallback
           print(f"{q['prompt']}")
           for i, opt in enumerate(q["options"]):
               print(f"  {i+1}. {opt}")
           choice = input("Enter number: ")
           answers[q["id"]] = q["options"][int(choice)-1]
   ```

4. **Approval Collection:**
   ```python
   for approval in approval_questions:
       answers[approval["id"]] = ask_yes_no(approval["prompt"], default=approval["default"])
   ```

5. **Run Resolver:**
   ```python
   # Write inputs
   write_json("detection.json", detection_results)
   write_json("answers.json", answers)
   
   # Run resolver
   run_command("uv run scripts/setup.py --detection-results detection.json --answers answers.json --output resolution.json --welcome-output welcome.md")
   
   # Load outputs
   resolution = read_json("resolution.json")
   welcome_message = read_file("welcome.md")
   ```

6. **Apply to Spec:**
   ```python
   spec = read_json(f"games/{slug}/game-spec.json")
   spec["build"]["connectors"] = resolution["specPatch"]["build"]["connectors"]
   spec["build"]["approvals"] = resolution["specPatch"]["build"]["approvals"]
   write_json(f"games/{slug}/game-spec.json", spec)
   ```

7. **Send Welcome Message:**
   ```python
   print(welcome_message)
   # Or send to user via appropriate channel
   ```

8. **Readiness Gate:**
   - Run G1-G5 checks as defined in `setup/steps.yaml` readinessGate
   - Report pass/fail/skipped for each
   - Say "ready" only if all required checks pass

### Widget Availability
- **Grok Bot:** Check for question widget, RequestUserForm, masked secret request
- **Structure:** All logic is in setup/steps.yaml + role manifests, so the Lead just executes the definitions

---

## File Structure

```
setup/
  steps.yaml                    # Declarative setup flow
  welcome-template.md           # Welcome message template
  setup-config.schema.json      # Schema for setup definitions

scripts/
  setup.py                      # Resolver (takes detection + answers, outputs resolution + welcome)
  roles.py                      # Role discovery and validation

roles/<id>/
  manifest.json                 # Role definition (canonical)
  agent.md                      # Agent instructions (canonical)
  example-*.md                  # Examples

skills/setup-bridge/SKILL.md    # Lead executor (needs rewrite to use setup/)
```

---

## Testing

1. **Role system:**
   ```bash
   uv run scripts/roles.py validate
   # Output: ✓ All roles valid
   ```

2. **Resolver:**
   ```bash
   uv run scripts/setup.py --self-check
   # Output: ✓ Self-check passed, 8 roles active
   ```

3. **Example spec:**
   ```bash
   python3 -c "import json,jsonschema;jsonschema.validate(json.load(open('skills/game-spec/example.game-spec.json')),json.load(open('skills/game-spec/schema.json')));print('✓')"
   # Output: ✓
   ```

---

## Summary

**What's runnable:** Role discovery, validation, resolver (with self-check), welcome message generation, spec patching.

**What's needed:** Lead skill rewrite to execute the setup flow (load definitions, run checks, show steps, ask questions, call resolver, apply patch, send welcome, run readiness gate).

**Exact flow:** Load `setup/steps.yaml` + role manifests → auto-detect → show needed manual steps → ask capability questions → ask approvals → run `scripts/setup.py` → patch spec → send welcome → readiness gate → done.
