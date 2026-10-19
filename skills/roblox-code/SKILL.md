---
name: roblox-code
description: Writes the game's Luau code into Roblox Studio through the Studio MCP - server/client architecture, typed --!strict modules, RemoteEvents with server-side validation and rate limits, DataStoreService persistence with pcall and retries, CollectionService-driven gameplay, and anti-exploit basics. Use when implementing or fixing Roblox scripts from game-spec.json, or whenever writing Luau for a Roblox place.
---

# Roblox code (Luau)

Implement every entry in `game-spec.json` -> `scripts[]` inside Studio, honoring
`mechanics[]`, `remotes[]`, `progression`, and `dataModel`. Reference implementations live in
`reference/` next to this file - adapt them, don't reinvent them:

| File | Put it at | Class |
|------|-----------|-------|
| `reference/Remotes.luau` | `ReplicatedStorage.Shared.Remotes` | ModuleScript |
| `reference/RateLimiter.luau` | `ServerScriptService.Server.Util.RateLimiter` | ModuleScript |
| `reference/DataService.luau` | `ServerScriptService.Server.Services.DataService` | ModuleScript |
| `reference/Main.server.luau` | `ServerScriptService.Server.Main` | Script |

Also follow `rules/roblox-luau.mdc` (style + conventions).

**Team mode (`team-protocol`):** Coding owns `ServerScriptService`,
`ReplicatedStorage.Shared` (except `Shared.AnimationIds`, which is Animator's) and
`StarterPlayer`. Your first task is the skeleton, so the others can build against it:
the folders below, `Shared.Config`, `Shared.Remotes`, `Shared.Tags` (one constant per
CollectionService tag in the spec, e.g. `Tags.Coin = "Coin"`), `Server.Main`,
`ClientMain`, and a placeholder `Shared.AnimationIds` (`return {}`) that Animator then
takes over. UI controllers use Designer's element names exactly. Animations play by name
through `Shared.AnimationIds`. Never start or stop play yourself; `ASK` the Lead.

## Procedural / tween fallback animation

When you animate something in code instead of (or as a fallback for) an Animator clip
(an `AnimationIds` entry is missing or `LoadAnimation` fails, a viewmodel kick, a bobbing
pickup, a door, a camera shake), it must meet the **same exaggerated standard** as
`roblox-animations` > Motion style (required). Subtle fallback motion reads as broken.

- **Copy the Animator's numbers** when the clip exists (spec `animations[].trigger`/`notes`):
  same amplitudes, timings and overshoot, so the fallback looks like the clip.
- **Visible amplitude:** held weapon recoil **15-25 deg pitch up and 0.3-0.6 studs back**;
  sub-parts (lever, slide, mag) >= 0.25 studs or 20 deg; character limbs move through large
  arcs (>= 60 deg for actions). Default durations: fire 0.2-0.35 s, reload 1.5-2.2 s, equip
  0.4-0.6 s, idle sway a 2-4 s loop.
- **Shape it as keys, not one tween:** chain tweens/springs as anticipation (if allowed) ->
  fast kick (0.03-0.06 s, `Enum.EasingStyle.Quint`/`Cubic` Out) -> eased return -> overshoot
  past rest -> settle (`Back` or `Elastic` Out). Lag child parts 0.03-0.1 s behind the
  parent (follow-through), move on arcs (offset a mid point), add secondary motion (sway,
  wobble). **Never `Enum.EasingStyle.Linear`** for visible motion.
- **Per-frame (`RenderStepped`/`BindToRenderStep`) motion:** use a spring or a
  frame-rate-independent lerp (`1 - math.exp(-k * dt)`) that overshoots and settles, and
  sum the offsets (recoil + sway + bob) onto the base CFrame, so they don't fight each other.
- **Timing:** if gameplay needs the action faster or slower, scale the whole sequence's time
  by `clipLength / gameplayDuration`; don't cut amplitude or skip the overshoot/settle.
- **Characters are R15** unless the spec says R6: address R15 joints (`UpperTorso`,
  `RightUpperArm`, ...) by name and don't assume R6 parts (`Torso`, `Right Arm`).
- In your `DONE`, list the fallback's peak amplitudes and timings so the Lead can check them
  against the Animator's clip.

## Canonical layout

```
ReplicatedStorage
  Shared/                 ModuleScripts used by both sides (Config, Remotes, Types, pure utils)
  Assets/                 Templates cloned at runtime (models, VFX, sounds)
  Remotes/                (created at runtime by Shared.Remotes on the server)
ServerScriptService
  Server/
    Main                  Script - the ONLY server entry point
    Services/             ModuleScripts with start(): DataService, <Mechanic>Service ...
    Util/                 RateLimiter, validation helpers
ServerStorage
  GameSpec                ModuleScript mirror of game-spec.json (see orchestrator)
  Templates/              Server-only templates (never replicated to clients)
StarterPlayer
  StarterPlayerScripts/
    ClientMain            LocalScript - the ONLY client entry point
    Controllers/          ModuleScripts with start(): HudController, InputController ...
StarterGui                ScreenGuis (built by roblox-ui)
Workspace                 Map + tagged gameplay objects
```

Single entry point per side keeps start order deterministic and makes the playtest
require-check trivial.

## Writing scripts through Studio MCP

Studio MCP tools (official docs: https://create.roblox.com/docs/studio/mcp). Every call
needs `studio_id` (from `list_roblox_studios`).

1. **Create the container with the right class first** - `multi_edit` creates a script if
   the path is missing, but don't rely on it choosing Script vs LocalScript vs
   ModuleScript. Run `execute_luau` with `datamodel_type: "Edit"`:
   ```lua
   local function ensure(parent: Instance, name: string, className: string): Instance
       local inst = parent:FindFirstChild(name)
       if inst and inst.ClassName ~= className then inst:Destroy(); inst = nil end
       if not inst then
           inst = Instance.new(className)
           inst.Name = name
           inst.Parent = parent
       end
       return inst
   end
   local SSS = game:GetService("ServerScriptService")
   local server = ensure(SSS, "Server", "Folder")
   ensure(server, "Services", "Folder")
   ensure(server, "Util", "Folder")
   ensure(server, "Main", "Script")
   return "ok"
   ```
2. **Write the source** with `multi_edit` (path like
   `game.ServerScriptService.Server.Services.CoinService`, `datamodel_type: "Edit"`).
   For a brand-new script, a single edit replacing the whole (empty) content is fine.
3. **Read back** with `script_read` and fix anything truncated or mangled.
4. **Require-check** (cheap compile/run test) in Edit mode:
   ```lua
   local results = {}
   for _, d in game:GetService("ReplicatedStorage").Shared:GetDescendants() do
       if d:IsA("ModuleScript") then
           local ok, err = pcall(require, d)
           table.insert(results, (ok and "OK  " or "ERR ") .. d:GetFullName() .. (ok and "" or (": " .. tostring(err))))
       end
   end
   return table.concat(results, "\n")
   ```
   Server-only modules that touch `Players`/DataStores at require time may misbehave in Edit;
   keep side effects inside `start()` so requiring is always safe.
   `require` caches per ModuleScript in the Edit session. After editing a module, require a
   fresh `d:Clone()` (parented to the same place, then destroyed) to make sure you test the
   new source.
5. Update `scripts[].status` to `written` in the spec. `verified` is set by `playtest-loop`.

Use `script_search` / `script_grep` before writing, to avoid duplicating something that
already exists in the place.

### Optional: Rojo file sync

If the user works in a local repo with [Rojo](https://rojo.space), write `.luau` files to
`src/` (`*.server.luau` = Script, `*.client.luau` = LocalScript, other = ModuleScript) and let
`rojo serve` sync them; still use Studio MCP for playtesting. Don't mix: if Rojo manages a
folder, never `multi_edit` scripts inside it (Rojo will overwrite them).

## Conventions (non-negotiable)

- `--!strict` at the top of every script. Type function signatures and module exports.
- `game:GetService("X")` at the top; never index `game.X` for services.
- `task.wait/spawn/defer/delay`, never `wait/spawn/delay`.
- String interpolation `` `{x}` `` over concatenation in new code.
- Modules return a table; side effects only in `start()`.
- Tunables live in `ReplicatedStorage.Shared.Config` generated from
  `mechanics[].tunables` - no magic numbers in services.
- Gameplay objects are found by `CollectionService` tag (`GetTagged` +
  `GetInstanceAddedSignal`) so assets can be swapped without code changes.
- Clean up connections on `Players.PlayerRemoving` and when instances are destroyed
  (store `RBXScriptConnection`s, call `:Disconnect()`), avoid per-frame `Instance.new`.
- Use `Attributes` (`SetAttribute`) for simple replicated per-instance state; leaderstats
  for scoreboard values.

## Networking and anti-exploit basics

The client is hostile. Assume every RemoteEvent argument is attacker-controlled.

- **Server authority:** currency, score, inventory, damage, unlocks, teleports, and cooldowns
  are computed and stored on the server only. Clients send *intent* ("RequestUnlock",
  "Activate"), never *results* ("AddCoins(100)").
- **Validate every argument:** `typeof` checks, ranges, NaN/inf (`x ~= x`), string length,
  that referenced instances exist and are tagged, that the player owns what they use.
  ```lua
  RequestUnlock.OnServerEvent:Connect(function(player: Player, stageId: unknown)
      if not limiter:allow(player) then return end
      if typeof(stageId) ~= "string" or #stageId > 32 then return end
      local unlock = Config.Unlocks[stageId]
      if not unlock then return end
      local profile = DataService.get(player)
      if not profile or profile.unlocked[stageId] then return end
      -- check prerequisites and cost, then mutate profile and replicate
  end)
  ```
- **Distance/sanity checks** for touch- or proximity-driven actions: verify the character
  is near the target on the server (`(hrp.Position - part.Position).Magnitude < N`).
  Prefer server-side `Touched` handlers or `ProximityPrompt.Triggered` (fires on the
  server) over client-reported touches.
- **Rate-limit** every client->server remote (`reference/RateLimiter.luau`), using
  `remotes[].rateLimitPerSecond`.
- **No RemoteFunction invoked server->client** (`InvokeClient`) - a client can yield
  forever. Server->client is always a RemoteEvent.
- Never trust client-provided `Player` arguments - the first parameter of
  `OnServerEvent` is the real sender.
- Don't put secrets or admin logic in ReplicatedStorage/StarterPlayer (clients can read
  all of it). Server-only code lives in ServerScriptService/ServerStorage.
- Physics: keep important parts anchored or server-owned (`SetNetworkOwner(nil)`) when
  clients shouldn't be able to move them.

## Persistence (DataStoreService)

Use `reference/DataService.luau` as the base. Requirements:
- All DataStore calls in `pcall` with retries and exponential backoff.
- Never save defaults over real data after a failed load (the reference tracks
  `loadedOk`).
- `UpdateAsync` for saves; autosave every ~2 minutes; save on `PlayerRemoving` and in
  `game:BindToClose`.
- Version the store name and `schemaVersion`; reconcile old profiles with the template.
- Studio: DataStores only work when **Game Settings > Security > Enable Studio Access to
  API Services** is on and the place is published. Do not toggle this yourself - tell the
  user. The module must degrade gracefully (no persistence) when unavailable.
- Respect limits; keep one key per player and avoid saving in tight loops. See
  https://create.roblox.com/docs/cloud-services/data-stores (limits change; check the
  page if you plan heavy usage).

## Definition of done for this stage

- Every `scripts[]` entry exists at `parentPath` with the right class and is `written`.
- Require-check returns no `ERR` lines; `get_console_output` shows no new errors.
- Every `remotes[]` entry is created by `Shared.Remotes` and has validation + rate limit.
- Checkpoint recorded in `build.checkpoints`.
