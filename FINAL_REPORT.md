# Final Report: 7 Playtest Failure Classes - General, Game-Agnostic Rules

## Executive Summary

All 7 playtest failure classes have been fixed with **general, game-agnostic rules** (not specific to one FPS), reusable code patterns, and automated checks. Rules are stated as failure classes ("interactions don't work"), never as specific symptoms ("weak point occluded"). The `AcceptanceFramework` is generic and extensible, driven by `game-spec.json`, so new roles and genres plug in their own checks.

---

## Complete Failure/Rule/Check/Files Table (Generalized)

| # | Failure Class | General Rule | Automated Check | Files Modified/Created |
|---|---------------|--------------|-----------------|------------------------|
| **1** | **Assets silently never load** | **Never assume a load succeeded.** All Roblox asset loads (animations, sounds, meshes, images) must be verified: wait for load completion with timeout, retry, fallback, warn once. | **Playtest:** `AcceptanceFramework` verifies every declared asset (animations, sounds, meshes, images) loads successfully and takes effect at runtime (animation tracks have Length > 0 and move Motor6Ds, sounds are IsLoaded, meshes preload successfully). | **Created:** `skills/roblox-code/reference/GuardedAnimationLoader.luau`, `skills/playtest-loop/reference/AcceptanceFramework.luau`<br>**Modified:** `skills/roblox-code/SKILL.md`, `skills/playtest-loop/SKILL.md` |
| **2** | **Interactions don't work** | **Every interaction must work through real player input.** Every interactive or targetable element the spec declares (hit zones, buttons, ProximityPrompts, ClickDetectors, pickups, touch triggers, doors, UI buttons) must be reachable the way a player would reach it (camera raycast, character touch, prompt trigger, UI click). Decorative or visual geometry never blocks interaction (CanQuery, CanTouch, collision are deliberately set). | **Builder self-check:** Exercise each interaction through its real input path before DONE.<br>**Playtest:** `AcceptanceFramework` exercises every declared interaction through real input paths, **never by calling server functions directly**, and fails any element that doesn't respond. | **Modified:** `skills/roblox-building/SKILL.md` (interaction reachability section), `roles/builder/agent.md` |
| **3** | **Attachments to rigs break** | **Everything attached to or held by a character must be checked against the rig.** Tools, accessories, welded props, mounts, and vehicles must have correct orientation, anchor point, and scale on an R15 rig, verified automatically. | **Builder self-check:** Attach on dummy R15 rig, verify orientation/position/scale, screenshot.<br>**Playtest:** `AcceptanceFramework` verifies every declared tool, accessory, and attached object on a test rig. | **Modified:** `skills/roblox-building/SKILL.md` (rig attachments section), `roles/builder/agent.md` |
| **4** | **DONE claims lack proof** | **Every DONE claim must be backed by machine-checkable artifacts.** Each role's DONE must pass a validator that checks its declared outputs exist and are complete for every item in its task, not only assets (e.g., `reports/<id>_import.json` for assets at `placed`, `assetId` for animations at `published`, `config` for VFX at `verified`, script tests for code). Each role defines what artifacts it produces. | **Pre-DONE validator:** `scripts/validate-spec-gates.py` checks every terminal status has required artifacts. Fails if missing. | **Created:** `scripts/validate-spec-gates.py`<br>**Modified:** `skills/blender-assets/SKILL.md` |
| **5** | **Gameplay doesn't match design** | **Spec numbers must match runtime, and the game must be fair to a new player.**<br><br>1. The spec declares measurable targets for every gameplay tunable (rates, chances, damage, cooldowns, timers, economy rates) with tolerance. Coding implements measured checks at runtime.<br><br>2. The spec includes a **genre-neutral new-player-experience check**: a freshly joined player, idle and acting normally (not exploiting, not AFK), isn't killed, stuck, softlocked, or overwhelmed within a **spec-defined grace window** (genre-specific, e.g., 5s for action, 30s for puzzles), and can reach the core loop. **No hardcoded defaults**; declare grace window and fairness criteria explicitly per game. | **Coding:** Implement measurement code for every tunable.<br>**Playtest:** `AcceptanceFramework` verifies measured values match spec targets within tolerance, and new-player fairness check passes (idle survival, core loop reachability). | **Modified:** `skills/game-spec/SKILL.md`, `skills/roblox-code/SKILL.md` (tunable measurement + fairness section) |
| **6** | **MCP sessions go stale** | **Before declaring `BLOCKED` on any Studio tool failure, always run `bash /workspace/scripts/heal-mcp-session.sh`.** Gateway restarts, tunnel blips, and auth token refreshes drop open MCP sessions. The heal script kills only the calling bot's exec-daemon children (process hierarchy isolation), never other bots' processes. Mandatory step. | **Any bot self-check:** Run heal script before escalating Studio errors. | **Created:** `scripts/heal-mcp-session.sh`<br>**Modified:** `skills/connect-studio/SKILL.md` (Heal section mandatory step), `skills/team-protocol/SKILL.md` (section 7a) |
| **7** | **Coordination messages lost** | **The coordinator itself always sends coordination messages, never delegates to helpers without messaging tools.** For playtest-loop, the Lead itself always sends `[GS] PLAY ON` and `[GS] PLAY OFF` (even on failure), never delegates to helpers without messaging tools. | **Lead self-check:** Never delegate coordination messages. Always send both messages directly, even on error paths. | **Modified:** `skills/playtest-loop/SKILL.md` (team mode section) |

