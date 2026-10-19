# Contributing to Grok Studio (for Claude & AI Assistants)

**Quick orientation for Claude, Cursor, and other AI coding assistants**

This is a plugin for **Grok Bot** (a multi-agent platform), not a standalone application. The plugin consists of skills, scripts, and role definitions executed by Grok Bot agents on a shared Linux machine.

---

## Repository Layout

```
grok-studio/
├── roles/                      # 8 specialist roles (extensible)
│   ├── lead/                   # Lead GrokBot (orchestrator)
│   ├── coder/                  # Coding GrokBot (Luau scripts)
│   ├── designer/               # Designer GrokBot (UI)
│   ├── builder/                # Builder GrokBot (world + 3D)
│   ├── animator/               # Animator GrokBot (animations)
│   ├── vfx/                    # VFX GrokBot (particle effects)
│   ├── sfx/                    # SFX GrokBot (sound design)
│   └── marketing/              # Marketing GrokBot (icons, X posts)
│   
│   Each role folder:
│   ├── manifest.json           # Machine-readable definition (REQUIRED)
│   ├── agent.md                # Agent instructions (REQUIRED, canonical source)
│   └── example-*.md            # Example tasks (optional)
│
├── skills/                     # Shared knowledge library
│   ├── game-spec/              # Spec schema and examples
│   ├── roblox-code/            # Luau coding guidelines
│   ├── roblox-building/        # Studio building + Blender
│   ├── roblox-animations/      # Animation creation
│   ├── roblox-vfx/             # VFX creation
│   ├── roblox-audio/           # Sound design
│   ├── team-protocol/          # 8-bot coordination rules
│   ├── playtest-loop/          # Automated playtesting
│   └── ...                     # More skills
│
├── scripts/                    # Automation and validation
│   ├── roles.py                # Role discovery and validation
│   ├── setup.py                # Setup resolver
│   ├── selftest.py             # Headless testing
│   ├── validate-spec-gates.py  # Artifact validator
│   └── heal-mcp-session.sh     # MCP session repair
│
├── setup/                      # Setup flow definitions
│   ├── steps.yaml              # Declarative setup flow
│   ├── welcome-template.md     # Dynamic welcome message
│   └── setup-config.schema.json
│
├── bridge/                     # Roblox Studio bridge (runs on user's PC)
├── docs/                       # Platform documentation
│   └── GROKBOT-PLATFORM.md     # What Grok Bot can/cannot do
│
├── README.md                   # User-facing quick start
├── CONTRIBUTING.md             # Add custom roles + "Lessons to Rules"
├── SETUP_SYSTEM.md             # Setup architecture
├── HOW_TO_TEST.md              # End-to-end testing guide
└── CLAUDE.md                   # This file
```

---

## Key Concepts

### 1. This is NOT a Standalone App
- **No server**, no UI, no runtime
- Executed by Grok Bot agents on their shared Linux machine
- Skills are loaded by agents, scripts run in their environment
- Users interact via Grok Bot chat interface

### 2. Multi-Agent Architecture
- **8 specialist agents** work in parallel
- Each has own chat, persona, memory
- Coordinate via **async messaging** (no synchronous calls)
- Share one Linux machine + one `game-spec.json`
- Team protocol prevents conflicts (locks, ownership rules)

### 3. Extensible Role System
- Roles defined by `manifest.json` (schema validation)
- Agent instructions in `agent.md` (canonical source)
- Dynamic discovery (no hardcoded role lists)
- Add roles without editing core files

### 4. Platform Constraints
- See **[docs/GROKBOT-PLATFORM.md](docs/GROKBOT-PLATFORM.md)** for what Grok Bot can/cannot do
- UI limited to: question cards, masked secrets, forms (no custom widgets)
- User PC commands require per-command approval
- Studio access only via MCP tools (no GUI automation)

---

## How to Add a Custom Role

Full guide in **[CONTRIBUTING.md](CONTRIBUTING.md)**. Quick version:

### 1. Create Role Folder
```bash
mkdir -p roles/my-role
```

### 2. Write Manifest
```json
{
  "manifestVersion": "1.0",
  "role": {
    "id": "my-role",
    "name": "My Role GrokBot",
    "description": "What this role does"
  },
  "ownership": {
    "specFields": ["myField"],
    "studioSubtrees": ["ReplicatedStorage.MyStuff"]
  },
  "capabilities": {
    "required": [...],
    "optional": [...]
  },
  "agentInstructions": { "file": "agent.md" },
  "skills": [...]
}
```

