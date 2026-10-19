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

## Interaction reachability (REQUIRED)

**Every interactive element (hit zones, weak points, pickups, prompts, buttons) must be
reachable by typical player input (raycast, touch, proximity).** Decorative geometry must
NOT occlude gameplay-critical parts.

**Problem:** A gameplay part (e.g. weak point, pickup trigger, ProximityPrompt) placed
inside or behind decorative collision (the hull mesh) registers nothing — player raycasts
and touches hit the hull first.

**Solution:**
1. **Hit zones and weak points** are always **separate BaseParts** (e.g. a 2×2×2 cube),
   placed at the surface where the player should aim, NOT inside the model.
2. **Decorative hulls** set `CanQuery = false` and `CanTouch = false` (or simplified
   collision via `CollisionFidelity = Box`). Coding resolves hits explicitly via hit zone
   parts, never by `Mouse.Target` or `Raycast` filtering the hull.
3. **ProximityPrompts and pickup triggers**: Parts are small and flush with walkable
   surfaces, never occluded by walls or large collision geometry.

**Builder self-check (before `DONE`):** For every declared hit zone / weak point / pickup:
- Place a dummy R15 character at typical player positions (spawn, cover, mid-range).
- `workspace:Raycast(origin, direction, raycastParams)` with `raycastParams.FilterType =
  Enum.RaycastFilterType.Include` and `FilterDescendantsInstances = {hitZonePart}`.
- Verify the ray hits the intended part, not the decorative hull.

**Playtest check:** AcceptanceFramework verifies every declared interactive part has a
clear raycast path from typical player positions.

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

## Rig attachments and tool grip (REQUIRED - Builder self-check)

**Every tool, accessory, or held object attached to an R15 rig must be oriented correctly
and anchored at the proper attachment point.** Misaligned grips leave tools pointing the
wrong direction.

**Problem:** A `Tool` with default `Grip` (zero rotation, zero offset) may point upward
or sideways instead of along the character's forward direction. Accessories parented to
wrong attachments (e.g. a hat on a hand) break visually.

**Solution:**
1. **Tools (weapons, items held in hand):**
   - `Tool.Grip` CFrame must orient the tool's forward axis (typically -Z or +Y, depending
     on model) along the character's LookVector (the direction they face).
   - Common grip for a forward-pointing tool (e.g. blaster, sword):
     `Tool.Grip = CFrame.new(0, 0, 0) * CFrame.Angles(0, 0, 0)` — adjust angles until the
     tool points forward when equipped. Test on a dummy before committing.
   - `Tool.GripPos` anchors the tool at the right hand attachment.

2. **Accessories (hats, backpacks, shoulder mounts):**
   - Parent to the correct `Attachment` in the character rig:
     - Hats: `HatAttachment` (in Head)
     - Backpacks: `BodyBackAttachment` (in UpperTorso)
     - Shoulder items: `LeftShoulderAttachment` or `RightShoulderAttachment`
   - Use an `Accessory` instance with `Handle` and correct `AttachmentPoint` CFrame.

**Builder self-check (before `DONE` on any tool/accessory):**
1. Spawn a dummy R15 character in Studio (or use a test rig).
2. `character.Humanoid:EquipTool(toolInstance)` for tools, or parent the accessory and
   call `Humanoid:BuildRigFromAttachments()`.
3. Set the character's `HumanoidRootPart.CFrame` to face a known direction (e.g. +Z).
4. Verify:
   - **Tool forward axis** aligns with `HumanoidRootPart.CFrame.LookVector` (within ~15°).
   - **Accessory position** sits at the expected body part (head, back, shoulder), not
     floating or clipping.
5. Take a screenshot and include it in the `DONE` message.

**Playtest check:** AcceptanceFramework verifies every declared tool and accessory on a
test rig.

## Quality gates (a failed gate blocks `placed`)

- **No overlay Parts.** Never fake detail by stacking thin Parts on, or inside, a MeshPart
  or another Part. It z-fights, flickers on phones and doubles the part count. Never leave
  two coincident copies of one part. Put detail in the mesh, or make it a proper separate
  piece that clears the surface. Imported models must pass `post_import_check.luau`
  (`blender-assets`), which checks this along with names, sizes and colours.
- **Scale and footing:** nothing floats or sinks unintentionally, and the spawn and every
  gameplay spot are reachable at default jump settings.
- **Budgets:** under 20,000 triangles per mesh and within the spec's per-item budget.
  Report the part count.
- **Looks match the source:** for Blender models, compare the Blender review render with
  a Studio `screen_capture` from the matching camera (`blender-assets`, render vs
  capture).

## Verify

- `search_game_tree` under `Workspace.Map` (shallow, filtered) to confirm names.
- An Edit-mode check that every tag in the spec has at least the expected count:
  `#CollectionService:GetTagged(tag)`.
- `screen_capture` from 1-3 angles (overview, spawn view, a gameplay spot). Look at each,
  fix floating parts, gaps players can fall through and wrong scale, then set
  `assets.items[].status = "placed"` with `instancePath`.
- Part count: report it. Keep scenery merged and simple on mobile (fewer, larger parts).
