---
name: roblox-building
description: Builds a Roblox game's world directly in Studio through the Studio MCP - blockout of the map from game-spec.json world/layout, spawn, CollectionService-tagged gameplay parts, terrain, lighting, and props via parts, generate_procedural_model, generate_mesh, generated materials/textures, or inspected Creator Store assets - with idempotent builders that never overwrite the user's own edits. Use for any map, level, building or prop work in Studio (Builder's main skill).
---

# Roblox building (in Studio)

Realize `world` and the Studio-sourced `assets.items[]` from `game-spec.json` inside
`Workspace`. Blender meshes are covered in `blender-assets`; this skill places them too.
Ownership and locks: `team-protocol` (Builder owns `Workspace`, `Lighting`, `Terrain`,
`ReplicatedStorage.Assets.Models`, `ServerStorage.Templates`).

## Order of work

1. **Blockout first:** grey parts for every play space, path, platform and the spawn,
   at real scale (a default avatar is about 5 studs tall, jumps about 7 studs high and
   about 12 studs far at default settings, and a door is about 4x7 studs). Place the
   gameplay parts with their **tags** in the same pass. Coding and the Lead can start
   testing on a blockout. Report `DONE` for it before you start making it pretty.
2. **Look and feel:** materials and colors from `assets.styleGuide`, lighting, terrain,
   then props and dressing.
3. **Custom models** from Blender or `generate_mesh` replace blockout pieces last.

## Structure

```
Workspace
  Map/                 everything you build (Folder)
    Gameplay/          tagged parts the code uses (Coin, Lava, Checkpoint...)
    Scenery/           visual-only, CanCollide/CanQuery off where possible
    Spawn              SpawnLocation (one, or one per team)
ReplicatedStorage.Assets.Models/   templates code clones at runtime (client-visible)
ServerStorage.Templates/           server-only templates
```

## Builders (execute_luau, Edit)

One builder per area, idempotent: find-or-create by name, update properties in place,
and never `ClearAllChildren()` a folder that may hold the user's work.

```lua
local CollectionService = game:GetService("CollectionService")
local map = workspace:FindFirstChild("Map") or Instance.new("Folder")
map.Name = "Map"; map.Parent = workspace
if map:GetAttribute("Frozen") then return "Map is frozen (user edits): not touching it" end

local function part(parent: Instance, name: string, props: { [string]: any }, tags: { string }?): BasePart
    local p = parent:FindFirstChild(name) :: BasePart?
    if not p then
        p = Instance.new("Part")
        p.Name = name
        p.Parent = parent
    end
    local inst = p :: BasePart
    inst.Anchored = true
    for k, v in props do (inst :: any)[k] = v end
    for _, t in tags or {} do CollectionService:AddTag(inst, t) end
    inst:SetAttribute("BuiltBy", "Builder")
    return inst
end
```

Rules that keep the user's work safe:
- Tag everything you create with `BuiltBy = "Builder"`. Only modify or remove instances
  that carry it.
- If the user edits the map by hand, set `Map:SetAttribute("Frozen", true)` when they say
  so. From then on, only add new things and never move or rebuild existing ones.
- Before and after a big builder, take a cheap checksum of `Workspace.Map` (part count,
  summed positions) and report it in your `DONE`. If something you didn't expect changed,
  say so.

## Lighting and terrain

- `Lighting`: set `Technology` only if the spec asks. Prefer tuning `Ambient`,
  `OutdoorAmbient`, `Brightness`, `ClockTime`, plus `Atmosphere`/`Sky` children made with
  find-or-create. Leave the user's own Sky alone if one exists.
- `Terrain`: `workspace.Terrain:FillBlock(cframe, size, Enum.Material.Grass)` /
  `FillBall` / `FillCylinder` for ground, hills and water. Keep it coarse, since terrain
  costs memory on phones. Never `Terrain:Clear()` unless you made all of it.

## Studio generation tools

| Tool | Use for | Notes |
|---|---|---|
| `generate_procedural_model` | buildings, furniture, vehicles, blocky creatures from primitives, with tunable attributes | long-running: call with `async: true`, keep building, then `wait_job_finished`. It inserts into Workspace: move the result into `Map` and add tags |
| `generate_mesh` | organic one-off props in a style that allows AI meshes | pass `maxTriangles` (spec budget) and `size` in studs; include the style guide ("flat-shaded low-poly, palette ..."). Check scale and pivot after insert |
| `segment_mesh` | split a generated mesh into named parts (up to 5) | e.g. so a door can open |
| `generate_material` / `generate_texture` | MaterialVariants for parts/terrain, re-texturing a MeshPart | keep to the palette |
| `store_image` | turn a reference image into an `IMAGEID_...` for `generate_procedural_model` | the file must be on the user's PC: `send-to-pc.py` first |
| `search_asset` + `insert_asset` | generic filler from the Creator Store | **inspect every script inside** (`script_grep` for `require(`, `getfenv`, `loadstring`, `HttpService`, `MarketplaceService`), delete unexpected scripts, and prefer verified creators |

## Placing Blender models

Once a model is in the place (Open Cloud upload + `insert_asset`, or the user's Import
3D), find it with `search_game_tree`, rename it to the spec id, set `PrimaryPart`, scale
with `Model:ScaleTo(model:GetScale() * f)` (ScaleTo is absolute, so multiply), place it with
`PivotTo`, and set `Anchored`, `CanCollide` and `CollisionFidelity` (Box or Hull for simple
props, PreciseConvexDecomposition only when needed). Turn `CastShadow` off on tiny props,
and add the tags. Put templates in `ReplicatedStorage.Assets.Models` and instances in
`Workspace.Map`.

**Apply the manifest**: Blender exports split multi-material meshes into one MeshPart per
material (`<Object>_<Material>`) and write `exports/<id>_manifest.json` (piece -> limb,
main piece, sRGB colour). Run `apply` then `validate` from
`skills/blender-assets/reference/studio/manifest_importer.lua` (usage in `blender-assets`,
"Placing"); `validate` must print `PASS`. Never fake missing colours with stacked box Parts.

## Verify

- `search_game_tree` under `Workspace.Map` (shallow, filtered) to confirm names.
- An Edit-mode check that every tag in the spec has at least the expected count:
  `#CollectionService:GetTagged(tag)`.
- `screen_capture` from 1-3 angles (overview, spawn view, a gameplay spot). Look at each,
  fix floating parts, gaps players can fall through and wrong scale, then set
  `assets.items[].status = "placed"` with `instancePath`.
- Part count: report it. Keep scenery merged and simple on mobile (fewer, larger parts).
