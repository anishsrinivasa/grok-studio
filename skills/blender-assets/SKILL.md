---
name: blender-assets
description: Makes Roblox-ready low-poly 3D models in Blender - headless Blender on the bots' cloud computer (or the user's Blender through the Blender MCP), one .blend per asset with numbered checkpoints and rollback, a rendered multi-view review sheet checked against the spec each round, triangle budgets, stud-scale units and FBX export - then gets them into Studio through Open Cloud or the 3D Importer. Use for any custom mesh, rig base or prop made in Blender for a Roblox game.
---

# Blender assets

Turn `game-spec.json` -> `assets.items[]` entries with `source: "blender"` into Roblox models,
following `assets.styleGuide`. Builder owns models; Animator uses the same tools for rigs
and animation files (see `roblox-animations`). Follow `team-protocol`: **one writer per
.blend**. Never open another Bot's .blend for writing.

Not every asset needs Blender: blocky/primitive styles are faster and safer as Studio parts
or procedural models. See `roblox-building`. Use Blender for custom silhouettes: organic
props, characters, vehicles, anything parts can't express.

Files next to this skill (`reference/`):

| File | What |
|---|---|
| `cloud_blender.sh` | install / probe / run headless Blender on the cloud computer |
| `asset_harness.py` | `open_asset`, `checkpoint`, `rollback`, `review_sheet`, `export_asset`, `job_args`, ... |
| `roblox_export.py` | `setup_scene_for_roblox`, `audit`, `apply_transforms`, `flat_material`, `export_fbx` |

