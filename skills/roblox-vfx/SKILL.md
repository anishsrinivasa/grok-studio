---
name: roblox-vfx
description: Creates particle effects, beams, trails, explosions and screen post-effects in Roblox Studio (ParticleEmitter, Beam, Trail, Attachments, Lighting effects) tied to gameplay events, following the game's art style and motion standards. Use for any VFX work in a grok-studio game.
---

# Roblox VFX

Build visual effects for every gameplay event in `game-spec.json` -> `vfx[]` as reusable
Studio templates in `ReplicatedStorage.Assets.VFX`, wired to Coding's events. Effects match
the world's art style, are exaggerated and readable, and stay performant on mobile.

**Team mode (`team-protocol`):** VFX builds the effect templates and owns
`ReplicatedStorage.Assets.VFX` and transient `Lighting` post-effects. Coding triggers them
from gameplay code. Builder owns base Lighting properties (ambient, time, atmosphere).

## Planning: what effects does the game need?

Read `mechanics[]`, `world.setting`, `assets.styleGuide.artStyle` and the palette. List:
- **Impact/contact effects**: coin pickup burst, footstep dust, landing particles, damage
  sparks, explosion rings
- **Projectile/ability trails**: muzzle flash, bullet tracer (Beam), ability aura (Beam or
  Trail on moving parts)
- **Environment ambiance**: floating embers/leaves, fog patches, water ripples, ambient
  fireflies
- **Screen feedback**: damage red vignette (ColorCorrection flash), ability charge glow
  (Bloom pulse), screen shake (Camera CFrame offset, Coding's side)

Write each to `vfx[]` in the spec:

```json
{
  "id": "coinBurst",
  "name": "Coin pickup burst",
  "type": "particle",
  "trigger": "Client event CoinPickup",
  "location": "Coin position",
  "duration": 0.4,
  "authority": "client",
  "status": "planned"
}
```

`authority`: client = visual only, server = visible to everyone, shared = hybrid (server
spawns, client animates).

## Building effects

### ParticleEmitters (bursts, trails, ambiance)

Create each effect as a `Folder` or `Part` template in `ReplicatedStorage.Assets.VFX` with
one or more `ParticleEmitter` children and `Attachment` anchors.

**Example: coin pickup burst** (radial burst of 20-30 sparkles, 0.4 s):

```lua
-- execute_luau Edit
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local TweenService = game:GetService("TweenService")

local vfxFolder = ReplicatedStorage:FindFirstChild("Assets")
if not vfxFolder then
  vfxFolder = Instance.new("Folder")
  vfxFolder.Name = "Assets"
  vfxFolder.Parent = ReplicatedStorage
end
local vfx = vfxFolder:FindFirstChild("VFX")
if not vfx then
  vfx = Instance.new("Folder")
  vfx.Name = "VFX"
  vfx.Parent = vfxFolder
end

-- Template: invisible part with an Attachment and ParticleEmitter
local template = vfx:FindFirstChild("CoinBurst")
if template then template:Destroy() end
template = Instance.new("Part")
template.Name = "CoinBurst"
template.Size = Vector3.new(0.1, 0.1, 0.1)
template.Transparency = 1
template.CanCollide = false
template.Anchored = true
template.Parent = vfx

local attach = Instance.new("Attachment")
attach.Name = "Origin"
attach.Parent = template

local emitter = Instance.new("ParticleEmitter")
emitter.Name = "Sparkles"
emitter.Parent = attach

-- Burst: emit once, then destroy
emitter.Enabled = false
emitter.Rate = 0
emitter.Lifetime = NumberRange.new(0.3, 0.5)
emitter.Speed = NumberRange.new(8, 12)
emitter.SpreadAngle = Vector2.new(180, 180)
emitter.Acceleration = Vector3.new(0, -20, 0)  -- gravity
emitter.Size = NumberSequence.new({
  NumberSequenceKeypoint.new(0, 0.4),
  NumberSequenceKeypoint.new(0.5, 0.6),
  NumberSequenceKeypoint.new(1, 0)
})
emitter.Transparency = NumberSequence.new({
  NumberSequenceKeypoint.new(0, 0),
  NumberSequenceKeypoint.new(0.7, 0.3),
  NumberSequenceKeypoint.new(1, 1)
})
emitter.Color = ColorSequence.new(Color3.fromHex("FFD23F"))  -- spec accent color
emitter.LightEmission = 0.8
emitter.ZOffset = 0.5

return "CoinBurst created"
```

**Trigger from Coding's client event handler:**

```lua
local coinBurst = ReplicatedStorage.Assets.VFX.CoinBurst:Clone()
coinBurst.Position = coinPosition
coinBurst.Parent = workspace.Effects
coinBurst.Origin.Sparkles:Emit(25)
task.delay(1, function() coinBurst:Destroy() end)
```

### Beams (lasers, ropes, trails between parts)

`Beam` connects two `Attachment`s. Use for continuous lines (laser sights, grappling hooks)
or projectile tracers (bullet from muzzle to hit point).

**Example: laser beam between two parts:**

```lua
local beam = Instance.new("Beam")
beam.Attachment0 = part0.Attachment
beam.Attachment1 = part1.Attachment
beam.Color = ColorSequence.new(Color3.fromHex("FF6B1A"))
beam.Width0 = 0.2
beam.Width1 = 0.2
beam.Transparency = NumberSequence.new(0.3)
beam.LightEmission = 1
beam.Texture = "rbxasset://textures/particles/smoke_main.dds"
beam.TextureMode = Enum.TextureMode.Stretch
beam.Parent = part0
```

### Trails (motion trails on moving parts)

`Trail` draws a ribbon behind a moving part, between two `Attachment`s on the same part.
Use for swords, projectiles, ability glows.

**Example: sword slash trail:**

```lua
local trail = Instance.new("Trail")
trail.Attachment0 = sword.Base
trail.Attachment1 = sword.Tip
trail.Lifetime = 0.3
trail.MinLength = 0.05
trail.Color = ColorSequence.new(Color3.fromHex("FFFFFF"))
trail.Transparency = NumberSequence.new({
  NumberSequenceKeypoint.new(0, 0.5),
  NumberSequenceKeypoint.new(1, 1)
})
trail.WidthScale = NumberSequence.new({
  NumberSequenceKeypoint.new(0, 1),
  NumberSequenceKeypoint.new(1, 0.3)
})
trail.Parent = sword
```

Coding enables `trail.Enabled = true` during the swing, then disables it.

### Screen post-effects (transient feedback)

Add or configure `Lighting` children for gameplay feedback. Builder's base Lighting (time,
ambient, Atmosphere) stays constant; you add transient effects.

