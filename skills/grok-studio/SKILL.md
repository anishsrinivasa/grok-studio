---
name: grok-studio
description: Orchestrates building a complete, playable Roblox game from a single prompt - spec, Luau code, UI, Blender models and animations, playtest-and-fix loop, thumbnail and icon. Use when the user asks to "make/build/one-shot a Roblox game", or wants an end-to-end Roblox build rather than a single script or asset.
---

# Roblox One-Shot (orchestrator)

You are the build lead. Turn one prompt into a published-ready Roblox place by running the
stage skills below **in order**, keeping `game-spec.json` as the single source of truth, and
refusing to call the game "done" until the final playtest gate passes.

## Stage map

| # | Stage | Skill | Output | Required connector |
|---|-------|-------|--------|--------------------|
| 0 | Preflight | (this skill) | connector report, `build.connectors` | - |
| 1 | Spec | `game-spec` | `game-spec.json` (validated) | none |
| 2 | Code | `roblox-code` | scripts in Studio, `scripts[].status = written` | Studio |
| 3 | UI | `roblox-ui` | ScreenGuis in StarterGui | Studio (+ Figma optional) |
| 4 | Assets | `blender-assets` | MeshParts placed in Workspace | Studio (+ Blender optional) |
| 5 | Animations | `roblox-animations` | Animation IDs wired in code | Studio (+ Blender optional) |
| 6 | Playtest | `playtest-loop` | report, all `acceptanceTests` pass | Studio |
| 7 | Marketing | `thumbnail-and-icon` | `marketing/icon-512.png`, `marketing/thumb-*.png` | Studio or Blender |

Stages 3-5 may run in any order once Stage 2's skeleton exists, but Stage 6 always runs last
before Stage 7, and re-runs after any later change to code.

## Stage 0 - Preflight (do this before anything else)

1. **Detect connectors by trying them, not by assuming.** Tool names below are from the
   official docs (Oct 2026); your client may prefix them (e.g. `roblox-studio_...`).
   - Studio: call `list_roblox_studios`. If it fails or returns nothing, Studio is not
     connected. If you are a **remote agent** (e.g. Grok Bot), run the `/setup-bridge`
     skill first — it will start the bridge on the user's PC, open a tunnel, and register
     the Studio and Blender connectors automatically, then return here. If you are a
     **local agent** (Cursor, Claude Code on the same PC), tell the user: open Roblox
     Studio with a place, then **Assistant > ... > Manage MCP Servers > Enable Studio as
     MCP server**. Studio is **mandatory** — stop here without it.
   - Pick the target Studio instance: if more than one is listed, ask which (or match the
     place name). Store its id as `build.studioId`; **every** Studio tool call takes
     `studio_id`.
   - Call `get_studio_state`. If it is in play mode, stop play (`start_stop_play`) before
     editing.
   - Blender: call `get_addon_status` (mcp-for-blender). Unavailable => assets/animations fall
     back to Studio generation (`generate_mesh`, `generate_procedural_model`, primitives) and
     Studio's Animation Editor keyframes via Luau.
   - Figma: call `whoami`. Unavailable, unauthenticated, or on a seat that can't write =>
     UI uses the Studio-direct path. Never block on Figma.
2. Record results in `build.connectors` and tell the user in one short message what will be
   used and what falls back.
3. **Safety check:** confirm the open place is a scratch/new place or that the user accepts
   edits. Suggest File > Save to File (a `.rbxl` backup) before Stage 2. Never publish,
   change game settings, enable API services, or spend Robux without explicit permission.

## The single source of truth: `game-spec.json`

- Lives in the user's project folder (repo root or the folder they name). Remote agents that
  have no shared filesystem with the user's PC keep it in their own workspace **and** mirror
  it into Studio as a `ModuleScript` at `game.ServerStorage.GameSpec` (source:
  `return [==[ <json> ]==]`) so the spec travels with the place.
- Every stage **reads** the spec first and **writes back** statuses (`scripts[].status`,
  `ui.screens[].status`, `assets.items[].status`, `animations[].status`,
  `acceptanceTests[].status`) and IDs (`assetId`, `instancePath`).
- If a later stage discovers the spec is wrong (e.g. a mechanic is unbuildable), edit the
  spec first, note the change in `meta.assumptions`, then continue. Code must never silently
  diverge from the spec.
- Validate against `skills/game-spec/schema.json` after every write.

## Checkpoints (after every stage)

After each stage:
1. Append to `build.checkpoints`: `{ "stage", "at" (ISO time), "summary", "openIssues" }`
   and set `build.stage` to the next stage.
2. Run a cheap smoke check: `get_console_output` should show no new errors after an Edit-mode
   `execute_luau` that `require`s every ModuleScript written so far (see `playtest-loop`).
3. Ask the user to save the place (Ctrl+S / File > Save to File) - you cannot rely on
   Studio autosave. If a tool exists to save in your client, use it.
4. Post a 3-5 line progress note to the user. Do **not** wait for approval between stages
   unless something needs a decision (monetization, publishing, deleting user content,
   ambiguous genre).

## Execution rules

- **Small, verifiable steps.** Write one script or one UI screen at a time, then read it
  back (`script_read`) or inspect it (`inspect_instance`) before moving on.
- **Prefer Luau over clicking.** Build instances with `execute_luau` (datamodel_type `Edit`);
  write script source with `multi_edit`. Make scripts idempotent: re-running a builder must
  not duplicate instances (find-or-create by name).
- **Tag, don't hard-code paths.** Gameplay objects get `CollectionService` tags
  (e.g. `Coin`, `Lava`, `Checkpoint`) so code and assets can be built independently.
- **Budget awareness.** Keep each Studio tool call output small (filter `search_game_tree`
  by path/type, limit depth).
- **No secrets in the place.** Never write API keys into scripts. Open Cloud keys stay in the
  agent's environment and are used only from outside Roblox.
- **Content standards.** Keep everything within Roblox Community Standards; no real-brand
  logos or copyrighted characters unless the user owns them.

## Final playtest gate (definition of done)

The game is done only when **all** are true (run the `playtest-loop` skill):
- Zero errors in `get_console_output` across Edit-mode require-check, a server+client
  playtest start, and the full acceptance run. Warnings are listed in the report.
- Every `acceptanceTests[]` item is `pass`.
- The core loop was completed end-to-end at least once via simulated input
  (`character_navigation`, `user_keyboard_input`, `user_mouse_input`).
- Every `ui.screens[]` is `verified` with a `screen_capture` at a phone-like and a desktop
  viewport (or explicitly noted as not checkable).
- Every MeshPart is under 20,000 triangles and every `assets.items[]` is `placed`.
- Persistence (if enabled) loads defaults in Studio without crashing even when API access
  is off (DataStore calls are wrapped in `pcall`).

If the gate fails after the playtest skill's max iterations, stop, set `build.stage` to
`playtest`, and give the user the report with the remaining failures - do not claim success.

## Final handoff message

Summarize: title + pitch; what was built (scripts, screens, assets, animations); files
produced (`game-spec.json`, `marketing/*`); connectors used/fallbacks; the playtest report
summary; and **manual steps left for the user** (save, publish via File > Publish to Roblox,
enable Studio Access to API Services for DataStores in Game Settings > Security, upload
icon/thumbnails in Creator Dashboard, set maturity questionnaire).
