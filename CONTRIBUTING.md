# Contributing to Grok Studio

## Add Your Own GrokBot Role

Grok Studio is extensible: you can add your own specialist role without editing core files.
Each role is self-contained in its own folder under `roles/<role-id>/`.

### Role Structure

```
roles/<role-id>/
  manifest.json         # Machine-readable role definition (required)
  agent.md              # Agent instructions with frontmatter (required)
  example-*.md          # Example task or artifact (optional)
```

### Step 1: Choose a Role ID

Pick a short, kebab-case identifier (e.g. `vfx`, `qa`, `monetization`). It must:
- Start with a lowercase letter
- Contain only lowercase letters, digits, and hyphens
- Be unique (check `python3 scripts/roles.py list`)

### Step 2: Write the Manifest

Create `roles/<role-id>/manifest.json` following the schema at
`roles/role-manifest.schema.json`. Required fields:

```json
{
  "manifestVersion": "1.0",
  "role": {
    "id": "your-role-id",
    "name": "Your Role GrokBot",
    "description": "One-sentence summary (max 200 chars)."
  },
  "display": {
    "keyCapabilities": [
      "2-4 concise capability statements",
      "for the welcome message"
    ]
  },
  "ownership": {
    "specFields": ["your.spec.field"],
    "studioSubtrees": ["ReplicatedStorage.YourArea"],
    "files": ["your-folder/"]
  },
  "taskTypes": [
    {
      "id": "your-task-type",
      "description": "What this task does",
      "typicalDependsOn": ["skeleton"]
    }
  ],
  "capabilities": {
    "required": [],
    "optional": []
  },
  "agentInstructions": {
    "file": "agent.md"
  },
  "skills": [
    {
      "path": "skills/your-skill",
      "ownership": "owned"
    },
    {
      "path": "skills/team-protocol",
      "ownership": "shared"
    }
  ],
  "setupQuestions": []
}
```

**Key sections:**

- **`role`**: ID, display name, and one-sentence description
- **`display.keyCapabilities`**: 2-4 bullet points for the welcome message
- **`ownership`**: Which spec fields, Studio subtrees, and files this role owns (see
  `skills/team-protocol/SKILL.md` for the ownership rules)
- **`taskTypes`**: Task types this role handles, for automatic planning and routing
- **`capabilities`**: Required and optional integrations (connectors, secrets, checks).
  Setup resolves these and shows what's available.
- **`skills`**: Skills this role uses (`ownership: "owned"` means you maintain it;
  `"shared"` means it's used by multiple roles)
- **`setupQuestions`**: Questions this role contributes to the guided setup (optional)

### Step 3: Write the Agent Instructions

Create `roles/<role-id>/agent.md` with YAML frontmatter:

```markdown
---
name: your-role-id
description: Same one-sentence description as the manifest. Explains when to use this agent.
---

You are **Your Role GrokBot**, the [job title] on the grok-studio team. The team is Lead,
Coding, Designer, Builder, Animator and you, and together you build one Roblox game in the
user's Roblox Studio from one `game-spec.json`.

Before any work, load the skills `team-protocol` and `your-skill`. `team-protocol` wins if
anything here disagrees with it.

## You own
- Studio: [list paths from ownership.studioSubtrees]
- Spec: [list fields from ownership.specFields]
- Files: [list paths from ownership.files]

## Your usual tasks
1. Task type 1: what and when
2. Task type 2: what and when
...

## Every task starts the same way
Run the health check from `team-protocol`, then `list_roblox_studios`, and use the id of
the entry for this game's place id (`build.placeId`). Studio ids change whenever Studio
restarts: never save one in memory or notes.

## Rules
- [Your role-specific rules]
- Check the `studio-play` lock before every Studio write. Never start or stop play.
- **Never message, ask, or send approval popups to the user.** Every question, approval or
  decision goes to the Lead as `ASK` or `BLOCKED`. Only the Lead talks to the user.

## Reporting
On Grok Bot, message **Lead GrokBot** with `DONE #n` / `BLOCKED #n`, listing what changed,
and send `ASK #n` messages to the owner Bot. As a subagent, put the same blocks in your
final answer.
```

Follow the template from existing roles (`roles/coder/agent.md`, `roles/vfx/agent.md`).

### Step 4: Create Skills (if needed)

If your role needs new skills, create them under `skills/<skill-name>/SKILL.md` with YAML
frontmatter. See existing skills for the format (`skills/roblox-vfx/SKILL.md`,
`skills/roblox-audio/SKILL.md`).

### Step 5: Add an Example (optional)

Create `roles/<role-id>/example-*.md` showing a typical task and its DONE report. See
`roles/vfx/example-coin-pickup-vfx.md` or `roles/marketing/example-icon-brief.md`.

### Step 6: Extend the Schema (if needed)

If your role writes to new spec fields:

1. Add them to `skills/game-spec/schema.json` (follow the existing structure)
2. Update `skills/game-spec/SKILL.md` (procedure step for your fields)
3. Update `skills/game-spec/example.game-spec.json` (add example data)

### Step 7: Validate

```bash
python3 scripts/roles.py validate
```

This checks:
- Manifest validates against `roles/role-manifest.schema.json`
- All referenced files (agent.md, skills, examples) exist
- No spec field ownership conflicts

Fix any errors before committing.

### Step 8: Test

1. Run `/setup-bridge` in a test session
2. Verify your role appears in the welcome message
3. Test a typical task: the Lead should route it to your role
4. Verify your role's DONE report format and team-protocol compliance

## Validation Script

`scripts/roles.py` discovers and validates roles:

```bash
# List all roles
python3 scripts/roles.py list

# Validate all manifests
python3 scripts/roles.py validate

# Generate setup questions from all roles
python3 scripts/roles.py setup-questions
```

## Worked Example: VFX GrokBot

See `roles/vfx/` for a complete worked example:
- `manifest.json` - defines the role
- `agent.md` - agent instructions
- `example-coin-pickup-vfx.md` - example task
- `skills/roblox-vfx/SKILL.md` - owned skill

VFX was added in v0.3.0 without touching any core files.

## Guidelines

- **Keep roles focused**: one specialist area (VFX, sound, QA, monetization), not broad
  overlaps
- **Follow team protocol**: ownership rules, locks, message formats, escalation (never
  contact the user)
- **Dynamic discovery**: the Lead and setup discover roles from manifests, so your role
  appears automatically
- **Capability resolution**: use `capabilities.required` and `capabilities.optional` to
  declare what your role needs (connectors, secrets). Setup resolves them and shows the
  fallback.
- **Test with existing specs**: ensure your role doesn't break the example spec
  (`skills/game-spec/example.game-spec.json`)

## Questions?

Open an issue or read the team-protocol skill (`skills/team-protocol/SKILL.md`) for
ownership, locks, and message formats.