**Example: damage flash (red vignette pulse):**

```lua
local lighting = game:GetService("Lighting")
local flash = lighting:FindFirstChild("DamageFlash")
if not flash then
  flash = Instance.new("ColorCorrectionEffect")
  flash.Name = "DamageFlash"
  flash.TintColor = Color3.fromRGB(255, 200, 200)
  flash.Brightness = 0
  flash.Contrast = 0
  flash.Saturation = 0
  flash.Enabled = true
  flash.Parent = lighting
end

-- Coding triggers this on damage:
-- local tween = TweenService:Create(flash, TweenInfo.new(0.15, Enum.EasingStyle.Quad, Enum.EasingDirection.Out, 0, true), {Brightness = 0.2})
-- tween:Play()
```

## Motion and style rules

Effects follow the same **exaggerated, fluid motion** standard as animations
(`roblox-animations` > Motion style):
- **Anticipation**: pre-sparks 0.1 s before an explosion, charge-up glow before a blast
- **Readable amplitude**: particles visible from 50+ studs, Size 0.4-1.0 studs, high
  `LightEmission` (0.6-1.0) for glows
- **Arcs and follow-through**: Acceleration for gravity/wind, SpreadAngle for radial
  bursts, speed variation (NumberRange) for depth
- **Eased curves**: Size and Transparency use NumberSequence with 3+ keypoints (start,
  peak, end), never linear
- **Overshoot and settle**: explosion ring expands fast then slows (Speed + Drag), or Size
  sequence 0 -> 1.2 -> 1.0

**Art style match:**
- Palette from `assets.styleGuide.palette` and `ui.styleGuide.palette`
- Low-poly/flat-shaded: geometric particle textures (`rbxasset://textures/particles/smoke_main.dds`
  works as a soft square), solid colors, hard edges
