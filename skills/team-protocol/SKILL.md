---
name: team-protocol
description: Shared operating rules for the grok-studio bot team (Lead, Designer, Animator, Builder, Coding) building one Roblox game together - workspace layout, who may edit which part of the Studio place and of game-spec.json, locks for play mode and spec writes, the handoff/report message format, and how files reach the user's PC. Load it before doing any grok-studio work as a team member, and whenever you are unsure whether you may touch something.
---

# Team protocol

Five specialists share **one Roblox Studio** (on the user's PC, behind the bridge), **one
cloud computer** (`/workspace`), and **one `game-spec.json`**. These rules keep them from
breaking each other's work. They apply to Grok Bots (each role is its own Bot) and to
subagents (Claude Code / Cursor / Grok Build), where "message" means "your final report".

| Bot | Grok Bot name | Owns | Main skills |
|---|---|---|---|
| Lead | Lead GrokBot | the spec, scheduling, play mode, the final gate, the user's PC | `grok-studio`, `game-spec`, `playtest-loop`, `connect-studio` |
| Coding | Coding GrokBot | all scripts | `roblox-code` |
| Designer | Designer GrokBot | all UI, icon and thumbnails | `roblox-ui`, `thumbnail-and-icon` |
| Builder | Builder GrokBot | the world and every 3D model (Studio and Blender) | `roblox-building`, `blender-assets` |
| Animator | Animator GrokBot | rigs and animations | `roblox-animations` (+ `blender-assets` for rigs) |

## 1. Workspace layout (cloud computer)

```
/workspace/grok-studio/
  current-game              one line: the slug of the game being built
  .bridge.json              live bridge session (Lead writes it; mode 600; see section 7)
  plugin/                   this plugin's files (setup links or downloads them here)
  .tools/                   shared installs (headless Blender lives here)
  games/<slug>/
    game-spec.json          THE source of truth
    locks/                  section 4
    blender/<id>.blend      one .blend per asset or rig - never two writers on one file
    blender/<id>/           its checkpoints (NN_<label>.blend) and job_*.py scripts
    exports/<id>.fbx        exported meshes / animations
    renders/                previews and marketing renders
    reports/                playtest reports, <id>_import.json gate results, long handoff notes
    marketing/              icon-512.png, thumb-<n>.png
```

`/workspace` is durable and every Bot can read it; temp dirs are not. Never write secrets
(API keys) into it, except the short-lived bridge session file (section 7). Secrets the
user saves in Grok Bot reach the shell as environment variables:
`ROBLOX_OPEN_CLOUD_API_KEY`, `ROBLOX_CREATOR_USER_ID` or `ROBLOX_CREATOR_GROUP_ID`.

Read the slug from `current-game`, then always use absolute paths. Subagents running on
the user's own PC use `<project>/grok-studio/games/<slug>/` with the same layout.

## 2. Studio ownership - write only your own subtree

Everyone may **read** anything. You **write** (create, edit, destroy, reparent) only here:

| Owner | Studio subtrees |
|---|---|
| Coding | `ServerScriptService`, `ReplicatedStorage.Shared` (except `AnimationIds`), `StarterPlayer` |
| Designer | `StarterGui`, `ReplicatedStorage.Assets.UI` |
| Builder | `Workspace` (map, spawn, tagged gameplay parts), `Lighting`, `Terrain`, `ReplicatedStorage.Assets.Models`, `ServerStorage.Templates` |
| Animator | `ReplicatedStorage.Shared.AnimationIds` (ModuleScript: name -> `rbxassetid://`), `ReplicatedStorage.Assets.Rigs`, `ServerStorage.RBX_ANIMSAVES` |
| Lead | `ServerStorage.GameSpec` (spec mirror), play mode, nothing else |

Need a change in someone else's subtree (a new tag on a part, a new remote, a new UI hook)?
Send them an `ASK` (section 5). Do not "just quickly fix it". Gameplay objects are found
by **CollectionService tags** (from the spec), so Builder places tagged parts and Coding
finds them by tag - neither edits the other's instances.

Every Studio builder you run must be **idempotent** (find-or-create by name, never
duplicate) and must touch only your subtree. Never `Destroy()` or `ClearAllChildren()`
on a container you do not own. Never call `ChangeHistoryService` undo/redo, and never
ask the user to press Ctrl+Z: undo history is shared by all Bots and by the user.

Every Studio tool call takes `studio_id`: use `build.studioId` from the spec. Never pick
a different Studio window on your own. If the id stops working (Studio restarted), tell
the Lead.

## 3. Spec ownership

| Owner | Writes these parts of `game-spec.json` |
|---|---|
| Lead | `meta`, `pitch`, `coreLoop`, `mechanics`, `progression`, `monetization`, `world`, `audio`, `acceptanceTests`, `build` (except your own task entries), `marketing.description` |
| Coding | `scripts[]`, `remotes[]`, `dataModel` |
| Designer | `ui`, `marketing.icon`, `marketing.thumbnails` |
| Builder | `assets` |
| Animator | `animations[]` |

Anyone may update **their own** entry in `build.tasks[]` (status, notes). If you think
something outside your parts is wrong, `ASK` the Lead. Never rewrite the whole file from
memory: read it, change only your fields, write it back, validate it (see `game-spec`).
Do the read-modify-write while holding the `spec` lock.

## 4. Locks

A lock is a directory created atomically with `mkdir` (it fails if it already exists).

```bash
G=/workspace/grok-studio/games/$(cat /workspace/grok-studio/current-game)
lock()   { mkdir "$G/locks/$1.lock" 2>/dev/null && echo "$2 $(date -u +%FT%TZ) ${3:-600}" > "$G/locks/$1.lock/owner"; }
unlock() { rm -rf "$G/locks/$1.lock"; }
holder() { cat "$G/locks/$1.lock/owner" 2>/dev/null || echo free; }
# usage: lock spec Builder 60 || { holder spec; sleep 5; }   ...edit...   unlock spec
```

The owner line is `<who> <ISO time> <ttl seconds>`. A lock older than its TTL is stale:
tell the Lead, who may break it. Do not break other locks yourself.

| Lock | Who takes it | Meaning |
|---|---|---|
| `studio-play` | **Lead only** (and `/setup-bridge` during its readiness gate) | Studio is in play mode. **Nobody edits Studio while it exists.** Edits made during play are lost when play stops, and starting play kicks everyone into the play DataModel. |
| `spec` | anyone, held < 1 minute | one writer on `game-spec.json` at a time |

Before **every** Studio write: check `holder studio-play`. If it isn't `free`, wait for
the Lead's `PLAY OFF` message instead of editing. Specialists never call `start_stop_play`.
To check your own work at runtime, `ASK` the Lead for a playtest. Edit-mode checks you
may run yourself: `execute_luau` (Edit), `inspect_instance`, `screen_capture` (Edit view),
`script_read`, the require-check.

## 5. Messages

Bots message each other directly (Grok Bot: a direct message to the other Bot by name;
the receiving Bot wakes up and handles it). Keep one owner per task. Every message starts
with a tag line so the receiver knows what it is:

```
[GS] TASK #12 Lead -> Builder
game: lava-leap   spec: /workspace/grok-studio/games/lava-leap/game-spec.json
do: build the 3 lava-jump stages and place the Coin/Lava/Checkpoint-tagged parts
spec refs: world, assets.items[stage1..stage3], mechanics[coins]
inputs: -
done when: every listed item is status "placed", tags match the spec, Edit-mode screenshot taken
reply with: DONE #12 or BLOCKED #12
```

| Tag | From -> to | Content |
|---|---|---|
| `TASK #n` | Lead -> specialist | one job: what, spec refs, inputs, done-when |
| `DONE #n` | specialist -> Lead | 3-6 lines: what changed (Studio paths, files), spec fields updated, open issues |
| `BLOCKED #n` | specialist -> Lead | what is missing, who could unblock it, what you tried |
| `ASK #n` | anyone -> anyone | a question or a request in the receiver's subtree; the receiver answers `ANSWER #n` |
| `PLAY ON` / `PLAY OFF` | Lead -> all | play-mode lock taken / released |
| `FIX #n` | Lead -> owner | a playtest failure in your area, with the evidence (console lines, screenshot) |

Task numbers come from `build.tasks[]` (the Lead creates them). Handoff texts are
text-only in groups. To send an image (a render, a screenshot) message the Bot directly
or put the file under `renders/` and send the path. Do not chat: no thanks, no status
pings. Report when the task is done or blocked, or when you need something.

## 6. Doing a task

0. **Health check first.**
   - `python3 <plugin>/scripts/bridge-check.py` checks the bridge from the cloud computer
     in about 1 s. It runs no PC command, so no approval is needed. It already retries
     transient errors, and prints `{"bridge": "up"|"down", ..., "fix": ...}`.
   - Then call `get_studio_state` with `build.studioId`.
   - If the task needs Blender, also run
     `bash <plugin>/skills/blender-assets/reference/cloud_blender.sh version`.
   - **Transient errors** (`fetch failed`, timeouts, 502/503/504, "session not found"):
     retry with backoff, 2 s, 5 s, 15 s, 30 s, before calling it a failure. Apply the
     same retry to any Studio call mid-task.
   - **Still down: heal it yourself** (any Bot; `connect-studio` > Heal):
     1. `python3 <plugin>/scripts/bridge-check.py --studio`
     2. If it's down, restart the bridge on the PC. This is the one PC command every Bot
        may run, and the user approves it like any local command:
        - Windows: `powershell -NoProfile -ExecutionPolicy Bypass -File "%USERPROFILE%\grok-studio\bridge\start-bridge.ps1" restart -JsonOutput`
        - macOS/Linux: `bash ~/grok-studio/bridge/start-bridge.sh restart --json-output`
     3. If the printed line's `api_key` or `studio_url` differs from `.bridge.json`, write
        the line there (mode 600) and update the `roblox-studio` connector in place.
     4. Re-check: `python3 <plugin>/scripts/bridge-check.py --studio --wait 30`.
     5. Still failing: send `BLOCKED #n: health <error> <fix>` to the Lead, and don't loop.
        A PC that is asleep or off, or Studio closed, needs the user, and the Lead asks
        them.
1. Read the task and the spec refs. Check `holder studio-play` before any Studio write.
2. Mark your task `in-progress` in `build.tasks[]` (under the `spec` lock).
3. Work in small verified steps (write, then read back or inspect).
4. Update your spec fields and set the task to `done` or `blocked`.
5. Send `DONE #n` / `BLOCKED #n` to the Lead.

If a task is too vague to finish, decide sensibly, record the decision in your `DONE`
message, and move on. Do not wait for the user unless the Lead asks you to.

## 7. The user's PC (Lead only)

Only the Lead, and the Bot running `/setup-bridge` in the user's chat, run commands on the
user's PC. That's local execution: the user approves each command. The bridge
(`connect-studio`) runs there as a background service and exposes Studio and a small file
drop. Its session details are in `/workspace/grok-studio/.bridge.json`, written by
`connect-studio`:
- bridge fields: `api_key`, `studio_url`, `files_url`, `pc_drop_dir`, `pc_http_base`,
  `tunnel`, `tunnel_stable`, `pc_os`
- added by `/setup-bridge`: `studio_id`, `place_id`, `place_name`, `creator_user_id`

A gateway restart drops open MCP sessions. If a Studio call suddenly fails with "session
not found" or a 404, that is a transient error: retry it.

To get a file from the cloud computer onto the user's PC (a texture for `upload_image`,
an image for `store_image`, an FBX for the Importer), any Bot runs:

```bash
python3 <plugin>/scripts/send-to-pc.py <file> [dest/relative/path]
# prints JSON: {"localPath": "C:\\Users\\...\\grok-studio\\drop\\...", "httpUrl": "http://127.0.0.1:8766/...", "bytes": N}
```

`<plugin>` is `/workspace/grok-studio/plugin` on Grok Bot (created by
`setup-bridge`). On a local agent, it is the folder that holds this plugin's `skills/`
directory. `localPath` is valid on the PC (use it for `store_image`).
`httpUrl` is reachable **from Studio only** (use it for `upload_image`). The api key in
`.bridge.json` lets anyone run code in the user's Studio: never print it, never put it in
a message, never copy it anywhere else. It stops working when the user stops the bridge.

## 8. Escalation

Tell the Lead (not the user) when you're blocked. The Lead decides whether the user must
act: publish, enable API access, import a file by hand, approve spending. Specialists never
publish, never change game settings, never spend Robux, and never insert Creator Store
assets without inspecting their scripts (see `roblox-building`).
