---
name: roblox-animations
description: Creates and wires custom Roblox character/object animations - R15 rigs, animating in Blender (via Blender MCP) and importing FBX/glTF into Studio's Animation Editor, or authoring KeyframeSequences directly with Luau in Studio - then publishing and playing them with Animator:LoadAnimation. Use for emotes, attacks, tool swings, NPC/creature motion, or Stage 5 of a one-shot build.
---

# Roblox animations

Deliver every `game-spec.json` -> `animations[]` entry: authored, imported into Studio,
playable in playtest, published (when the user allows), and wired in code.

Default walk/run/jump/idle animations come free with R15 avatars - only build what the spec
lists.

## Key facts (verified Oct 2026)

- Play animations through an **Animator**: humanoid characters have `Humanoid.Animator`;
  non-humanoid rigs need an `AnimationController` with a child `Animator`. Load with
  `Animator:LoadAnimation(animation)` to get an `AnimationTrack`.
  [Use animations](https://create.roblox.com/docs/animation/using)
- Priority levels (high -> low): Action4, Action3, Action2, Action, Movement, Idle, Core.
  If the animation replaces a default character animation, its last keyframe must be named
  `End`. [Animation Editor](https://create.roblox.com/docs/animation/editor)
- Animation Editor **Save** stores a `KeyframeSequence` under `ServerStorage` (local work
  only). Games must use a **published** animation asset ID (Animation Editor > ... >
  **Publish to Roblox**; pick the group as Creator for group-owned games). (same page)
- FBX exports carry **one animation track per file**; export each animation separately for
  the general importer. [General specifications](https://create.roblox.com/docs/art/modeling/specifications)
- Since Jan 2026 (GA March 2026) the Animation Clip Editor importer uses the Import 3D code
  path, supports **FBX and glTF**, **multiple clips per file**, and auto-saves imported clips
  to `ServerStorage/RBX_ANIMSAVES`; upload is still a separate step.
  [DevForum announcement](https://devforum.roblox.com/t/full-release-animation-clip-editor-improved-importing-and-gltf-support/4260501)
- Rig rules: bones with scale 1 / rotation 0, root at origin, <= 4 influences per vertex.
  [General specifications](https://create.roblox.com/docs/art/modeling/specifications);
  R15 joint names/hierarchy must match Roblox exactly for avatar animations
  ([Export avatar animations (Maya guide; same rules apply to Blender)](https://create.roblox.com/docs/art/characters/export-avatar-animations-from-maya)).
- Open Cloud can upload **Animation** assets only as `.rbxm/.rbxmx` saved from Studio
  (not FBX). [Assets usage guide](https://create.roblox.com/docs/cloud/guides/usage-assets)

## Choose a path per animation

| Situation | Path |
|---|---|
| Short gameplay motion on R15 (wave, cheer, swing, punch) | **A: Luau keyframes in Studio** (no Blender needed, fully automatable) |
| Complex/organic motion, creatures, custom rigs, Blender connected | **B: Blender -> FBX/glTF -> Animation Editor import** |
| Generic motion that exists already | Creator Store animation via `search_asset`/`insert_asset` (check ownership: you can only play animations owned by the game's creator or Roblox) |

## Path A - author KeyframeSequences with Luau (Studio MCP)

Build a `KeyframeSequence` of `Keyframe`s containing nested `Pose`s that mirror the rig's
Motor6D hierarchy (`HumanoidRootPart > LowerTorso > UpperTorso > RightUpperArm ...`).
Run via `execute_luau` (`datamodel_type: "Edit"`):

```lua
-- R15 "cheer": both arms up and back down, 1.2 s
local seq = Instance.new("KeyframeSequence")
seq.Name = "VictoryCheer"
seq.Loop = false
seq.Priority = Enum.AnimationPriority.Action

local function pose(parent: Instance, name: string, cf: CFrame?): Pose
    local p = Instance.new("Pose")
    p.Name = name
    p.CFrame = cf or CFrame.identity
    p.EasingStyle = Enum.PoseEasingStyle.Cubic
    p.EasingDirection = Enum.PoseEasingDirection.InOut
    p.Parent = parent
    return p
end

local function keyframe(t: number, armAngle: number, name: string?)
    local kf = Instance.new("Keyframe")
    kf.Time = t
    if name then kf.Name = name end
    local root = pose(kf, "HumanoidRootPart")
    local lower = pose(root, "LowerTorso")
    local upper = pose(lower, "UpperTorso")
    pose(upper, "RightUpperArm", CFrame.Angles(0, 0, math.rad(armAngle)))
    pose(upper, "LeftUpperArm", CFrame.Angles(0, 0, math.rad(-armAngle)))
    kf.Parent = seq
end

keyframe(0, 0)
keyframe(0.3, 150)
keyframe(0.6, 120)
keyframe(0.9, 150)
keyframe(1.2, 0, "End")

local saves = game:GetService("ServerStorage"):FindFirstChild("RBX_ANIMSAVES")
    or Instance.new("Folder")
saves.Name = "RBX_ANIMSAVES"
saves.Parent = game:GetService("ServerStorage")
local old = saves:FindFirstChild(seq.Name)
if old then old:Destroy() end
seq.Parent = saves
return "saved " .. seq.Name
```

Pose CFrames are **relative offsets of the joint** (Motor6D.Transform), so identity = rest
pose. Only include poses for joints you move (plus their ancestors); keep keyframes sparse
and let easing interpolate.

**Testing before publishing (Studio only):** register the sequence to get a temporary ID:
```lua
local KSP = game:GetService("KeyframeSequenceProvider")
local tempId = KSP:RegisterKeyframeSequence(seq) -- temporary content id, works in this Studio session only
```
Use it for playtest validation; it will not work in a live server.

## Path B - Blender -> Studio

1. **Rig:** for R15 work, start from a Roblox R15 reference rig (export a rig built with
   Studio's Avatar > Rig Builder via the 3D Exporter, or the R15 rig linked from the Maya
   guide), so bone names match: `HumanoidRootPart, LowerTorso, UpperTorso, Head,
   Left/RightUpperArm, Left/RightLowerArm, Left/RightHand, Left/RightUpperLeg,
   Left/RightLowerLeg, Left/RightFoot`. Custom creatures: any hierarchy, but follow the rig
   rules above and import the mesh+rig first (Importer: Rig Type Custom).
   *Guidance - verify the current Roblox 3D Export flow (`https://create.roblox.com/docs/art/modeling/gltf-export`) for your Studio version.*
2. **Animate** with `execute_blender_code`: create an Action, insert keyframes on pose
   bones (`pose_bone.keyframe_insert("rotation_quaternion", frame=f)`), 30 fps, keep the
   root in place unless root motion is intended. Preview with `look` mode `frames`.
3. **Export:** `export_fbx(path, [armature, mesh], with_animation=True)` from
   `blender-assets/reference/roblox_export.py` (bakes animation, no leaf bones, FBX Unit
   Scale). One animation per FBX for the general importer; glTF can hold several clips for
   the Animation Editor importer.
4. **Import (needs the user's hands):** select the target rig in Studio, open the
   Animation Editor, use its **Import** option (FBX or glTF) and choose the file; pick the
   rig's rest pose when asked. Clips land in `ServerStorage/RBX_ANIMSAVES`. Then continue
   with the same test/publish steps as Path A.

## Publish (requires the user)

Publishing creates an asset on the user's account - ask first. In the Animation Editor:
load the clip > ... > **Publish to Roblox** > title, Creator (user or group that owns the
game) > Submit. Copy the asset ID into `animations[].assetId`, set `status = "published"`.
If the user prefers not to publish yet, keep the temp-ID path for playtests and list
publishing as a manual step in the handoff.

## Wire it up

Store IDs in `ReplicatedStorage.Shared.Config.Animations` and play them client-side for the
local character (animations replicate from the owning client's Animator):

```lua
--!strict
local Players = game:GetService("Players")
local Config = require(game:GetService("ReplicatedStorage").Shared.Config)

local cache: { [string]: AnimationTrack } = {}

local function play(name: string): AnimationTrack?
    local character = Players.LocalPlayer.Character
    local humanoid = character and character:FindFirstChildOfClass("Humanoid")
    local animator = humanoid and humanoid:FindFirstChildOfClass("Animator")
    if not animator then return nil end
    local track = cache[name]
    if not track or track.Parent == nil then
        local anim = Instance.new("Animation")
        anim.AnimationId = Config.Animations[name] -- "rbxassetid://123..."
        track = animator:LoadAnimation(anim)
        cache[name] = track
    end
    track:Play(0.1)
    return track
end

Players.LocalPlayer.CharacterAdded:Connect(function() table.clear(cache) end)
```
NPCs: play on the server via the NPC's Animator. Use `AnimationTrack:GetMarkerReachedSignal`
for hit frames instead of `task.wait` timing.

## Verify

During playtest: trigger the animation, `screen_capture` mid-animation, check
`get_console_output` for "Failed to load animation" (ownership or bad ID). Set
`status = "wired"`.
