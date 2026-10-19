---
name: roblox-audio
description: Sources and wires Roblox game audio (music, UI sounds, gameplay SFX, ambient audio) from the Creator Store, sets up SoundGroups, mixing, 3D spatial audio, and hooks sounds to gameplay events. Use for any audio/sound work in a grok-studio game.
---

# Roblox Audio

Build the audio for every gameplay event, UI interaction, and ambient moment in
`game-spec.json` -> `audio[]` by sourcing sounds from the Creator Store, setting up
SoundGroups and mixing in `SoundService`, and coordinating triggers with Coding.

**Team mode (`team-protocol`):** SFX builds audio templates and owns `SoundService` and
`ReplicatedStorage.Assets.Audio`. Coding triggers them from gameplay code.

## Planning: what sounds does the game need?

Read `mechanics[]`, `world.setting`, `ui.screens[]` and the palette/tone. List:
- **Music**: background loop (gameplay), menu music, victory/defeat stingers
- **UI sounds**: button click, hover, popup open/close, unlock fanfare, purchase confirm
- **Gameplay SFX**: footsteps, coin/pickup, weapon fire/swing/reload, explosion, damage
  grunt, ability cast, door open, checkpoint activated
- **Ambient environment**: wind loop, water ripple, fire crackle, birds/crickets, distant
  thunder

Write each to `audio[]` in the spec:

```json
{
  "id": "coinPickup",
  "purpose": "Coin pickup",
  "source": "creator-store",
  "assetId": "rbxassetid://..."
}
```

`source`: `creator-store` (search and insert), `none` (placeholder for future).

## Sourcing sounds from the Creator Store

Use Studio MCP tools `search_asset` and `insert_asset`.

**Example: coin pickup sound:**

```lua
-- execute_luau Edit
-- search_asset returns {name, assetId, creator} items
local results = search_asset("coin pickup", {assetType = "Audio", limit = 20})
-- Pick one (check creator = "Roblox" for free sounds, or user-uploaded with rights)
-- Insert it:
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local audioFolder = ReplicatedStorage:FindFirstChild("Assets")
if not audioFolder then
  audioFolder = Instance.new("Folder")
  audioFolder.Name = "Assets"
  audioFolder.Parent = ReplicatedStorage
end
local audio = audioFolder:FindFirstChild("Audio")
if not audio then
  audio = Instance.new("Folder")
  audio.Name = "Audio"
  audio.Parent = audioFolder
end

local assetId = 123456789  -- from search results
local sound = insert_asset(assetId, audio)
sound.Name = "CoinPickup"
return "inserted " .. sound.Name
```

**Licensing check:** Roblox-owned audio (creator "Roblox") is free. User-uploaded audio
may have copyright restrictions: only use sounds you have rights to, or public-domain
audio. When in doubt, search for "royalty free" or Roblox-verified sounds.

## SoundGroups and mixing

Create SoundGroups under `SoundService` to control categories (Music, SFX, UI, Ambience),
then parent each Sound to its group and set `SoundGroup.Volume` for relative mixing.

**Example setup:**

```lua
local SoundService = game:GetService("SoundService")

local function getOrCreate(parent, className, name)
  local obj = parent:FindFirstChild(name)
  if not obj then
    obj = Instance.new(className)
    obj.Name = name
    obj.Parent = parent
  end
  return obj
end

local music = getOrCreate(SoundService, "SoundGroup", "Music")
music.Volume = 0.4  -- background, shouldn't drown gameplay

local sfx = getOrCreate(SoundService, "SoundGroup", "SFX")
sfx.Volume = 0.7

local ui = getOrCreate(SoundService, "SoundGroup", "UI")
ui.Volume = 0.8  -- clear and immediate

local ambience = getOrCreate(SoundService, "SoundGroup", "Ambience")
ambience.Volume = 0.3  -- subtle

-- Parent sounds to groups:
ReplicatedStorage.Assets.Audio.CoinPickup.SoundGroup = sfx
```

**3D spatial audio (for sounds in the world):**

```lua
local sound = workspace.Coin.Sound
sound.RollOffMode = Enum.RollOffMode.InverseTapered  -- realistic falloff
sound.RollOffMinDistance = 10  -- full volume within 10 studs
sound.RollOffMaxDistance = 50  -- inaudible past 50 studs
```

- `RollOffMinDistance`: distance where the sound is at full volume
- `RollOffMaxDistance`: distance where the sound is silent
- Use larger values for important sounds (explosions: 30/150), smaller for detail
  (footsteps: 8/40)

**2D sounds (UI, music):** leave `RollOff` settings default, or explicitly set
`RollOffMode = Enum.RollOffMode.Linear` with Min/Max both 0 (though 2D sounds ignore
rolloff anyway).

## Wiring with Coding

You source and organize sounds; Coding triggers them.

**Your `DONE` report lists:**
- Sound paths: `ReplicatedStorage.Assets.Audio.CoinPickup`
- Trigger API: `sound:Play()` or `sound:Stop()`
- Authority: client (player hears it only) or server (everyone hears it)
- Event name: the remote or signal Coding should call it from (e.g. "play CoinPickup on
  client when ReplicatedStorage.Shared.Remotes.CoinPickup fires")

**Coding's side:**
- Clone 2D sounds into `SoundService` or player's `PlayerGui` so they're always audible
- 3D sounds stay in `Workspace` parts (coins, explosions, NPCs)
- For one-shot SFX, clone-play-destroy: `local s = sound:Clone(); s.Parent = ...; s:Play();
  game:GetService("Debris"):AddItem(s, s.TimeLength + 0.1)`
- Music loops: one instance, `sound.Looped = true`, `sound:Play()` at the right moment

## Verify

1. `search_game_tree` filtered to `ReplicatedStorage.Assets.Audio` and `SoundService` to
   confirm paths and SoundGroups exist.
2. Edit-mode test: call `sound:Play()` via `execute_luau` and listen (you may need
   `execute_luau` Server if the sound is in Workspace, or `warn(sound.SoundId,
   sound.TimeLength)` to verify it loaded).
3. Runtime test: `ASK` the Lead for a playtest. Trigger the sound in context (pick up a
   coin, fire a weapon), check volume balance, 3D falloff, and whether it's audible over
   music/ambience.
4. Set `audio[].status` -> `sourced` after inserting, `verified` after the playtest.

## Team protocol compliance

- Check `holder studio-play` before every write. Never start or stop play yourself.
- Only write to your owned subtrees (`SoundService`, `ReplicatedStorage.Assets.Audio`).
  Never edit Coding's scripts or Designer's UI.
- `ASK` Coding for trigger hooks.
- `ASK` the Lead for playtests, approvals, or decisions.
- Never message the user.
