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
`AnimationIds`. Build what the spec lists; the spec includes custom clips when they add to
the game's feel, including styled replacements for Roblox defaults (idle, walk, run, jump,
fall, land). **Two plugin-wide rules apply to every game:** characters are R15 unless the
spec or player explicitly asks for R6, and every clip meets the **Motion style
(required)** bar below (big, eased, readable at a glance), checked by the self-review
before `DONE`.

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

## Rig type: R15 by default

Characters and avatars are **R15** unless the game spec or the player explicitly asks for
R6. Never pick, assume or suggest R6 on your own: author against R15 joint names
(`HumanoidRootPart > LowerTorso > UpperTorso > Head`, `Left/RightUpperArm > LowerArm >
Hand`, `Left/RightUpperLeg > LowerLeg > Foot`), test on an R15 rig, and set
`animations[].rig = "R15"`. Use `"R6"` only when `game-spec.json` or the user says so
(then also check the place's avatar settings agree). Non-humanoid things (weapon
viewmodels, props, creatures) are `"custom"` rigs.

## Motion style (required)

Player feedback across games: subtle animations read as "barely noticeable" (a 0.15 s
blaster kick with a few hundredths of a stud of motion is invisible in play). Every clip
you ship must be **fluid, exaggerated and readable at a glance in gameplay**, on a phone,
at speed. When in doubt, push it further. A clip that looks slightly too big in the editor
usually looks right in play.

**Principles (all required):**
- **Anticipation:** a small opposite move before the main action (wind-up, crouch, dip),
  except where gameplay needs zero input delay (fire kick). Then the snap itself is the
  first key.
- **Strong key poses with clearly visible amplitude:** each pose must be visibly different
  from rest, as a silhouette, not just as a number change.
- **Overshoot and settle:** go past the target, come back, settle. Never stop dead on the
  final pose.
- **Follow-through and overlap:** parts don't all start and stop together. Children
  (hands, mag, lever, head, tail) lag their parent by 1-3 frames (0.03-0.1 s) and keep
  moving after it stops.
- **Eased curves, never linear:** no `Linear` easing on any moving key (`Constant` only for
  deliberate snaps/holds). Fast out of the hit, slow into the settle.
- **Arcs:** limbs and thrown/moving parts travel on curves (add a mid key off the straight
  line), not straight lines.
- **Secondary motion:** something besides the main part reacts (body sway on a weapon
  kick, head bob on a swing, a mag wobble, a cape/ear flop).

**Minimum amplitudes (checkable):**

| Thing | Minimum at the peak key |
|---|---|
| Held weapon recoil (viewmodel or in-hand) | pitch up **15-25 deg** and pull-back **0.3-0.6 studs**; optional roll 2-5 deg |
| Moving weapon sub-parts (lever, slide, bolt, mag) | travel >= 0.25 studs or >= 20 deg, with a follow-through key |
| Character arms in an action (swing, punch, throw, cheer) | shoulder/elbow arcs of **>= 60 deg**, big swings 90-150 deg |
| Character legs/torso in an action | torso twist or lean >= 15-30 deg; legs >= 30 deg where they move |
| Walk / run cycles | legs swing about +/-30-45 deg (run +/-45-70), arms counter-swing +/-25-40 deg (run more), torso bob 0.1-0.25 studs, slight counter-rotation of hips vs shoulders |
| Idle sway / breathing | still visible: torso rise 0.05-0.1 studs, 2-5 deg sway, weapon drift 0.03-0.08 studs |
| Hit reactions | torso snap 15-30 deg away from the hit, head follows late |

**Durations per clip type (defaults; change only with a gameplay reason):**

| Clip | Length | Shape | Min keys |
|---|---|---|---|
| Fire / recoil | **0.2-0.35 s** | kick to peak in 0.03-0.06 s, eased return, overshoot past rest, settle | 4 (rest, peak, overshoot, settle) |
| Reload | **1.5-2.2 s** | tilt/roll weapon 30-50 deg, eject on an arc, insert with a slap-in jolt, rack/charge with an elastic settle, return with overshoot | 8 |
| Equip | **0.4-0.6 s** | come in from off-screen/below on an arc, overshoot, settle | 4 |
| Idle sway | **2-4 s loop** | gentle figure-8/breathing; first key = last key | 3 (plus the matching end key) |
| Walk cycle | ~0.8-1.2 s loop at WalkSpeed 16 | contact, down, passing, up, mirrored | 5 (8 + end for a clean cycle) |
| Run cycle | ~0.5-0.8 s loop | as walk, bigger and with more lean | 5 |
| Melee attack | 0.5-0.9 s | **clear wind-up** 0.15-0.3 s (pull back 60-90 deg), strike 0.08-0.15 s, follow-through 0.2-0.3 s, recover | 5 (rest, wind-up, strike, follow-through, settle) |
| Hit react | 0.2-0.4 s | snap, overshoot, settle | 3 |
| Emote | 1.5-4 s | big full-body poses (arms > 120 deg, jumps, spins), several distinct beats | 6 |

