# Example: Coin Pickup VFX

This example shows VFX GrokBot creating a particle burst effect for coin pickup in an obby game.

## Task from Lead

```
[GS] TASK #6 Lead -> VFX
game: lava-leap   spec: /workspace/grok-studio/games/lava-leap/game-spec.json
do: create VFX for coin pickup (radial particle burst, gold sparkles, 0.4 s)
spec refs: mechanics[coinPickup], assets.styleGuide.palette (accent #FFD23F)
inputs: -
done when: ReplicatedStorage.Assets.VFX.CoinBurst template created, trigger API in DONE
reply with: DONE #6 or BLOCKED #6
```

## VFX Build

Create `ReplicatedStorage.Assets.VFX.CoinBurst` with ParticleEmitter:

- **Type:** Burst (Enabled=false, :Emit(25))
- **Lifetime:** 0.3-0.5 s
- **Speed:** 8-12 studs/s, SpreadAngle 180 deg (radial)
- **Size:** 0.4 → 0.6 → 0 studs (peak at 50%)
- **Color:** #FFD23F (spec accent)
- **LightEmission:** 0.8 (glows)
- **Acceleration:** (0, -20, 0) for gravity
- **ZOffset:** 0.5 (slightly in front)

## DONE Report

```
DONE #6 VFX

Created: ReplicatedStorage.Assets.VFX.CoinBurst
Trigger: Client-side on CoinPickup remote
API: coinBurst = template:Clone(); coinBurst.Position = coinPos; coinBurst.Parent = workspace.Effects; coinBurst.Origin.Sparkles:Emit(25); task.delay(1, function() coinBurst:Destroy() end)

Edit capture: renders/vfx/coin-burst-preview.png
Readable from 50+ studs, matches spec palette.

Open issues: none
ASK Coding: wire to client CoinPickup remote
```

## Coding Wires It

Coding adds to the client controller:

```lua
local Remotes = require(ReplicatedStorage.Shared.Remotes)
local coinBurst = ReplicatedStorage.Assets.VFX.CoinBurst

Remotes.CoinPickup.OnClientEvent:Connect(function(coinPosition)
    local fx = coinBurst:Clone()
    fx.Position = coinPosition
    fx.Parent = workspace.Effects
    fx.Origin.Sparkles:Emit(25)
    task.delay(1, function() fx:Destroy() end)
end)
```

Playtest confirms: visible, on-brand, performant on mobile.
