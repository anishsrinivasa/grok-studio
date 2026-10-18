---
name: game-spec
description: Turns a one-line Roblox game idea into a complete, validated game-spec.json (genre, core loop, mechanics, progression, scripts with services and locations, remotes, UI screens, asset list with style guide and triangle budgets, animations, thumbnail/icon brief, acceptance tests). Use at the start of any Roblox build, or when the user wants a game design document for Roblox.
---

# Game spec

Produce `game-spec.json`: the single source of truth every other stage reads. Files in this
skill folder:
- `schema.json` - JSON Schema (draft 2020-12). The spec **must** validate against it.
- `example.game-spec.json` - a complete worked example (a lava obby). Mirror its level of
  detail.

## Procedure

1. **Extract** from the prompt: genre, fantasy/setting, verbs (what the player *does*),
   win/lose conditions, multiplayer expectations, platform hints, tone.
2. **Fill gaps with defaults, don't interrogate.** One-shot means you decide. Ask the user
   only if the prompt is contradictory or requests something against Roblox rules. Record
   every decision in `meta.assumptions`.
3. **Scope for a one-shot.** Target 3-5 `must` mechanics, 1-2 currencies, 2-4 UI screens,
   5-15 custom assets, 0-4 custom animations. Push extras to `could` priority. A tight,
   working loop beats a broad broken one.
4. **Design the core loop** as 3-6 steps that repeat every 30-180 s, plus a progression hook
   (unlock, upgrade, rank) that gives a reason to keep looping.
5. **Derive architecture from mechanics:**
   - Each mechanic gets `authority`. Anything touching currency, score, inventory, damage,
     or other players is `server`.
   - Map mechanics to `scripts[]`: one server `Main` Script bootstrapping ModuleScript
     services in `ServerScriptService.Server.Services`, shared modules in
     `ReplicatedStorage.Shared`, one client `ClientMain` LocalScript in
     `StarterPlayer.StarterPlayerScripts` plus client controller modules. See
     `roblox-code` for the canonical layout.
   - List every RemoteEvent in `remotes[]` with payload types, explicit server validation
     rules and a rate limit. No RemoteFunction server->client (client can hang the server).
6. **Persistence:** if anything should survive rejoining, set
   `progression.persistence.enabled = true`, pick a versioned `dataStoreName`
   (e.g. `<Slug>_PlayerData_v1`) and write `dataModel.profileTemplate`.
7. **Monetization is off by default** (`monetization.enabled = false`). Only enable if the
   user explicitly asks; then list passes/products but never create them on Roblox without
   permission.
8. **UI:** define a style guide (palette hex, font, corner radius, stroke) and each screen's
   elements, trigger, and mobile notes (thumb zones: jump button bottom-right, thumbstick
   bottom-left - keep HUD top/edges).
9. **Assets:** set an art style that is feasible for an agent: `flat-shaded low-poly` with
   flat materials or vertex colors is the most reliable. For every item: source
   (`blender`, `studio-generate-mesh`, `studio-procedural-model`, `studio-primitives`,
   `creator-store`), size in studs, triangle budget (**hard cap 20,000 per mesh**, Roblox
   rejects more - [General specifications](https://create.roblox.com/docs/art/modeling/specifications)),
   collision fidelity, anchored.
   Suggested budgets (guidance, not Roblox rules): props 100-800 tris, hero props 1-3k,
   buildings 2-8k, characters 2-10k.
   Scale reference: 1 stud = 28 cm ([Units](https://create.roblox.com/docs/physics/units));
   a default avatar is ~5 studs tall, a door ~4x7 studs.
10. **Animations:** only list ones the game needs beyond Roblox defaults (walk/run/jump are
    free). Include rig, loop, priority, trigger.
11. **Marketing brief:** icon (512x512, one bold subject, no small text) and 1+ thumbnails
    (1920x1080, 16:9, real gameplay moment) - see `thumbnail-and-icon`.
12. **Acceptance tests:** 3-8 concrete, automatable checks phrased as steps + expected
    result, covering the core loop, persistence, and at least one exploit attempt (client
    fires a remote with bad data). The playtest gate runs exactly these.
13. Initialize `build` with `stage: "spec"`, `connectors` from preflight, empty
    `checkpoints`.

## Validate

Validate before handing off - pick whatever is available:
```bash
# Python (uv): 
uv run --with jsonschema python -c "import json,jsonschema;jsonschema.validate(json.load(open('game-spec.json')),json.load(open('<plugin>/skills/game-spec/schema.json')));print('ok')"
# Node:
npx -y ajv-cli validate --spec=draft2020 -s <plugin>/skills/game-spec/schema.json -d game-spec.json
```
If neither is available, check required keys manually against the schema and say so.

## Output

Write `game-spec.json` (2-space indent) to the project folder (Grok Bot:
`/workspace/grok-studio/games/<slug>/game-spec.json`, see `team-protocol`), show the user a 6-10 line
summary (title, pitch, loop, mechanics, screens, asset count), and continue to the next
stage unless they object.

## Quality bar

- Every `scripts[].dependsOn` entry names another script in the list (no dangling deps).
- Every remote referenced by a script description exists in `remotes[]`.
- Every UI element that shows data has a source (remote or attribute) implied by a script.
- Every acceptance test can be executed with Studio MCP tools (navigation, input, Luau
  inspection, console output) - no "ask a human" steps.