### 3. Write Agent Instructions
```markdown
---
name: my-role
description: My Role GrokBot - does X, Y, Z
---

You are **My Role GrokBot**...
```

### 4. Validate
```bash
uv run scripts/roles.py validate
```

### 5. Test Integration
```bash
uv run scripts/setup.py --self-check
```

---

## Development Workflow

### Running Validators
```bash
# Validate all roles
uv run scripts/roles.py validate

# Test setup resolver
uv run scripts/setup.py --self-check

# Run complete selftest (has-figma, no-figma)
uv run scripts/selftest.py

# Validate example spec
python3 -c "import json,jsonschema; jsonschema.validate(json.load(open('skills/game-spec/example.game-spec.json')), json.load(open('skills/game-spec/schema.json'))); print('✓ valid')"

# Check artifact gates (on a game)
python3 scripts/validate-spec-gates.py <slug>

# Test MCP healing
bash scripts/heal-mcp-session.sh
```

All should exit 0 on success.

### File Conventions

#### JSON Files
- 2-space indent
- Validate against schema before committing
- No trailing commas

#### Markdown Files
- Frontmatter for metadata (YAML between `---` markers)
- Code blocks use triple backticks with language tags
- Line length: prefer <100 chars, no hard limit

#### Python Scripts
- `#!/usr/bin/env python3` shebang
- Docstrings for functions
- Type hints where helpful
- Exit 0 on success, 1 on failure

#### Shell Scripts
- `#!/usr/bin/env bash` shebang
- `set -euo pipefail` for safety
- Chmod +x after creating

#### YAML Files
- 2-space indent
- Use `>` for multi-line strings (folded)
- Validate against schema where applicable

### Naming Conventions
- **Roles:** `kebab-case` (e.g., `my-role`)
- **Skills:** `kebab-case` (e.g., `my-skill`)
- **Scripts:** `snake_case.py` or `kebab-case.sh`
- **Spec fields:** `camelCase` (e.g., `myField`)
- **Files:** `kebab-case.md`, `PascalCase.luau`

---

## Key Files to Know

### For Role Development
- `roles/role-manifest.schema.json` - Manifest validation schema
- `scripts/roles.py` - Discovery, validation, conflict detection
- `CONTRIBUTING.md` - Complete role creation guide

### For Setup Flow
- `setup/steps.yaml` - Declarative setup definitions
- `scripts/setup.py` - Resolver (detection + answers → resolution)
- `setup/welcome-template.md` - Dynamic welcome message

### For Playtest Fixes
- `skills/roblox-code/reference/GuardedAnimationLoader.luau` - Asset loading
- `skills/playtest-loop/reference/AcceptanceFramework.luau` - Extensible checks
- `scripts/validate-spec-gates.py` - Artifact validator
- `scripts/heal-mcp-session.sh` - MCP session healing

### For Testing
- `scripts/selftest.py` - Headless simulation with fixtures
- `HOW_TO_TEST.md` - End-to-end testing from plugin install
- `VERIFICATION_REPORT.md` - Implementation verification

---

## Design Principles

### 1. General, Game-Agnostic Rules
**Never design for one specific game.** Rules must apply to any Roblox game.

✅ **Good:** "Every interaction must work via real player input"
❌ **Bad:** "FPS weak points must not be occluded by hull meshes"

See **[CONTRIBUTING.md](CONTRIBUTING.md)** "Lessons to Rules" section.

### 2. Extensible Framework
All checks are driven by `game-spec.json`. New roles plug in custom checks without modifying core.

```lua
-- AcceptanceFramework is extensible
local framework = AcceptanceFramework.new(gameSpec)
framework:RegisterCheck("my_check", MyCheckFunction)
framework:RunAll()
```

### 3. Single Source of Truth
- **Agent instructions:** `roles/<id>/agent.md` (canonical)
- **Role definition:** `roles/<id>/manifest.json`
- **Spec schema:** `skills/game-spec/schema.json`

### 4. Team Protocol
- **Lead** talks to user, orchestrates work
- **Specialists** never contact user (route via Lead)
- **Ownership:** Each role owns specific spec fields + Studio subtrees
- **Locks:** `studio-play` and `spec` locks prevent conflicts
- **Messages:** `[GS] TASK`, `[GS] DONE`, `[GS] BLOCKED`, `[GS] ASK`

### 5. Platform Constraints
- **Question cards** for user choices (not free text)
- **Masked secret entry** for credentials (one per card)
- **Async messaging** between bots (no synchronous calls)
- **MCP tools** for Studio (no GUI automation)
- **Approval upfront** for publishing/spending