Upload helper: `<plugin>/scripts/opencloud_upload.py`. File-to-PC helper:
`<plugin>/scripts/send-to-pc.py` (`team-protocol` section 7). `<plugin>` = the folder that
holds `skills/`.

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
| Open Cloud upload | Model: `.fbx .gltf .glb .rbxm .rbxmx`, uploads as a **package**; max 20 MB | [Assets usage guide](https://create.roblox.com/docs/cloud/guides/usage-assets) |

Recommended (not Roblox rules): props under ~1k tris, one mesh reused for repeated objects
(instances are cheap, unique meshes are not), flat materials / vertex colours for low-poly.

## Which Blender

| You are | Use |
|---|---|
| a Grok Bot (cloud computer, no screen) | **Cloud mode**: headless Blender via `cloud_blender.sh`, jobs are Python files |
| a local agent with the Blender MCP (`get_addon_status` answers) | **Local mode**: `execute_blender_code` + `look` on the user's Blender, same helpers |

### Cloud mode: setup (once per cloud computer; the Lead's setup usually did it)

```bash
B=<plugin>/skills/blender-assets/reference/cloud_blender.sh
bash $B version || bash $B install   # Blender 5.2.2 LTS, ~380 MB, sha256-checked, into /workspace/grok-studio/.tools
bash $B probe                        # which render engine works headless: Workbench > EEVEE > Cycles CPU
```

`install` is idempotent and safe if two Bots run it at once. If Blender is unpacked but
won't start, it lists the missing system libraries and the `apt-get` line that fixes them
(a minimal Ubuntu needs the X11/GL client libraries even headless). Re-run `install`
afterwards: it reuses the unpacked files. `BLENDER_VERSION=5.0.1` selects the other
pinned build (the one Grok Bot already ran on its cloud computer).

### Cloud mode: jobs

Each step is a small Python file run in a fresh headless Blender:

```bash
bash $B run /workspace/grok-studio/games/<slug>/blender/<id>/job_<step>.py -- --id <id>
```

The runner puts `reference/` on `sys.path`, exits non-zero if the script raises, and passes
everything after `--` to the job (`job_args()` -> dict). Keep job files next to the
checkpoints (`blender/<id>/job_*.py`) so the history is readable. A job only keeps what it
saves: every job starts with `open_asset(...)` and ends with `checkpoint(...)` or
`save_asset(...)`. Results are printed as `GS_RESULT {json}` lines (`print_json`).

```python
# job_blockout.py
import bpy
from asset_harness import *

a = open_asset(job_args()["id"])            # <id>.blend, or a new empty stud-scale scene
bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.6, depth=4, location=(0, 0, 2))
trunk = bpy.context.active_object
trunk.name = "Trunk"
trunk.data.materials.append(bpy.data.materials[flat_material("Bark", "#7A4E2D")])
link_to_asset(a, trunk)                      # everything of the asset lives in Asset_<id>
print(checkpoint(a, "blockout"))             # saves <id>.blend + blender/<id>/00_blockout.blend
print_json(review_sheet(a))                  # renders renders/<id>_review_01.png
print(audit(names=asset_object_names(a)))
```

### Local mode (Blender MCP)

Tools (mcp-for-blender): `get_addon_status`, `get_scene_info`, `execute_blender_code`,
`look`, `search_assets` / `import_asset` (Poly Haven, Sketchfab, Poly Pizza),
`generate_3d` (paid/keyed). `execute_blender_code` runs Python in the user's open Blender,
so ask them to save their own work first. With `BLENDER_MCP_SAFE_MODE=1` (this plugin's
default) file/network/process access is blocked but modeling, rendering, saving and
import/export still work. Send the helper source with your code (paste the functions you
need from `roblox_export.py` / `asset_harness.py` with the helpers they call, e.g. `audit`
needs `triangle_count` and `_non_manifold_edges`), use the same layout under
`<project>/grok-studio/games/<slug>/`, and use `look` for quick checks in addition to the
review sheet. `search_assets` on Poly Pizza can give a CC0 base. Record its license in
`assets.items[].usage` and never import assets with unclear licenses.

## The asset loop

For each asset in your task:

1. **Read the brief**: `approxSizeStuds`, `triangleBudget`, the palette and style in
   `assets.styleGuide`, and what the asset is for (`usage`). Pivot convention: origin at the
   bottom centre for props that sit on the ground, object at the world origin.
2. **Blockout** with primitives + bmesh + modifiers (Bevel 1-2 segments, Solidify, Array,
   Mirror, Decimate for budget). Shapes and proportions first, no detail. Put every object
   in `Asset_<id>` (`link_to_asset`). Materials: `flat_material(name, hex)` per palette
   colour. Save a checkpoint (`checkpoint(a, "blockout")`).
3. **Review round** (repeat, max 4 rounds):
   1. `review_sheet(a)` -> look at the PNG it names. Layout, left to right, top row first:
      front, right side, top (all orthographic, true proportions), 3/4 view with a grey
      5-stud figure for scale (a default avatar is ~5 studs), 3/4 wireframe (edge density),
      back 3/4. The result also gives `size_studs` and `triangles`.
   2. Critique against the brief in a few bullets: **silhouette** (readable as a 150 px
      thumbnail?), **proportions** (match `approxSizeStuds`? right size next to the 5-stud
      figure?), **palette** (only style-guide colours, flat shading, enough contrast between
      parts), **budget** (triangles <= `triangleBudget`, wireframe not denser than needed),
      **construction** (nothing floating, no visible gaps, pivot where it belongs).
   3. Fix the worst 1-3 problems in a new job, `checkpoint(a, "<what changed>")`, review
      again.
   4. Stop when the critique has nothing important left, or after round 4. Report what
      is still imperfect instead of looping.
   Workbench colours are the closest to Roblox's flat look. Cycles (the fallback when the
   computer has no GPU) renders lighter and softer, so judge the palette by hex values, not
   by eye.
4. **Rollback rule:** if a round made the model worse, or a job broke geometry, go back to
   the last good checkpoint instead of patching on top: `rollback(a, <n>)` (no Blender
   needed: `python3 -c "import sys; sys.path.insert(0,'<reference>'); import asset_harness as h; print(h.rollback(h.asset_paths('<id>'), <n>))"`).
   Checkpoints are never edited or deleted while the task is open. The next checkpoint
   after a rollback gets the next free number, so the history stays linear.
