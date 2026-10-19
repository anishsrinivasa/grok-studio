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

## Interaction reachability (REQUIRED - general rule)

**Every interaction must work through real player input.** Every interactive or targetable
element the spec declares (hit zones, buttons, ProximityPrompts, ClickDetectors, pickups,
touch triggers, doors, UI buttons) must be reachable the way a player would reach it.

**Problem:** Decorative or visual geometry blocks interaction. A ProximityPrompt inside a
decorative hull never triggers. A touch part with `CanTouch=true` sits behind a wall with
`CanTouch=true`. A UI button is under another transparent frame that eats clicks.

**Solution:**
1. **Separation of concerns:** Interactive parts (hit zones, prompts, triggers, buttons)
   are distinct instances with deliberate collision and query settings.
2. **Decorative geometry** sets `CanQuery=false`, `CanTouch=false`, or simplified
   collision (`CollisionFidelity=Box`) so it never interferes with interaction paths.
3. **Coding resolves interactions explicitly:** Hit detection uses specific parts (by name
   or tag), never relies on `Mouse.Target` or broad raycasts that might hit decoration.
4. **UI layering:** Interactive buttons have higher `ZIndex` than decorative frames, or
   decorative frames set `Active=false`.

**Builder self-check (before `DONE`):** For every declared interactive element:
- **Camera raycast targets (hit zones, ClickDetectors):** Place dummy R15 at typical
  player positions, raycast toward the element, verify the intended part is hit (not
  decoration).
- **Touch/proximity triggers (pickups, ProximityPrompts, doors):** Verify character can
  reach the part (walkable path, not occluded by walls/collision).
- **UI buttons:** Click each button in a test UI scene, verify it fires.

**Playtest check:** AcceptanceFramework exercises **every declared interaction through real
input paths** (camera raycast, character touch, prompt trigger, UI click), **never by
calling server functions directly**, and fails any element that doesn't respond.

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

## Rig attachments and held objects (REQUIRED - Builder self-check)

**Everything attached to or held by a character must be checked against the rig.** Tools,
accessories, welded props, mounts, and vehicles must have the correct orientation, anchor
point, and scale on an R15 rig.

**Problem:** A `Tool` with default `Grip` (zero rotation, zero offset) points the wrong
direction. An `Accessory` parented to the wrong attachment floats or clips. A welded prop
(shield, jetpack, mount) has wrong orientation or scale.

**Solution:**
1. **Tools (weapons, items held in hand):**
   - `Tool.Grip` CFrame must orient the tool's forward axis along the character's
     LookVector (the direction they face).
   - Test on a dummy R15: the tool should point forward when equipped, not up/sideways.
   - `Tool.GripPos` anchors at the right hand attachment.

2. **Accessories (hats, backpacks, shoulder items):**
   - Parent to the correct `Attachment` in the character rig:
     - Hats: `HatAttachment` (in Head)
     - Backpacks: `BodyBackAttachment` (in UpperTorso)
     - Shoulder items: `LeftShoulderAttachment` or `RightShoulderAttachment`
   - Use an `Accessory` instance with `Handle` and correct `AttachmentPoint` CFrame.

3. **Welded props, mounts, vehicles:**
   - WeldConstraint or Motor6D between character part and prop must have correct `C0`/`C1`
     offsets for orientation and position.
   - Scale: model must fit the R15 rig (e.g., a mount's seat at hip height, a shield
     sized for the arm).

**Builder self-check (before `DONE` on any attached/held object):**
1. Spawn a dummy R15 character in Studio (or use a test rig).
2. Attach the object:
   - Tools: `character.Humanoid:EquipTool(toolInstance)`
   - Accessories: parent and call `Humanoid:BuildRigFromAttachments()`
   - Welded props: create WeldConstraint, set `C0`/`C1`
3. Set `HumanoidRootPart.CFrame` to face a known direction (e.g., +Z).
4. Verify:
   - **Tools:** forward axis aligns with `LookVector` (within ~15°)
   - **Accessories:** sit at expected body part (head, back, shoulder), no float/clip
   - **Welded props:** correct position relative to body, appropriate scale
5. Take a screenshot, include in `DONE` message.

**Playtest check:** AcceptanceFramework verifies every declared tool, accessory, and
attached object on a test rig automatically.

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
