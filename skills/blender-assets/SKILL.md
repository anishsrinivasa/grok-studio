---
name: blender-assets
description: Creates Roblox-ready low-poly 3D assets with the Blender MCP (modeling, materials, triangle budgets, stud-scale units, FBX export) and gets them into Studio via the 3D Importer, Open Cloud Assets API, or Studio MCP generation as a fallback. Use for any custom 3D model/mesh work for a Roblox game or Stage 4 of a one-shot build.
---

# Blender assets

Produce every `game-spec.json` -> `assets.items[]` entry, respecting
`assets.styleGuide`, and place it in the Studio world. `reference/roblox_export.py` holds
tested Blender Python helpers (`setup_scene_for_roblox`, `audit`, `apply_transforms`,
`flat_material`, `export_fbx`) to send through `execute_blender_code`.

## Roblox constraints (verified Oct 2026 against create.roblox.com)

| Constraint | Value | Source |
|---|---|---|
| Triangles per mesh | **max 20,000** (avatar items have their own budgets) | [General specifications](https://create.roblox.com/docs/art/modeling/specifications) |
| Geometry | watertight, no n-gons (quads where possible), non-zero thickness | same |
| Rig | bones scale 1 / rotation 0, root at origin, max 4 influences per vertex, no root influences | same |
| Unit scale | 1 stud = 28 cm. Set Blender **Unit System = None** so 1 BU = 1 stud | [Units](https://create.roblox.com/docs/physics/units), [Blender guide](https://create.roblox.com/docs/art/blender) |
| FBX export | Path Mode **Copy** + **Embed Textures**; **Apply Scalings = FBX Unit Scale**; disable **Add Leaf Bones**; **Bake Animation** off unless exporting animation | [Export settings](https://create.roblox.com/docs/art/modeling/export-requirements) |
| Scale alternatives | export Transform Scale **0.01**, or scene Unit Scale **0.01** (can cause Blender camera/modifier issues). glTF needs no scale tweaks | [Blender guide - Adjust scale (FBX)](https://create.roblox.com/docs/art/blender) |
| Formats | `.fbx`, `.gltf`/`.glb`, `.obj` via Importer | [Importer](https://create.roblox.com/docs/studio/importer) |
| Textures | `.png/.jpg/.tga/.bmp`, up to 4096x4096; guidance 256 px for ~5-stud props, 512 for ~10, 1024 for ~20; normal maps OpenGL tangent space | [Texture specifications](https://create.roblox.com/docs/art/modeling/texture-specifications) |

Recommended (not Roblox rules): keep props under ~1k tris, reuse one mesh for repeated
objects (instances are cheap, unique meshes are not), and prefer flat materials/vertex
colors in low-poly styles.

## Workflow (Blender MCP available)

Tool names from mcp-for-blender (https://github.com/ahujasid/mcp-for-blender):
`get_addon_status`, `get_scene_info`, `execute_blender_code`, `look`, `search_assets` /
`import_asset` (Poly Haven, Sketchfab, Poly Pizza), `generate_3d` (Tripo/Hunyuan3D/Rodin/
Meshy - premium/keys).

1. `get_addon_status` -> confirm connection. Remind the user to **save their .blend**
   first; `execute_blender_code` runs arbitrary Python. This plugin's config enables
   `BLENDER_MCP_SAFE_MODE=1`, which blocks file/network/process access but still allows
   modeling, materials, rendering, saving and import/export.
2. Start from an empty scene or a dedicated collection per asset
   (`Asset_<id>`). Run `setup_scene_for_roblox()`.
3. **Model procedurally** with `bpy` (primitives + bmesh edits + modifiers: Bevel with 1-2
   segments, Solidify, Array, Mirror, Decimate for budget). Keep pivots meaningful (bottom
   center for props that sit on the ground) and dimensions in studs from
   `approxSizeStuds`.
   - Shortcut: `search_assets` on Poly Pizza for CC0 low-poly bases, then adapt. Record the
     license/attribution in `assets.items[].usage`. Never import assets with unclear
     licenses.
   - `generate_3d` only if the user has it enabled; always re-topologize/decimate to budget.
4. **Materials:** one material per color slot via `flat_material(name, hex)` using the style
   guide palette. For textures, keep a single atlas per asset where possible.
5. **Check visually**: `look` with `angles` (multi-view) in `solid` and `wireframe`. Fix
   silhouette and proportions before details.
6. **Audit**: `audit({"<name>": budget})` - must report OK (no over-limit, applied scale,
   no n-gons). Use `apply_transforms([...])` and triangulate/decimate as needed.
7. **Export**: `export_fbx("<project>/exports/<id>.fbx", [names])`. One FBX per asset (or one
   per logical model). Remote agents: the path is on the **user's PC** (Blender runs there),
   so use a folder the user can find, e.g. `~/grok-studio/<slug>/exports`.
8. Set `assets.items[].status = "exported"`.

## Getting the mesh into Studio

Pick the first option that works:

1. **Studio 3D Importer (most reliable, needs the user's hands):** ask the user to use
   File > Import 3D (or Avatar/Home > Import 3D), choose the FBX, keep **Scale Unit =
   Stud**, enable **Insert Using Scene Position** if layout matters, then Import. Then
   continue yourself: find it with `search_game_tree`, rename, reparent to
   `ReplicatedStorage.Assets` (templates) or `Workspace.Map`.
2. **Open Cloud Assets API (automatable, needs an API key from the user):**
   `POST https://apis.roblox.com/assets/v1/assets` (multipart: `request` JSON with
   `assetType: "Model"`, `displayName`, `description`,
   `creationContext.creator.userId|groupId`; `fileContent` with `type=model/fbx`) and header
   `x-api-key`. Poll `GET https://apis.roblox.com/assets/v1/operations/{operationId}` until
   `done: true`, read `response.assetId`. Models upload as **packages**. Then
   `insert_asset` (Studio MCP) with the numeric ID. API key needs the Assets API with
   read/write permission. Source:
   https://create.roblox.com/docs/cloud/guides/usage-assets . Run the HTTP call from the
   machine that has the FBX (the user's PC via a shell, or upload the file to your
   workspace first). Never store the key in the place or the repo.
3. **Roblox Blender plugin** (optional, user-installed): pushes assets from Blender straight
   to Studio via Open Cloud - https://create.roblox.com/docs/art/modeling/roblox-blender-plugin .

## Fallback: no Blender

Use Studio MCP generation, in this order of control:
- `generate_procedural_model` - primitive-part models (blocks/wedges/cylinders) with
  attributes; great for buildings, furniture, platforms. Wait with `wait_job_finished`.
- `generate_mesh` - AI textured mesh from a text prompt (pass the style guide: "flat-shaded
  low-poly, palette ..."). Check triangle count and fix scale after insertion.
- `generate_material` - custom MaterialVariants for terrain/parts.
- `search_asset` + `insert_asset` - Creator Store; prefer Roblox-verified or highly rated
  free models, then **inspect every inserted script** (`script_grep` for `require(`,
  `getfenv`, `loadstring`, `HttpService`) and delete unexpected scripts - free models are a
  common malware vector.
- Plain parts built with `execute_luau` are a fine last resort for low-poly styles.

## Placing in the world

- Templates go in `ReplicatedStorage.Assets` (client-visible) or `ServerStorage.Templates`
  (server-only); the map lives in `Workspace.Map`.
- Set `Anchored`, `CanCollide`, `CollisionFidelity` (Box/Hull for simple props,
  PreciseConvexDecomposition only when needed), `CastShadow` off for tiny props,
  `RenderFidelity = Automatic`.
- Add `CollectionService` tags from the spec (`Coin`, `Lava`, `Checkpoint`) so code picks
  them up.
- Group multi-part assets in a `Model` with `PrimaryPart` set; use `PivotTo` for placement.
- Record `instancePath`/`assetId`, set `status = "placed"`, then `screen_capture` an
  overview for the checkpoint.