See **[docs/GROKBOT-PLATFORM.md](docs/GROKBOT-PLATFORM.md)** for complete list.

---

## Common Tasks

### Add a New Skill
1. Create `skills/my-skill/SKILL.md` with frontmatter
2. Add to role manifest's `skills[]` array
3. No registration needed (global library)
4. **Note:** Skills don't appear instantly (platform refresh delay)

### Extend Setup Flow
1. Edit `setup/steps.yaml` (add check, step, or question)
2. Update role manifest if adding capability
3. Test: `uv run scripts/setup.py --self-check`
4. Run: `uv run scripts/selftest.py`

### Add Acceptance Check
1. Add check function to `AcceptanceFramework.luau`
2. Register in `runAll()` method
3. Document in `skills/playtest-loop/SKILL.md`
4. Update spec schema if check needs new fields

### Fix a Validation Error
```bash
# See which role failed
uv run scripts/roles.py validate

# Check JSON syntax
python3 -m json.tool roles/<role>/manifest.json

# Validate against schema
python3 -c "import json,jsonschema; jsonschema.validate(json.load(open('roles/<role>/manifest.json')), json.load(open('roles/role-manifest.schema.json')))"
```

---

## Testing Your Changes

### Before Committing
```bash
# 1. Validate all roles
uv run scripts/roles.py validate

# 2. Test setup resolver
uv run scripts/setup.py --self-check

# 3. Run selftest (both scenarios)
uv run scripts/selftest.py

# 4. Validate example spec
python3 -c "import json,jsonschema; jsonschema.validate(json.load(open('skills/game-spec/example.game-spec.json')), json.load(open('skills/game-spec/schema.json'))); print('✓')"
```

### End-to-End (Optional)
See **[HOW_TO_TEST.md](HOW_TO_TEST.md)** for complete guide:
1. Install plugin via bootstrap.sh
2. Setup Studio with MCP
3. Message Lead: "Hi! Let's set up grok-studio."
4. Verify welcome message shows all 8 bots

---

## Getting Help

### Documentation
- **[README.md](README.md)** - User quick start
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Add roles, "Lessons to Rules"
- **[docs/GROKBOT-PLATFORM.md](docs/GROKBOT-PLATFORM.md)** - Platform capabilities
- **[HOW_TO_TEST.md](HOW_TO_TEST.md)** - Testing guide
- **[SETUP_SYSTEM.md](SETUP_SYSTEM.md)** - Setup architecture

### Key References
- **Role manifest schema:** `roles/role-manifest.schema.json`
- **Spec schema:** `skills/game-spec/schema.json`
- **Team protocol:** `skills/team-protocol/SKILL.md`
- **Acceptance framework:** `skills/playtest-loop/reference/AcceptanceFramework.luau`

### Common Patterns
Look at existing roles (`roles/vfx/`, `roles/sfx/`, `roles/marketing/`) for examples of:
- Manifest structure
- Agent instructions format
- Setup questions
- Capability declarations
- Skill ownership

---

## Quick Reference

### File You'll Edit Most
- `roles/<id>/manifest.json` - Role definition
- `roles/<id>/agent.md` - Agent instructions
- `skills/<name>/SKILL.md` - Skill documentation
- `setup/steps.yaml` - Setup flow

### Commands You'll Run Most
```bash
uv run scripts/roles.py validate     # After role changes
uv run scripts/setup.py --self-check # After setup changes
uv run scripts/selftest.py           # Full integration test
```

### Files You'll Read Most
- `CONTRIBUTING.md` - How to add roles
- `docs/GROKBOT-PLATFORM.md` - What's possible
- `skills/team-protocol/SKILL.md` - Coordination rules
- `skills/game-spec/schema.json` - Spec structure

---

## Remember

1. This is a **Grok Bot plugin**, not a standalone app
2. Design for **8-bot async coordination**, not single-agent execution
3. Follow **team protocol** (ownership, locks, messages)
4. Check **platform constraints** before assuming features exist
5. Write **general rules**, not game-specific symptoms
6. Validate **before committing** (all scripts should pass)
7. Single source of truth: **`roles/<id>/agent.md`**

**Start here:** [CONTRIBUTING.md](CONTRIBUTING.md) → Add a role → Test with validators → See it in selftest welcome message

**Questions?** Read [docs/GROKBOT-PLATFORM.md](docs/GROKBOT-PLATFORM.md) to understand what Grok Bot can and cannot do.
