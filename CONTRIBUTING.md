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
- Be unique (check `uv run scripts/roles.py list`)

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
uv run scripts/roles.py validate
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
uv run scripts/roles.py list

# Validate all manifests
uv run scripts/roles.py validate

# Generate setup questions from all roles
uv run scripts/roles.py setup-questions
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

---

## Lessons to Rules: Making Playtest Failures Impossible to Repeat

When a playtest failure reveals a systemic gap — not just a one-off bug but a pattern
that could recur in any game — we codify the fix as a **general, game-agnostic rule**
with three components:

1. **Rule (in the owning role's agent.md and skill):** A clear principle or requirement
   that prevents the failure class.
2. **Reusable code pattern (where applicable):** A reference implementation in
   `skills/*/reference/*.luau` or a documented pattern that specialists can adapt.
3. **Automated check:** A playtest-loop acceptance check (using `AcceptanceFramework.luau`)
   that the Lead always runs, and/or a pre-DONE validator or self-check script.

This approach turns debugging into lasting process improvements.

### Example: 7 Fixed Failure Classes (v0.3.0)

**Important:** Rules must be stated as the general failure class, never as the specific symptom. "Weak point occluded" becomes "interactions don't work." "Spawn camping" becomes "gameplay doesn't match design."

| Failure | Rule | Check | Files |
|---------|------|-------|-------|
| **1. Assets silently never load** | Never assume a load succeeded. All Roblox asset loads (animations, sounds, meshes, images) must be verified: wait for load completion with timeout, retry, fallback, warn once. | Playtest: `AcceptanceFramework` verifies every declared asset (animations, sounds, meshes, images) loads successfully and takes effect at runtime (animation tracks have Length > 0 and move Motor6Ds, sounds are IsLoaded, meshes preload successfully). | `skills/roblox-code/SKILL.md` (asset loading section), `skills/roblox-code/reference/GuardedAnimationLoader.luau`, `skills/playtest-loop/reference/AcceptanceFramework.luau` |
| **2. Interactions don't work** | Every interaction must work through real player input. Every interactive or targetable element the spec declares (hit zones, buttons, ProximityPrompts, ClickDetectors, pickups, touch triggers, doors, UI buttons) must be reachable the way a player would reach it (camera raycast, character touch, prompt trigger, UI click). Decorative or visual geometry never blocks interaction (CanQuery, CanTouch, collision are deliberately set). | Builder self-check: Exercise each interaction through its real input path before DONE. Playtest: `AcceptanceFramework` exercises every declared interaction through real input paths, **never by calling server functions directly**, and fails any element that doesn't respond. | `skills/roblox-building/SKILL.md` (interaction reachability section), `roles/builder/agent.md` |
| **3. Attachments to rigs break** | Everything attached to or held by a character must be checked against the rig. Tools, accessories, welded props, mounts, and vehicles must have correct orientation, anchor point, and scale on an R15 rig, verified automatically. | Builder self-check: Attach on dummy R15 rig, verify orientation/position/scale, screenshot. Playtest: `AcceptanceFramework` verifies every declared tool, accessory, and attached object on a test rig. | `skills/roblox-building/SKILL.md` (rig attachments section), `roles/builder/agent.md` |
| **4. DONE claims lack proof** | Every DONE claim must be backed by machine-checkable artifacts. Each role's DONE must pass a validator that checks its declared outputs exist and are complete for every item in its task, not only assets (e.g., `reports/<id>_import.json` for assets at `placed`, `assetId` for animations at `published`, `config` for VFX at `verified`, script tests for code). | Pre-DONE validator: `scripts/validate-spec-gates.py` checks every terminal status has required artifacts. Fails if missing. Each role defines what artifacts it produces. | `scripts/validate-spec-gates.py`, `skills/blender-assets/SKILL.md` |
| **5. Gameplay doesn't match design** | Spec numbers must match runtime, and the game must be fair to a new player. The spec declares measurable targets for every gameplay tunable (rates, chances, damage, cooldowns, timers, economy rates) with tolerance. Coding implements measured checks. The spec includes a genre-neutral new-player-experience check: a freshly joined player, idle and acting normally (not exploiting, not AFK), isn't killed, stuck, softlocked, or overwhelmed within a spec-defined grace window (genre-specific, e.g., 5s for action, 30s for puzzles), and can reach the core loop. No hardcoded defaults; declare grace window and fairness criteria explicitly. | Coding: Implement measurement code for every tunable. Playtest: `AcceptanceFramework` verifies measured values match spec targets within tolerance, and new-player fairness check passes (idle survival, core loop reachability). | `skills/game-spec/SKILL.md`, `skills/roblox-code/SKILL.md` (tunable measurement section) |
| **6. MCP sessions go stale** | Before declaring `BLOCKED` on any Studio tool failure, always run `bash /workspace/scripts/heal-mcp-session.sh`. Gateway restarts, tunnel blips, and auth token refreshes drop open MCP sessions. The heal script kills only the calling bot's exec-daemon children (process hierarchy isolation), never other bots' processes. Mandatory step. | Any bot self-check: Run heal script before escalating Studio errors. | `scripts/heal-mcp-session.sh`, `skills/connect-studio/SKILL.md` (Heal section mandatory step), `skills/team-protocol/SKILL.md` (section 7a) |
| **7. Coordination messages lost** | The coordinator itself always sends coordination messages, never delegates to helpers without messaging tools. For playtest-loop, the Lead itself always sends `[GS] PLAY ON` and `[GS] PLAY OFF` (even on failure), never delegates to helpers. | Lead self-check: Never delegate coordination messages. Always send both messages directly, even on error paths. | `skills/playtest-loop/SKILL.md` (team mode section) |

### How to Apply This Pattern

When you encounter a playtest failure:

1. **Generalize:** Is this a one-off bug (fix the code) or a pattern (e.g., "any asset can
   fail to load")? If it's a pattern, it needs a rule.
2. **Write the rule** in the owning role's `agent.md` and skill (e.g., Builder owns
   geometry, Coding owns scripts, Lead owns coordination).
3. **Provide a reusable pattern** (reference implementation, documented snippet, or guard
   function) so future work doesn't reinvent the solution.
4. **Add an automated check** (playtest acceptance check, validator script, or self-check
   step) so the failure cannot silently recur.
5. **Update this table** with the new failure class, rule, check, and files.

This discipline scales: as the plugin matures, the automated checks grow denser and entire
classes of bugs become impossible.
