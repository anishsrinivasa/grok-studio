---
name: roblox-animations
description: Creates and wires custom Roblox animations as the Animator - R15 KeyframeSequences authored with Luau in Studio (default, fully automatable), or rigs and clips made in headless Blender and imported through the Animation Editor - then publishing, recording the ids in ReplicatedStorage.Shared.AnimationIds, and handing playback to Coding. Use for emotes, attacks, tool swings, NPC/creature motion, or the animations part of a grok-studio build.
---

# Roblox animations

Deliver every `game-spec.json` -> `animations[]` entry: authored, playable in a Studio
playtest, published (when the user allows), and listed in `AnimationIds` for Coding to play.

**Owner: Animator** (`team-protocol`). You write `ReplicatedStorage.Shared.AnimationIds`,
`ReplicatedStorage.Assets.Rigs`, `ServerStorage.RBX_ANIMSAVES` and the `animations[]` part of
the spec. You don't write playback code. Coding plays your animations from
`AnimationIds`. Default walk/run/jump/idle come free with R15 avatars: build only what the
spec lists.

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
  (not FBX); files edited outside Studio "might not upload or function".
  [Assets usage guide](https://create.roblox.com/docs/cloud/guides/usage-assets)
- A game can only play animations owned by the game's creator (user or group) or by Roblox.

## Choose a path per animation

| Situation | Path |
|---|---|
| Short gameplay motion on R15 or a simple rig (wave, cheer, swing, punch, bob, spin) | **A: Luau keyframes in Studio** (default, no Blender, fully automatable) |
| Complex/organic motion, creatures, custom rigs | **B: headless Blender -> FBX/glTF -> Animation Editor import** (needs one user click per file) |
| Generic motion that exists already | Creator Store animation via `search_asset`/`insert_asset`, only if owned by Roblox or the game's creator |

Before any Studio write, check the `studio-play` lock (`team-protocol` section 4).

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
Put the temp id in `AnimationIds` (marked as temporary, see "Wire it up") so the Lead's
playtest can exercise it. It will not work in a live server, and it is gone after Studio
restarts: register again then.

## Path B - headless Blender -> Studio

Use the `blender-assets` tools (cloud: `cloud_blender.sh run`, `asset_harness`). Your
files are your own: one rig/animation .blend per id, `games/<slug>/blender/<id>.blend`,
with checkpoints. Never write a Builder's .blend. If you need a Builder's mesh, import its
FBX from `exports/` into your own file.

1. **Rig:** for R15 work, start from a Roblox R15 reference rig (export a rig built with
   Studio's Avatar > Rig Builder via the 3D Exporter, or the R15 rig linked from the Maya
   guide), so bone names match: `HumanoidRootPart, LowerTorso, UpperTorso, Head,
   Left/RightUpperArm, Left/RightLowerArm, Left/RightHand, Left/RightUpperLeg,
   Left/RightLowerLeg, Left/RightFoot`. Custom creatures: any hierarchy, but follow the rig
   rules above, and get the mesh + rig into Studio first (Importer: Rig Type Custom), into
   `ReplicatedStorage.Assets.Rigs`.
   *Guidance - verify the current Roblox 3D Export flow (`https://create.roblox.com/docs/art/modeling/gltf-export`) for your Studio version.*
2. **Animate** in a job: create an Action, insert keyframes on pose bones
   (`pose_bone.keyframe_insert("rotation_quaternion", frame=f)`), 30 fps, keep the root in
   place unless root motion is intended. `checkpoint()` after each clip.
3. **Check it:** render a few frames for review: set `scene.frame_set(f)` for 3-4 key
   frames and call `review_sheet(a, round_no=...)` for each, or render the 3/4 camera only.
   Look for broken joints, bones that flip, and feet sliding through the ground.
4. **Export:** `export_asset(a, with_animation=True)` (bakes animation, no leaf bones, FBX
   Unit Scale). One animation per FBX for the general importer. glTF can hold several clips
   for the Animation Editor importer.
5. **Import (needs the user's hands):** `send-to-pc.py` the file (`team-protocol` section 7)
   and `ASK` the Lead to have the user select the rig, open the Animation Editor, use its
   **Import** option, choose that file, and pick the rig's rest pose when asked. Clips land
   in `ServerStorage/RBX_ANIMSAVES`. Then continue as in Path A (temp id -> publish).

## Publish (requires the user)

Publishing creates an asset on the user's account, so only the user approves it. Ask
through the Lead.

- **Reliable route:** the user opens the clip in the Animation Editor > ... > **Publish to
  Roblox** > title, Creator (the user or group that owns the game) > Submit, and sends back
  the asset ID. Batch all clips into one request.
- **Possible automated route (unverified, do not rely on it):** serialize the
  KeyframeSequence in Studio Edit (`SerializationService:SerializeInstancesAsync`) to
  `.rbxm` bytes, get them onto a machine that has the Open Cloud key, and upload with
  `opencloud_upload.py <file>.rbxm --type Animation --name ...`. Moving the bytes through
  a chat model is not practical (it would have to retype them), so this needs a script on
  the user's PC. Try it only if the Lead asks, and report what worked.

Copy the asset ID into `animations[].assetId`, set `status = "published"`. If the user
prefers not to publish yet, keep temp ids for playtests and the Lead lists publishing as a
manual step in the final handoff.

## Wire it up

You own the id table. Coding owns the code that plays it.

`ReplicatedStorage.Shared.AnimationIds` (ModuleScript), written with `multi_edit`:

```lua
--!strict
-- Owned by the Animator (grok-studio). Name -> animation content id.
-- TEMP ids come from KeyframeSequenceProvider and only work in this Studio session.
local AnimationIds: { [string]: string } = {
    VictoryCheer = "rbxassetid://1234567890",
    SwordSwing = "<id returned by RegisterKeyframeSequence>", -- TEMP: publish before release
}
return table.freeze(AnimationIds)
```

Keys match `animations[].name` (PascalCase). Tell Coding in your `DONE` message which
names exist, their priorities, loop flags and markers (e.g. `Hit` at 0.35 s), so the
controllers can use `AnimationTrack:GetMarkerReachedSignal` instead of `task.wait`
timing. Coding's playback (for reference, not yours to write): load through the
character's `Humanoid.Animator`, cache tracks per character, clear the cache on
`CharacterAdded`. NPCs play on the server through the NPC's Animator.

## Verify

You can't start play yourself (only the Lead holds `studio-play`). In Edit mode, check that
every KeyframeSequence exists and that `AnimationIds` requires cleanly (the require-check
in `roblox-code`). Then `ASK` the Lead for a playtest check: trigger each animation,
`screen_capture` mid-animation, and look in `get_console_output` for "Failed to load
animation" (ownership or a bad id). After it passes, set `status = "wired"` (temp-id clips
stay `authored` until published).