**Easing (KeyframeSequence `Pose.EasingStyle`, which shapes the move from that key to the
next).** `Enum.PoseEasingStyle` only has Linear, Constant, Elastic, Cubic, Bounce, CubicV2,
so there is no Back or Quad here:
- snaps and kicks: `CubicV2` with direction Out (fast start), or a 1-2 frame gap;
- settles: `CubicV2` Out; spring-like snaps (lever release, landing): `Elastic` Out;
  impacts: `Bounce` Out, sparingly;
- Back-style overshoot: add an explicit overshoot key past rest, then settle to rest;
- verify the direction visually in the frame strip (the legacy `Cubic` direction is known to
  read inverted, which is why `CubicV2` exists).

For TweenService (procedural fallback) use `Enum.EasingStyle` **Back / Quad / Cubic /
Quint Out** for kicks and settles and **Elastic Out** for springy snaps, never `Linear`.

**Match gameplay timing with play speed, not by shrinking the motion.** If gameplay needs
the action in `gameplayDuration` seconds (fire rate, reload time, attack window), keep the
clip's full motion and play it with
`track:Play(fadeTime, weight, clipLength / gameplayDuration)` (or
`track:AdjustSpeed(clipLength / gameplayDuration)`). Don't cut amplitude or delete keys to
fit. If the needed speed goes past about 1.5x, the clip is the wrong length: ask the Lead
whether gameplay timing or the clip should change. Use markers (`GetMarkerReachedSignal`)
for gameplay events (`Hit`, `MagOut`, `MagIn`), not `task.wait`.

**Worked example (Scrapyard Showdown blaster viewmodel, the bar to meet):**
- **BlasterFire, 0.28 s:** Body kicks **0.55 studs back** (+0.1 up), **22 deg pitch up**
  and 3 deg roll in **0.05 s** (CubicV2 Out); eased return through 0.12 s; overshoots past
  rest at 0.18 s (forward 0.08, pitch -4 deg); settles by 0.28 s (`End`). The lever snaps
  back 0.35 at 0.05 s, follows through forward -0.08 at 0.12 s and +0.03 at 0.18 s; the
  magazine lags (-0.03, -5 deg) as secondary motion.
- **BlasterReload, 1.9 s:** Body rolls over **~45 deg** (pitch down 12 deg, yaw 10 deg) by
  0.28 s; the mag is tugged at 0.40 s, then **flung out on an arc** at 0.48 s (`MagOut`) and
  drops off-screen by 0.70 s; the new mag rises from below and **slaps in** with a +0.07
  overshoot at 1.20 s (`MagIn`) while the Body jolts up 0.11 / pitch +6 deg; the Body
  rebounds and rolls back; the lever **racks back 0.45** at 1.52 s (Body jerks back),
  releases with overshoot and an **Elastic settle** at 1.60 s; the Body overshoots rest
  (roll +5, pitch +3) at 1.78 s and settles by 1.90 s (`End`).

### Self-review before DONE (required)

Before you report `DONE`, prove the motion is obviously visible:
1. **Numbers:** for each clip, compare the rest key with the peak key per moving joint
   (`(peak.Position - rest.Position).Magnitude` in studs, and the rotation angle from
   `peak:ToAxisAngle()` relative to rest). Check them against the tables above, and check
   key count, duration and that no moving key uses `Linear`.
2. **Frame strip:** render 4-6 frames: rest (t=0), anticipation if any, **peak**, overshoot,
   settle. In Studio (Path A), clone the rig into a preview spot in Edit mode, apply each
   sampled key's pose CFrames to the matching `Motor6D.Transform` (or play the track and
   `Animator:StepAnimations(dt)` to the time), `screen_capture` each frame from the
   gameplay camera angle, then delete the preview clone. In Blender (Path B), render those
   frames with `review_sheet`.
3. **Compare first vs peak frame:** the difference must be obvious at thumbnail size. If you
   have to look closely to see it, it is **subtle = fail**: increase the amplitude, add
   overshoot or follow-through, and redo before reporting.
4. Put the peak amplitudes (studs/deg), duration, key count and the frame-strip paths in your
   `DONE` so the Lead can check them.
*Guidance: verify edit-mode `StepAnimations`/`Transform` preview behavior in your Studio
version; if neither shows the pose, use the numeric check plus a Lead-run playtest capture.*

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
-- R15 "cheer": anticipation dip, arms fling up past the target, pump, overshoot, settle. 1.4 s
local seq = Instance.new("KeyframeSequence")
seq.Name = "VictoryCheer"
seq.Loop = false
seq.Priority = Enum.AnimationPriority.Action