- Stylized/hand-painted: softer textures, color gradients in ColorSequence
- Never photorealistic (smoke photos, real fire) unless the spec's art style is realistic

## Performance targets

**Mobile 60 FPS** is the bar. Profile in Studio's MicroProfiler (View menu) if unsure.

- **Burst effects** (coins, impacts): 20-50 particles, Lifetime 0.3-0.6 s, fine
- **Continuous emitters** (torches, ambient fog): Rate 5-10/s, Lifetime 2-4 s, place
  sparingly (< 10 active in view)
- **Per-player effects** (ability aura): Rate 10-20/s, client-only, Lifetime < 2 s
- **Trails**: Lifetime 0.2-0.5 s, MinLength 0.05
- **Beams**: cheap; dozens are fine if not overlapping
- **Avoid**: Collision = true (never), FlipbookLayout with 512x512 sheets (use smaller or
  skip), LockedToPart on high-rate emitters (use Attachments and clone/move the part),
  Size > 10 studs

**Z-offset**: keep particles slightly in front (ZOffset 0.3-1.0) so they don't hide the
player, but not so far they clip through walls.

## Wiring with Coding

You build templates; Coding triggers them. Coordinate with `ASK` messages.

**Your `DONE` report lists:**
- Effect paths: `ReplicatedStorage.Assets.VFX.CoinBurst`
- Trigger API: `coinBurst:Clone(); coinBurst.Position = pos; coinBurst.Parent =
  workspace.Effects; coinBurst.Origin.Sparkles:Emit(25); task.delay(1, function()
  coinBurst:Destroy() end)`
- Authority: client or server
- Event name: the remote or signal Coding should call it from

**Coding's side:**
- Remotes or BindableEvents for triggers
- Rate limiting (don't spam 100 explosions/second)
- Cleanup (`Debris:AddItem(effect, lifetime)` or manual Destroy)
- Camera shake (CFrame offset, not your ParticleEmitter)

## Verify

1. `search_game_tree` filtered to `ReplicatedStorage.Assets.VFX` and `Lighting` to confirm
   paths.
2. Edit-mode test: clone an effect into `Workspace`, call `:Emit(N)` via `execute_luau`,
   and `screen_capture` it. Look for: visibility from distance, color match, motion
   fluidity, no Z-fighting.
3. Runtime test: `ASK` the Lead for a playtest. Trigger the effect in context (pick up a
   coin, fire a weapon), capture it, check timing and feel.
4. Set `vfx[].status` -> `built` after creation, `verified` after the playtest.

## Reference: common effect patterns

| Effect | Implementation | Properties |
|---|---|---|
| Radial burst (coin, explosion) | ParticleEmitter, `Enabled=false`, `Rate=0`, `:Emit(N)`, SpreadAngle 180 | Speed 8-15, Lifetime 0.3-0.6, Size peak at 50%, Transparency 0->1, Acceleration for gravity |
| Projectile trail | Trail on a moving part, two Attachments (base/tip) | Lifetime 0.3, WidthScale taper, LightEmission 0.8 |
| Laser beam | Beam between two Attachments (muzzle -> target) | Width0/1 constant or taper, LightEmission 1, Texture stretched |
| Impact sparks | ParticleEmitter burst at hit position, narrow SpreadAngle (30 deg) | Speed 10-20, short Lifetime 0.2-0.4, bounce off surface normal |
| Screen flash | ColorCorrectionEffect in Lighting, TweenService Brightness 0 <-> 0.3, 0.15 s | Yoyo tween (0, true) |
| Ambient fog | ParticleEmitter on anchored parts, `Enabled=true`, low Rate 3-5/s | Lifetime 4-8 s, Size large (2-4), Transparency 0.7-0.95, Speed 1-3, LightEmission 0 |

## Team protocol compliance

- Check `holder studio-play` before every write. Never start or stop play yourself.
- Only write to your owned subtrees (`ReplicatedStorage.Assets.VFX`, transient Lighting
  effects). Never edit Builder's `Workspace` or `Lighting.ClockTime` / `Ambient` /
  `Atmosphere`, or Coding's scripts.
- `ASK` Coding for trigger hooks. `ASK` Builder if an effect needs a specific map element
  (torch holders, explosion spawn points).
- `ASK` the Lead for playtests, approvals, or decisions.
- Never message the user.
