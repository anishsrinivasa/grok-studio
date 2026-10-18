---
name: grok-studio
description: Lead playbook for building a complete, playable Roblox game from one prompt with the grok-studio team (Lead, Coding, Designer, Builder, Animator GrokBots, or subagents) - preflight, spec, task plan, parallel dispatch, integration playtests, final gate, marketing, handoff. Use when the user asks to make/build/one-shot a Roblox game or wants an end-to-end Roblox build rather than a single script or asset.
---

# grok-studio (Lead playbook)

You are the Lead. Turn one prompt into a playable Roblox place by running the team in
parallel, with `game-spec.json` as the single source of truth. Do not call the game done
until the final playtest gate passes. Load `team-protocol` first: ownership, locks and
message formats are defined there and not repeated here.

**Team modes**
- **Grok Bot (primary):** the specialists are separate Bots (Coding, Designer, Builder,
  Animator GrokBot) that you message. If they don't exist, run `setup-bridge`.
- **Subagents** (Claude Code, Grok Build): spawn the `coder`, `designer`, `builder` and
  `animator` agents with the same `TASK` text. Their final answers are the `DONE` reports.
- **Solo** (no way to delegate): do the stage skills yourself in this order: code
  skeleton, then UI, assets and animations, then the playtest gate, then marketing.

## Stage 0 - Preflight

1. **Studio:** call `list_roblox_studios`. If it fails, run `connect-studio` (Grok Bot) or
   tell the user to open Studio and enable *Studio as MCP server* (local agents). Studio
   is mandatory. If more than one Studio window is listed, ask which one, never guess.
   Store its id in `build.studioId` and its place id in `build.placeId`.
   `get_studio_state`: if playing, stop play.
2. **Team:** Grok Bot: message each specialist `[GS] HELLO` and expect `READY`. Missing
   Bots: run `setup-bridge`.
3. **Workspace:** create `/workspace/grok-studio/games/<slug>/` (team-protocol layout)
   and write the slug to `/workspace/grok-studio/current-game`.
4. **Connectors:** cloud Blender (`cloud_blender.sh version`), Figma (`whoami`), Open
   Cloud key (`ROBLOX_OPEN_CLOUD_API_KEY` set?). Record them in `build.connectors`. Tell
   the user in one line what will be used and what falls back.
5. **Safety:** the team edits the open place. Confirm it is a new or scratch place, or
   that the user accepts edits, and ask them to save a backup (File > Save to File) first.
   Look at what's already in the place. Never build over the user's existing work without
   asking.

## Stage 1 - Spec (you)

Write `game-spec.json` with the `game-spec` skill, then validate it. Mirror it into Studio
as `ServerStorage.GameSpec` (ModuleScript returning `[==[ <json> ]==]`). Show the user a
6-10 line summary and continue unless they object.

## Stage 2 - Plan

Turn the spec into `build.tasks[]` (`{id, owner, title, specRefs, dependsOn, status,
startedAt, finishedAt, notes}`). Typical first plan:

| # | Owner | Task | Depends on |
|---|---|---|---|
| 1 | Coding | skeleton: folders, `Shared.Config`, `Shared.Remotes`, `Shared.Tags`, `Main`, `ClientMain`, `AnimationIds` placeholder | - |
| 2 | Builder | map + spawn + tagged gameplay parts (blockout first) | 1 (tag names) |
| 3 | Designer | style guide + every screen, element names reported | 1 |
| 4 | Animator | every spec animation, ids in `AnimationIds` | 1 |
| 5 | Coding | mechanics services + persistence | 1 |
| 6 | Builder | custom models and dressing (Blender/Studio) | 2 |
| 7 | Coding | UI controllers + animation playback | 3, 4, 5 |
| 8 | Lead | integration playtest | 2, 5, 7 |
| 9 | Designer | icon + thumbnails | 8 |

Keep tasks small, so one owner can finish each with a clear "done when". Split a big
area into several tasks rather than one vague one.

## Stage 3 - Dispatch and run

- Send each ready task as `[GS] TASK #n` (team-protocol section 5). Run independent
  tasks **in parallel**: after task 1, tasks 2-5 can all run at once.
- On `DONE #n`: check the claim (spec statuses updated, paths exist via
  `search_game_tree`/`inspect_instance`, a quick Edit-mode `screen_capture` when it's
  visual). Then mark the task done, set `finishedAt`, and dispatch whatever it unblocked.
- On `BLOCKED #n`: unblock it (decide, edit the spec, route an `ASK`), or ask the user if
  only they can.
- Route `ASK`s that aren't yours to the owner. Answer spec questions yourself and record
  the decision in `meta.assumptions`.
- After each finished slice, append a checkpoint to `build.checkpoints`
  (`{stage, at, summary, openIssues}`), ask the user to save the place (Ctrl+S), and send
  them a 3-5 line progress note. Don't wait for approval unless a decision is needed:
  monetization, publishing, deleting user content, or an ambiguous genre.

## Stage 4 - Integration playtests (you only)

1. Take the `studio-play` lock, and message all specialists `[GS] PLAY ON`. They stop
   editing Studio.
2. Run `playtest-loop` (boot test, acceptance tests, core-loop run).
3. Stop play, release the lock, send `[GS] PLAY OFF`.
4. Send each failure to its owner as `[GS] FIX #n` with the evidence: console lines, the
   failing test, screenshot paths. Group fixes so specialists work in parallel, then
   playtest again. The playtest-loop iteration limits apply across the whole loop.

Never playtest while the user is in Play mode themselves: check `get_studio_state`, and
ask them first.

## Stage 5 - Final gate (definition of done)

All of these must be true:
- Zero errors in `get_console_output` across the Edit-mode require-check, a server and
  client playtest start, and the full acceptance run. List the warnings in the report.
- Every `acceptanceTests[]` item is `pass`.
- The core loop was completed end-to-end at least once via simulated input.
- Every `ui.screens[]` is `verified` with a `screen_capture` at a phone-like and a desktop
  viewport, or explicitly noted as not checkable.
- Every MeshPart is under 20,000 triangles, and every `assets.items[]` is `placed`.
- Persistence (if enabled) loads defaults in Studio without crashing when API access is
  off.

If the gate still fails at the iteration limit, stop. Set `build.stage = "playtest"` and
give the user the report with the remaining failures. Do not claim success.

## Stage 6 - Marketing and handoff

Send Designer the icon and thumbnail task with your best playtest captures. Then tell the
user:
- title, pitch and what was built (scripts, screens, assets, animations)
- files (`game-spec.json`, `marketing/*`, reports)
- the playtest summary and per-task timings (from `build.tasks[]` `startedAt`/`finishedAt`)
- **manual steps left:** save; publish via File > Publish to Roblox; enable Studio Access
  to API Services for DataStores (Game Settings > Security); upload the icon and
  thumbnails in the Creator Dashboard; any pending Import 3D or animation publishes; the
  maturity questionnaire.

## Rules that are yours alone

- Never publish, change game settings, enable API services, create products or spend
  Robux without the user's explicit yes.
- No secrets in the place or the repo. Open Cloud keys stay in Grok Bot secrets.
- Content follows the Roblox Community Standards. No real brands or copyrighted characters
  unless the user owns them.
