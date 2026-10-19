# Example: Preflight and Spec

This example shows how Lead GrokBot handles the preflight stage and writes the initial game-spec.json.

## User Prompt

> Make a co-op tycoon where players run a volcano-powered hot sauce factory. Conveyor
> droppers make sauce bottles, players collect cash, buy upgrades and unlock a second
> floor. Low-poly cartoon style, mobile-friendly UI, no monetization. Save progress.
> Make a thumbnail and icon.

## Preflight

1. **Studio check**: `list_roblox_studios` → one Studio open, place "HotSauceTycoon", placeId 123456789
2. **Team check**: all five Bots respond READY
3. **Workspace**: create `/workspace/grok-studio/games/hot-sauce-tycoon/`
4. **Connectors**: cloud Blender ✓, Figma auth ✗ (free seat), Open Cloud key ✓
5. **Gated approvals**: user approves automatic uploads and publishing

## Spec Write (abbreviated)

```json
{
  "specVersion": "1.0",
  "meta": {
    "title": "Hot Sauce Tycoon",
    "slug": "hot-sauce-tycoon",
    "genre": "tycoon",
    "targetSessionMinutes": 15,
    "maxPlayers": 4,
    "platforms": ["pc", "mobile", "tablet"],
    "originalPrompt": "...",
    "assumptions": [
      "2 floors for v1 scope",
      "Droppers are timed spawners, not player-activated",
      "Cash zones auto-collect when walked over"
    ]
  },
  "pitch": "Team up to run a lava-powered hot sauce factory: buy droppers, collect cash, unlock upgrades and the VIP floor.",
  "coreLoop": {
    "steps": ["Walk to cash zones", "Collect cash", "Buy a dropper or upgrade", "Wait for bottles", "Repeat"],
    "loopSeconds": 45,
    "funHypothesis": "Incremental progress with co-op synergy (friend's upgrades help you too)."
  },
  "mechanics": [
    {"id": "cashCollection", "name": "Cash collection", "authority": "server", "priority": "must"},
    {"id": "dropperPurchase", "name": "Buy droppers", "authority": "server", "priority": "must"},
    {"id": "floorUnlock", "name": "Unlock floor 2", "authority": "server", "priority": "should"}
  ],
  "animations": [
    {"id": "cheerUnlock", "name": "Unlock cheer", "rig": "R15", "source": "studio-keyframes", "looped": false, "priority": "Action", "durationSeconds": 1.4, "trigger": "Unlocking floor 2"}
  ],
  ...
}
```

## Output to User

> **Hot Sauce Tycoon** - Team up to run a lava-powered hot sauce factory: buy droppers,
> collect cash, unlock upgrades and the VIP floor.
>
> **Loop:** collect cash → buy droppers/upgrades → wait for bottles (45 s).
>
> **Mechanics:** 3 must, 1 should. **Assets:** 8 models. **UI:** 2 screens (HUD, shop).
> **Animations:** 1 custom. Persistence on. Mobile-ready.
>
> I'll plan tasks and dispatch the team now.

Then proceed to Stage 2: Plan.