local function pose(parent: Instance, name: string, cf: CFrame?, style: Enum.PoseEasingStyle?): Pose
    local p = Instance.new("Pose")
    p.Name = name
    p.CFrame = cf or CFrame.identity
    p.EasingStyle = style or Enum.PoseEasingStyle.CubicV2 -- eased, never Linear
    p.EasingDirection = Enum.PoseEasingDirection.Out
    p.Parent = parent
    return p
end

-- armAngle in degrees (big arcs), torsoDip in studs (anticipation / bounce), lean in degrees
local function keyframe(t: number, armAngle: number, torsoDip: number, lean: number, name: string?, style: Enum.PoseEasingStyle?)
    local kf = Instance.new("Keyframe")
    kf.Time = t
    if name then kf.Name = name end
    local root = pose(kf, "HumanoidRootPart")
    local lower = pose(root, "LowerTorso", CFrame.new(0, -torsoDip, 0), style)
    local upper = pose(lower, "UpperTorso", CFrame.Angles(math.rad(lean), 0, 0), style)
    pose(upper, "Head", CFrame.Angles(math.rad(-lean * 0.6), 0, 0), style) -- secondary motion
    pose(upper, "RightUpperArm", CFrame.Angles(0, 0, math.rad(armAngle)), style)
    pose(upper, "LeftUpperArm", CFrame.Angles(0, 0, math.rad(-armAngle)), style)
    kf.Parent = seq
end

keyframe(0.00,   0,    0,   0)                         -- rest
keyframe(0.20, -20,  0.4,  12)                         -- anticipation: crouch, arms drop back
keyframe(0.45, 165, -0.3, -15)                         -- peak: fling up past the target, body rises
keyframe(0.70, 130,  0.1,  -8)                         -- pump down
keyframe(0.95, 160, -0.2, -12)                         -- pump up
keyframe(1.20,  -8,  0.1,   4, nil, Enum.PoseEasingStyle.Elastic) -- overshoot past rest
keyframe(1.40,   0,    0,   0, "End")                  -- settle
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
pose. Only include poses for joints you move (plus their ancestors). Use easing to
interpolate between keys, but never go below the minimum keys for the clip type
(Motion style): anticipation, peak, overshoot and settle each need their own key.

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

1. **Rig:** characters default to R15 (R6 only if the spec/player asks). For R15 work,
   start from a Roblox R15 reference rig (export a rig built with Studio's Avatar > Rig
   Builder via the 3D Exporter, or the R15 rig linked from the Maya guide), so bone names match: `HumanoidRootPart, LowerTorso, UpperTorso, Head,
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
   Look for broken joints, bones that flip, and feet sliding through the ground, and run
   the Motion style self-review (first vs peak frame must differ obviously).
4. **Export:** `export_asset(a, with_animation=True)` (bakes animation, no leaf bones, FBX
   Unit Scale). One animation per FBX for the general importer. glTF can hold several clips
   for the Animation Editor importer.
5. **Import (needs the user's hands):** `send-to-pc.py` the file (`team-protocol` section 7)
   and `ASK` the Lead to have the user select the rig, open the Animation Editor, use its
   **Import** option, choose that file, and pick the rig's rest pose when asked. Clips land
   in `ServerStorage/RBX_ANIMSAVES`. Then continue as in Path A (temp id -> publish).

## Publish (Lead executes after user approval)

Publishing creates an asset on the user's account. The Lead collected approval at
preflight and executes publishes, or batches manual steps for the user.

**After authoring:** report to the Lead that the clip is ready. If `build.approvals.publishAnimations`
is true, the Lead will run the publish step (or arrange the manual step) and send back the
asset id. Animator never asks the user directly.

- **Manual route (current, requires user hands):** the user opens the clip in the Animation
  Editor > ... > **Publish to Roblox** > title, Creator (the user or group that owns the
  game) > Submit, and sends back the asset ID to the Lead, who forwards it to you. The
  Lead batches all clips into one request to minimize interruptions.
- **Possible automated route (unverified, Lead would run this if it works):** serialize the
  KeyframeSequence in Studio Edit (`SerializationService:SerializeInstancesAsync`) to
  `.rbxm` bytes, write to `exports/<id>.rbxm`, report `READY-UPLOAD #n exports/<id>.rbxm`
  to the Lead. The Lead runs `opencloud_upload.py <file>.rbxm --type Animation --name ...`
  and replies with the asset id. Moving the bytes from Studio to the file is the
  uncertain part; try it only if the Lead asks.

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

First pass the Motion style self-review (numbers + frame strip; subtle = fail, redo).
You can't start play yourself (only the Lead holds `studio-play`). In Edit mode, check that
every KeyframeSequence exists and that `AnimationIds` requires cleanly (the require-check
in `roblox-code`). Then `ASK` the Lead for a playtest check: trigger each animation,
`screen_capture` at the peak of each animation (it must read clearly at gameplay
speed), and look in `get_console_output` for "Failed to load
animation" (ownership or a bad id). After it passes, set `status = "wired"` (temp-id clips
stay `authored` until published).
