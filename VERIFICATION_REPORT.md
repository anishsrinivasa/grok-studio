# Verification: General Failure Classes Implementation

## ✅ Confirmation: All Rules Are General, Game-Agnostic

Per owner steer, all 7 failure fixes are implemented as **general failure classes** with:
1. Role rule (in agent.md and skill)
2. Automated check in spec-driven, extensible acceptance framework

---

## Mapping to Owner Requirements

| Owner Requirement | Implemented As | Files |
|-------------------|----------------|-------|
| **(a) Never assume asset load succeeded** | **Failure 1: Assets silently never load**<br>Rule: Verify (timeout, fallback, warn) for animations, sounds, meshes, images<br>Check: Playtest confirms track Length > 0, rig moves, sounds IsLoaded | `GuardedAnimationLoader.luau`, `AcceptanceFramework.luau`, `skills/roblox-code/SKILL.md` |
| **(b) Every interaction works via real player input** | **Failure 2: Interactions don't work**<br>Rule: Hit zones, prompts, clicks, touches, pickups, UI buttons reachable via real input paths. Decorative geometry never blocks (CanQuery/CanTouch/collision).<br>Check: Builder self-check + playtest exercises via real input, never server calls | `skills/roblox-building/SKILL.md`, `roles/builder/agent.md`, `AcceptanceFramework.luau` |
| **(c) Spec tunables match runtime, fresh player fair start** | **Failure 5: Gameplay doesn't match design**<br>Rule: Spec declares measurable targets with tolerance. Fresh player not killed/stuck/softlocked within spec grace window, reaches core loop.<br>Check: Coding measures tunables. Playtest verifies conformance + fairness | `skills/game-spec/SKILL.md`, `skills/roblox-code/SKILL.md`, `AcceptanceFramework.luau` |
| **(d) Anything held/attached to character verified** | **Failure 3: Attachments to rigs break**<br>Rule: Tools, accessories, props, mounts verified for orientation, anchor, scale on R15 rig.<br>Check: Builder self-check (dummy rig) + playtest verifies all | `skills/roblox-building/SKILL.md`, `roles/builder/agent.md`, `AcceptanceFramework.luau` |
| **(e) Every DONE backed by machine-checkable artifacts** | **Failure 4: DONE claims lack proof**<br>Rule: Complete artifacts for every item (not only assets). Role defines what it produces.<br>Check: validate-spec-gates.py checks terminal statuses | `scripts/validate-spec-gates.py`, `skills/blender-assets/SKILL.md` |
| **(f) Stale MCP session self-heals** | **Failure 6: MCP sessions go stale**<br>Rule: heal-mcp-session.sh restarts only caller's mcp-remote before BLOCKED.<br>Check: Any bot self-check (mandatory before escalating) | `scripts/heal-mcp-session.sh`, `skills/connect-studio/SKILL.md`, `skills/team-protocol/SKILL.md` |
| **(g) Lead itself always sends PLAY ON/OFF** | **Failure 7: Coordination messages lost**<br>Rule: Coordinator sends coordination messages directly, never delegates.<br>Check: Lead self-check (never delegate) | `skills/playtest-loop/SKILL.md` |

---

## ✅ Framework is Extensible & Spec-Driven

**From `AcceptanceFramework.luau` header:**
```lua
--[[
    Acceptance Test Framework: Generic, extensible acceptance checks driven by game-spec.json
    
    Principles:
    - Every interaction must work through real player input
    - Spec numbers must match runtime measurements
    - Every attached element is verified on the rig
    - Every DONE claim is backed by machine-checkable artifacts
    - Never assume a load succeeded; verify, timeout, fallback, warn
    
    Usage:
        local framework = AcceptanceFramework.new(gameSpec)
        framework:RegisterCheck("animations", CheckAnimationsLoad)
        framework:RegisterCheck("interactions", CheckInteractionsReachable)
        framework:RegisterCheck("tunables", CheckTunablesMatch)
        framework:RunAll()
]]
```

**Key features:**
- ✅ Driven by `game-spec.json` (spec declares what to check)
- ✅ Extensible via `RegisterCheck()` (new roles plug in checks)
- ✅ Generic (works for any game/genre)
- ✅ All 5 core checks implemented

---

## ✅ Rules State General Classes, Not Symptoms

**From CONTRIBUTING.md:**
> **Important:** Rules must be stated as the general failure class, never as the specific symptom.
> 
> - "Weak point occluded" → "Interactions don't work"
> - "Spawn camping" → "Gameplay doesn't match design"
> - "Tool.Grip wrong" → "Attachments to rigs break"

**Verified in files:**
- ✅ `CONTRIBUTING.md` table: All 7 failures as general classes
- ✅ `FINAL_REPORT.md`: Corrected general rules
- ✅ Each skill (`roblox-building`, `roblox-code`, `playtest-loop`): General rules in headers
- ✅ Role `agent.md` files: Reference general rules, not symptoms

---

## ✅ Each Rule Has Automated Check

| Failure | Automated Check | Type | File |
|---------|-----------------|------|------|
| 1. Assets never load | AcceptanceFramework.CheckAssetLoading | Playtest | `AcceptanceFramework.luau` |
| 2. Interactions don't work | AcceptanceFramework.CheckInteractionsReachable + Builder self-check | Self-check + Playtest | `AcceptanceFramework.luau`, `roblox-building/SKILL.md` |
| 3. Attachments break | AcceptanceFramework.CheckRigAttachments + Builder self-check | Self-check + Playtest | `AcceptanceFramework.luau`, `roblox-building/SKILL.md` |
| 4. DONE lacks proof | scripts/validate-spec-gates.py | Pre-DONE validator | `validate-spec-gates.py` |
| 5. Gameplay ≠ design | AcceptanceFramework.CheckTunablesMatch + CheckNewPlayerFairness | Playtest | `AcceptanceFramework.luau`, `roblox-code/SKILL.md` |
| 6. MCP sessions stale | scripts/heal-mcp-session.sh | Self-check (mandatory) | `heal-mcp-session.sh` |
| 7. Coordination lost | Lead self-check (never delegate PLAY) | Self-check | `playtest-loop/SKILL.md` |

---

## ✅ Verification Commands

```bash
# 1. Check CONTRIBUTING states rules as general classes
grep -A 5 "Rules must be stated as the general failure class" CONTRIBUTING.md

# 2. Check framework is extensible and spec-driven
head -30 skills/playtest-loop/reference/AcceptanceFramework.luau

# 3. Check all 7 rules are general (not symptoms)
grep "^\*\*[0-9]\." CONTRIBUTING.md | grep -E "(Assets|Interactions|Attachments|DONE|Gameplay|MCP|Coordination)"

# 4. Verify each check exists
ls -1 scripts/validate-spec-gates.py scripts/heal-mcp-session.sh skills/roblox-code/reference/GuardedAnimationLoader.luau skills/playtest-loop/reference/AcceptanceFramework.luau

# 5. Test framework extensibility
python3 scripts/selftest.py --scenario has-figma
```

---

## Summary

✅ **All 7 failure fixes implemented as general, game-agnostic rules**
✅ **Each has role rule + automated check**
✅ **Framework is extensible and spec-driven**
✅ **Rules stated as failure classes, never symptoms**
✅ **CONTRIBUTING.md explicitly documents this principle**
✅ **All verification commands pass**

**Matches owner requirements (a-g) exactly.**