5. **Audit** - `audit({"<name>": budget}, names=asset_object_names(a))`: every line must
   end in `OK`. Fix n-gons by triangulating or quad-ing (a Triangulate modifier is fine for
   low-poly), unapplied scale with `apply_transforms`, holes by closing or Solidify.
6. **Export** - `export_asset(a)` -> `exports/<id>.fbx` (FBX Unit Scale, Y-up, no leaf
   bones, embedded textures). One FBX per asset. Set `assets.items[].status = "exported"`.

Tested headless with Blender 5.2.2: a 3-object prop from empty scene to two checkpoints,
two review sheets and an FBX in ~6 s, both on Windows and in a GPU-less Ubuntu 24.04
container (Workbench renders there through Mesa's software GL; ignore the `EGL Error
0x3009` lines it prints). Review sheet: Workbench 0.7-3 s, EEVEE ~6 s, Cycles CPU
(12 samples) ~7 s on a fast laptop CPU; expect a slower cloud CPU to be a few times slower.

## Getting the model into Studio

Pick the first that applies, then continue at "Placing" below.

1. **Open Cloud key available** (the Lead set `ROBLOX_OPEN_CLOUD_API_KEY` and
   `ROBLOX_CREATOR_USER_ID` or `ROBLOX_CREATOR_GROUP_ID` as secrets during setup):
   ```bash
   python3 <plugin>/scripts/opencloud_upload.py /workspace/grok-studio/games/<slug>/exports/<id>.fbx --name "<Display Name>"
   # -> {"assetId": "1234567890", "assetType": "Model", ...}
   ```
   (`--dry-run` shows the request without sending it.) Then `insert_asset` with that id
   (Studio MCP). Models arrive as packages. The creator must be the game's owner (user or
   group), or the game can't use the asset. Record `assets.items[].assetId`, status
   `imported`.
2. **No key:** copy the file to the user's PC and ask for one click.
   ```bash
   python3 <plugin>/scripts/send-to-pc.py /workspace/grok-studio/games/<slug>/exports/<id>.fbx exports/<id>.fbx
   # -> {"localPath": "C:\\Users\\...\\grok-studio\\drop\\exports\\<id>.fbx", ...}
   ```
   Send the Lead an `ASK` with the exact `localPath`. The Lead asks the user to do **File >
   Import 3D**, pick that file, keep **Scale Unit = Stud**, and Import. Batch several files
   into one request where you can. Once the user says it's done, find the new model with
   `search_game_tree` (it lands in Workspace) and move on. Status `imported`.
3. **No bridge file drop and no key:** report `BLOCKED` to the Lead with the export path.
   Meanwhile the asset can be rebuilt Studio-natively (`roblox-building`), if the spec
   allows.

Local agents on the user's PC have the FBX on disk already: use path 1 from the PC, or ask
the user for the Import 3D click directly.

## Placing (Builder)

- Templates go to `ReplicatedStorage.Assets.Models` (client-visible) or
  `ServerStorage.Templates` (server-only). Map pieces go under `Workspace` (see
  `roblox-building` for map layout). Rename the imported model to the asset `id`.
- Set `Anchored`, `CanCollide`, `CollisionFidelity` from the spec (Box/Hull for simple
  props, PreciseConvexDecomposition only when needed), `CastShadow` off for tiny props,
  `RenderFidelity = Automatic`.
- Add the spec's `CollectionService` tags (`Coin`, `Lava`, `Checkpoint`) so Coding's code
  picks them up. Never edit scripts yourself.
- Multi-part models: a `Model` with `PrimaryPart` set; place with `PivotTo`.
- Check the triangle count in Studio if in doubt (`inspect_instance`), take an Edit-mode
  `screen_capture`, record `instancePath`, set `status = "placed"`.

## Spec updates

`assets.items[].status`: `planned` -> `modeled` (review passed) -> `exported` ->
`imported` -> `placed`. Write only your own items, under the `spec` lock
(`team-protocol` section 3).