---

## Key Principle: State Rules as General Failure Classes

**From CONTRIBUTING.md "Lessons to Rules":**

> Rules must be stated as the general failure class, never as the specific symptom.
> 
> - "Weak point occluded" → "Interactions don't work"
> - "Spawn camping" → "Gameplay doesn't match design"
> - "Tool.Grip wrong" → "Attachments to rigs break"

This ensures rules apply to all games and genres, not just the specific failure that revealed the gap.

---

## Generic, Extensible Acceptance Framework

The `AcceptanceFramework.luau` is **driven by `game-spec.json`** so new roles and genres plug in their own checks:

**Structure:**
```lua
local framework = AcceptanceFramework.new(gameSpec)
framework:RegisterCheck("asset_loading", CheckAssetLoading)
framework:RegisterCheck("interactions", CheckInteractionsReachable)
framework:RegisterCheck("rig_attachments", CheckRigAttachments)
framework:RegisterCheck("tunables", CheckTunablesMatch)
framework:RegisterCheck("new_player_fairness", CheckNewPlayerFairness)
-- New roles add custom checks
framework:RegisterCheck("vfx_performance", CheckVFXPerformance)  -- Example
local results = framework:RunAll(context)
```

**Core Checks:**
1. **Asset Loading** - Every animation/sound/mesh/image declared in spec loads and takes effect
2. **Interactions** - Every interactive element responds to real player input (raycast/touch/prompt/click), never server function calls
3. **Rig Attachments** - Every tool/accessory/attached object correct on R15 rig
4. **Tunable Conformance** - Measured gameplay stats match spec targets within tolerance
5. **New-Player Fairness** - Fresh player survives spec-defined grace window, can reach core loop

---

## Testing Instructions

### Quick Validation (Runnable Now):
```bash
cd /workspace

# 1. Validate role system
uv run scripts/roles.py validate
# ✓ All 8 roles valid

# 2. Test setup resolver
uv run scripts/setup.py --self-check
# ✓ Self-check passed, all 8 roles active

# 3. Validate example spec
python3 -c "import json,jsonschema; jsonschema.validate(json.load(open('skills/game-spec/example.game-spec.json')), json.load(open('skills/game-spec/schema.json'))); print('✓ valid')"
# ✓ valid

# 4. Test gate validator (on a game with spec)
python3 scripts/validate-spec-gates.py <slug>
# ✓ All gate checks passed (or lists missing artifacts)

# 5. Test MCP healing (safe)
bash scripts/heal-mcp-session.sh
# ✓ MCP sessions restarted
```

### Full Integration (When Building a Game):
1. **Lead Setup Flow:** Follow `SETUP_SYSTEM.md` (auto-detect → manual steps → questions → resolve → welcome → gate)
2. **Playtest with Framework:** Lead runs `AcceptanceFramework:RunAll()` via `execute_luau` (Server) before report
3. **Pre-Ship Validation:** Run `validate-spec-gates.py` to ensure all DONE items have gate records

---

## Commit History (Small Pushes - 10 Commits)

1-4: Extensibility, new roles, setup system, animation planning  
5. **957cd04** - Asset loading guards, MCP healing, Lead PLAY control (Failures 1, 6, 7)  
6. **9933619** - Builder reachability and grip verification (Failures 2, 3)  
7. **6b5a612** - Gate validator and tunable measurement (Failures 4, 5)  
8. **8273730** - Lessons to Rules documentation (CONTRIBUTING.md)  
9. **0c9e0c6** - Final comprehensive report  
10. **a4cf141** - **CORRECTION:** Reframe as general, game-agnostic rules (owner feedback)

---

## Documentation

- **`CONTRIBUTING.md`** - "Lessons to Rules" section with complete table, pattern guide, and note about stating general failure classes
- **`FINAL_REPORT.md`** - This updated report with general rules
- **`SETUP_SYSTEM.md`** - Setup flow and Lead execution guide
- **Each skill/role** - Updated with general, game-agnostic REQUIRED rules

---

## Pull Request

**PR #5:** https://github.com/anishsrinivasa/grok-studio/pull/5  
**Branch:** `cursor/extensible-roles-setup-df5f`  
**Status:** ✅ Ready for review (corrected with general rules)  
**Description:** Will be updated with corrected general rules

---

## Summary

✅ **All 7 playtest failure classes fixed** with **general, game-agnostic rules**, reusable patterns, and automated checks  
✅ **Rules stated as failure classes**, not specific symptoms (per owner correction)  
✅ **Framework is generic and extensible**, driven by `game-spec.json`  
✅ **No hardcoded defaults** (e.g., grace windows are spec-defined, genre-specific)  
✅ **Small commits** (10 total) preserving work across interruptions  
✅ **All validators pass** (roles, setup, spec, gates)  
✅ **Ready for integration** - scripts runnable, documentation complete

The "Lessons to Rules" pattern is established with the correct principle: rules must be general failure classes that apply to all games and genres, never specific symptoms.
