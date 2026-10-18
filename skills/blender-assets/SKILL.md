---
name: blender-assets
description: Makes Roblox-ready low-poly 3D models in headless Blender on the bots' cloud computer (the user's own Blender through the Blender MCP is an opt-in extra) and gets them into Studio through quality gates - checkpoints and review renders while modeling, audit, split by material, FBX + manifest export, Open Cloud upload, insert_asset, apply manifest, post-import check, render-vs-capture comparison - before an asset counts as placed. Use for any custom mesh, rig base or prop made in Blender for a Roblox game.
---

# Blender assets

Turn `game-spec.json` -> `assets.items[]` entries with `source: "blender"` into Roblox models,
following `assets.styleGuide`. Builder owns models; Animator uses the same tools for rigs and
animation files (`roblox-animations`). Follow `team-protocol`: **one writer per .blend**.

Not every asset needs Blender: blocky/primitive styles are faster as Studio parts or
procedural models (`roblox-building`). Use Blender for custom silhouettes: organic props,
characters, vehicles, anything parts can't express.

**Cloud first.** Blender runs headless on the cloud computer (`cloud_blender.sh`), and the
Open Cloud upload runs there too (the key is an environment variable). The user's own Blender
through the Blender MCP is an opt-in extra (section "Opt-in: the user's Blender").

## Files (`reference/` next to this skill)

| File | Runs in | What |
|---|---|---|
| `cloud_blender.sh` | cloud shell | `install` / `probe` / `run` / `version` headless Blender |
| `asset_harness.py` | cloud jobs | paths, `open_asset`, `checkpoint`, `rollback`, `review_sheet`, `split_by_material`, `export_asset`, `write_manifest`, `render_compare`, `compare_capture` |
| `gs_core.py` | any Blender (safe-mode clean) | scene setup, `flat_material`, `audit`, `split_by_material`, `asset_manifest`, `export_fbx`, `smoke_build` |
| `compare_images.py` | any Blender (safe-mode clean) | `render_compare`, `compare_camera`, `compare_images` |
| `smoke_test.py` | cloud job | setup's readiness gate |
| `apply_manifest.luau` | Studio, `execute_luau` Edit | name, colours, materials, physics, pivot, attributes |
| `post_import_check.luau` | Studio, `execute_luau` Edit | pass/fail checks, read-only |
| `capture_booth.luau` | Studio, `execute_luau` Edit | clean shot for the comparison |

`<plugin>/scripts/opencloud_upload.py` uploads, `<plugin>/scripts/send-to-pc.py` copies a file to
the user's PC (`team-protocol` section 7). `<plugin>` = the folder that holds `skills/`.

## Roblox constraints (verified Oct 2026 against create.roblox.com)

| Constraint | Value | Source |
|---|---|---|
| Triangles per mesh | **max 20,000** (avatar items have their own budgets) | [General specifications](https://create.roblox.com/docs/art/modeling/specifications) |
| Geometry | watertight, no n-gons (quads where possible), non-zero thickness | same |
| Rig | bones scale 1 / rotation 0, root at origin, max 4 influences per vertex, no root influences | same |
| Unit scale | 1 stud = 28 cm. Blender **Unit System = None** so 1 BU = 1 stud | [Units](https://create.roblox.com/docs/physics/units), [Blender guide](https://create.roblox.com/docs/art/blender) |
| FBX export | Path Mode **Copy** + **Embed Textures**; **Apply Scalings = FBX Unit Scale**; no **Leaf Bones**; **Bake Animation** only for animation | [Export settings](https://create.roblox.com/docs/art/modeling/export-requirements) |
| Formats | `.fbx`, `.gltf`/`.glb`, `.obj` via Importer | [Importer](https://create.roblox.com/docs/studio/importer) |
| Textures | `.png/.jpg/.tga/.bmp`, up to 4096x4096 | [Texture specifications](https://create.roblox.com/docs/art/modeling/texture-specifications) |
| Open Cloud upload | Model: `.fbx .gltf .glb .rbxm .rbxmx`, uploads as a **package**; max 20 MB | [Assets usage guide](https://create.roblox.com/docs/cloud/guides/usage-assets) |
| One colour per MeshPart | a MeshPart has one `Color` and one `Material`, hence the split by material | Studio |

Recommended (not Roblox rules): props under ~1k tris, one mesh reused for repeated objects,
flat materials for low-poly.

## Setup (once per cloud computer; the Lead's setup runs it)

```bash
B=<plugin>/skills/blender-assets/reference/cloud_blender.sh
bash $B version || bash $B install   # Blender 5.2.2 LTS, ~380 MB, sha256-checked, into /workspace/grok-studio/.tools
bash $B probe                        # headless render engine: Workbench > EEVEE > Cycles CPU
bash $B run <plugin>/skills/blender-assets/reference/smoke_test.py   # readiness gate, prints GS_RESULT {"ok": true, ...}
python3 <plugin>/scripts/opencloud_upload.py introspect               # if the key is set: scopes, expiry, owner id
```

`install` is idempotent and safe if two Bots run it at once. If Blender won't start it lists
the missing libraries and the `apt-get` line that fixes them, then re-run `install` (it
reuses the unpacked files). `BLENDER_VERSION=5.0.1` selects the other pinned build. The smoke
test builds a 2-material block, splits it, audits, exports FBX + manifest and renders, in
about 5 s (exit code 1 if anything fails). `introspect` prints the key's owner
(`authorizedUserId`): save it as `ROBLOX_CREATOR_USER_ID` (or set `ROBLOX_CREATOR_GROUP_ID`
for a group-owned game). It needs Assets **read + write**.

## Jobs

Every Blender step is a small Python file run in a fresh headless Blender:

```bash
bash $B run /workspace/grok-studio/games/<slug>/blender/<id>/job_<step>.py -- --id <id>
```

The runner puts `reference/` on `sys.path`, exits non-zero if the script raises, and passes
the arguments after `--` to `job_args()`. Keep job files next to the checkpoints
(`blender/<id>/job_*.py`). A job keeps only what it saves: start with `open_asset(...)`, end
with `checkpoint(...)` or `save_asset(...)`. Results print as `GS_RESULT {json}` lines.

```python
# job_blockout.py
import bpy
from asset_harness import *

a = open_asset(job_args()["id"])            # <id>.blend, or a new empty stud-scale scene
bpy.ops.mesh.primitive_cylinder_add(vertices=8, radius=0.6, depth=4, location=(0, 0, 2))
trunk = bpy.context.active_object
trunk.name = "Trunk"
trunk.data.materials.append(bpy.data.materials[flat_material("Bark", "#7A4E2D", roblox_material="Wood")])
link_to_asset(a, trunk)                      # everything of the asset lives in Asset_<id>
print(checkpoint(a, "blockout"))             # saves <id>.blend + blender/<id>/00_blockout.blend
print_json(review_sheet(a))                  # renders renders/<id>_review_01.png
print(audit(names=asset_object_names(a)))
```

`flat_material(name, hex, roughness, metallic, roblox_material=None)`: the Roblox Material
(`"Wood"`, `"Neon"`, `"Metal"`, ...) goes into the manifest; default SmoothPlastic
(`Metal` when metallic >= 0.5).

## The pipeline - every gate must pass before `placed`

A failed gate blocks the next step. Fix the cause and redo from the step that produced it.
Write the JSON results of steps 7-10 to `reports/<id>_import.json` and summarise them in
your `DONE` message.

### 1. Model with checkpoints and review rounds

1. **Read the brief**: `approxSizeStuds`, `triangleBudget`, palette and style, `usage`.
   Pivot convention: the manifest's pivot is the bottom centre of the bounds, so model props
   standing on the ground at z = 0.
2. **Blockout** with primitives + bmesh + modifiers (Bevel 1-2 segments, Solidify, Array,
   Mirror, Decimate). Shapes and proportions first. Every object in `Asset_<id>`
   (`link_to_asset`). One `flat_material` per palette colour. `checkpoint(a, "blockout")`.
3. **Review rounds** (max 4): `review_sheet(a)` -> look at the PNG. Layout (left to right, top
   row first): front, right side, top (orthographic), 3/4 with a grey 5-stud figure for
   scale, 3/4 wireframe, back 3/4. Critique in a few bullets: **silhouette** (readable at
   150 px?), **proportions** (match `approxSizeStuds`; size next to the 5-stud figure),
   **palette** (style-guide colours only, flat, parts distinguishable), **budget** (tris vs
   `triangleBudget`, wireframe no denser than needed), **construction** (nothing floating, no
   gaps). Fix the worst 1-3 problems, checkpoint, review again. Stop when nothing important
   is left, or after round 4, and report what is still imperfect. Judge colours by hex, not
   by eye: Cycles (the no-GPU fallback) renders lighter than Workbench.
4. **Rollback rule:** if a round made it worse or broke geometry, return to the last good
   checkpoint instead of patching: `rollback(a, <n>)` (also works without Blender:
   `python3 -c "import sys; sys.path.insert(0,'<reference>'); import asset_harness as h; print(h.rollback(h.asset_paths('<id>'), <n>))"`).
   Checkpoints are never edited or deleted while the task is open.

### 2. Gate A - audit

`audit({"<name>": budget}, names=asset_object_names(a))`: every line ends in `OK` (no
over-budget mesh, applied scale, no n-gons, watertight, a material on everything). Fix n-gons
with a Triangulate modifier or quads, scale with `apply_transforms`, holes by closing or
Solidify. Status `modeled`.

### 3. Split by material + manifest

```python
split_by_material(a, collision="Hull")   # spec collision: Default | Hull | Box | PreciseConvexDecomposition | none
print(audit(names=asset_object_names(a), allow_open=True))   # parts cut out of a closed mesh are open: fine
```

One object per material, named `<id>_<Material>` (pieces with the same material merge into
one part; `merge_same_material=False` keeps them apart). Rotation/scale are baked in, each
part's origin is its bounding-box centre. It writes `exports/<id>.manifest.json`: per part
name, hex colour, Roblox material, size and position in studs (Roblox axes, relative to the
bottom-centre pivot), triangles; for the asset size, pivot, triangle total, primary part,
Anchored/CanCollide/CollisionFidelity (`anchored=False`, `can_collide=False` also work).
Don't split skinned meshes (rigs). Checkpoint after.

### 4. Export

`export_asset(a)` -> `exports/<id>.fbx` and a refreshed manifest. It refuses a mesh that still
has more than one material. Status `exported`.

### 5. Upload (cloud, key in the environment)

```bash
python3 <plugin>/scripts/opencloud_upload.py upload /workspace/grok-studio/games/<slug>/exports/<id>.fbx --name "<id>"
# -> {"assetId": "1234567890", "assetType": "Model", "moderation": ...}
```

It waits until Roblox has processed the upload (`--no-wait` + `status <operationId> --wait`
for long ones; `--dry-run` shows the request). The creator must be the game's owner, or the
game can't use the asset.

**No key:** `python3 <plugin>/scripts/send-to-pc.py <fbx> exports/<id>.fbx`, then send the Lead
an `ASK` with the printed `localPath`: the user does **File > Import 3D** with that file
(**Scale Unit = Stud**) and tells you where it landed. Batch several files into one request.
Then continue at step 7 with that model's path.

### 6. Insert

`insert_asset` with `assetId`, `assetName = "<id>"`, `parentPath = "game.Workspace"`. Find
it with `search_game_tree` if unsure. Status `imported`.

### 7. Apply the manifest

Send `reference/apply_manifest.luau` through `execute_luau` (Edit) with `MANIFEST_JSON` = the
manifest file's contents and `MODEL_PATH` = the model (e.g. `"Workspace.<id>"`). It renames
the model to the id, matches each MeshPart to a manifest part (exact name, case-insensitive,
contained name, then closest size), sets Color / Material / Anchored / CanCollide /
CollisionFidelity, clears textures that would hide the colour, sets PrimaryPart, a
bottom-centre `WorldPivot` and the `BuiltBy` / `GsAssetId` attributes. It is safe to re-run.
**Gate B:** `ok: true` (no `missing`, no `extra`).

### 8. Gate C - post-import check

Send `reference/post_import_check.luau` the same way. Read-only. **`pass: true`** required:
part count and names, only MeshParts in the model, sizes and positions (tolerance 0.05
studs + 3 %), colours (3/255 per channel), materials, no texture hiding the colour,
physics, pivot at the bottom centre, model bounds = manifest size, no scripts, **no plain
Parts layered on or coincident with the MeshParts and no duplicate coincident parts**, and no
loose copies of the asset's parts outside a copy of the asset. Checked in Workspace (a
template in ReplicatedStorage is checked without the world-overlap scan). A size that
matches only with axes swapped means the import came in rotated: check the export axes.

### 9. Gate D - render vs Studio capture

1. Cloud job: `print_json(render_compare(a, "three_quarter"))` (also `"front"` for flat
   props) -> `renders/<id>_compare_<view>.png`, plus `studio` (camera offsets from the pivot
   and field of view) and `backdrop` (a colour far from every part colour).
2. `reference/capture_booth.luau` (Edit) with `MODEL_PATH`, `CAMERA_JSON` = that `studio`
   object, `BACKDROP` = that colour, `MODE = "setup"`. It clones the model into
   `Workspace._GS_CaptureBooth` high above the map, unrotated and shadowless, in front of a
   flat backdrop. It returns `camera_position` / `look_at_position`. If it reports
   `fovMatches: false`, re-render with `fov=<its fieldOfView>`.
3. `screen_capture` with those two positions. Save the image as
   `renders/<id>_capture_<view>.png`.
4. Cloud job: `print_json(compare_capture(a, "<capture png>", "three_quarter"))` ->
   `pass`, plus `silhouette.iouNormalized` (>= 0.80) and `color.intersection` (>= 0.70).
   Silhouette and colour are normalised for framing, so a wrong shape, a missing part, a
   wrong orientation or a wrong colour fails; Studio's different lighting and window size
   don't.
5. **Also look at both images yourself** and say what differs.
6. `capture_booth.luau` with `MODE = "cleanup"`. Always run it, even after a failure.

If your client gives you the capture only as an image and you can't save it as a file, do
step 5 alone and write "numeric compare unavailable" in the report. The visual check then
is the gate.

### 10. Place

Move or clone the model to where it belongs: `ReplicatedStorage.Assets.Models.<id>` for
templates (cloned at runtime), `ServerStorage.Templates` for server-only ones, or the map
under `Workspace`. Add the spec's `CollectionService` tags (`Coin`, `Lava`, `Checkpoint`) so
Coding's code finds them, and never edit scripts yourself. After placing copies in the
world, run `post_import_check.luau` on one placed copy (it catches coincident duplicates and
overlays in the world). Record `instancePath` (and `assetId`), set `status = "placed"`, take
an Edit-mode `screen_capture` for the checkpoint.

Status flow: `planned` -> `modeled` (gate A) -> `exported` -> `imported` -> `placed` (gates
B, C, D). Write only your own items, under the `spec` lock (`team-protocol` section 3).

## Opt-in: the user's Blender (Blender MCP)

Only when the user chose it (the Lead says so). Tools (mcp-for-blender):
`get_addon_status`, `get_scene_info`, `execute_blender_code`, `look`, `search_assets` /
`import_asset` (Poly Haven, Sketchfab, Poly Pizza; record CC0 licences in
`assets.items[].usage`), `generate_3d` (paid/keyed).

- The plugin runs it with `BLENDER_MCP_SAFE_MODE=1`: only bpy, bmesh, mathutils and plain
  stdlib modules (no os/sys/numpy/open/exec, no lambdas or classes). `gs_core.py` and
  `compare_images.py` are written for that and checked against the add-on's own validator.
  `asset_harness.py`, `review_sheet` and `smoke_test.py` are cloud-only.
- Every `execute_blender_code` call starts from an empty namespace: send the whole
  `gs_core.py` (and `compare_images.py` when needed) followed by one call that prints a
  marker line, e.g. `print("GS_RESULT " + json.dumps(split_by_material("<id>")))` or
  `print("GS_RESULT " + json.dumps(asset_manifest("<id>", collision="Hull")))`, and read the
  `GS_RESULT` line (exporters print their own lines too).
- Safe mode has no file API, so functions return dicts: write the manifest file yourself.
  Folders are created by `ensure_dir` (FBX and .blend writers don't create them).
  `smoke_build("<folder>")` is the readiness gate there.
- Review with `look` instead of `review_sheet`. Checkpoint with
  `bpy.ops.wm.save_as_mainfile(filepath=..., copy=True)`. Ask the user to save their own work
  first.
- The FBX ends up on the user's PC, so the user's File > Import 3D is the natural import
  (the Open Cloud key lives on the cloud computer). Steps 6-10 are the same.

## Tests (Oct 2026)

Blender 5.2.2, headless:
- **Smoke test:** ~4.7 s in-job (~10 s with Blender start-up).
- **Split + manifest + FBX:** a 4-part tree took ~1 s. The two leaf blobs merged, and a
  rotated 2-material sign split cleanly.
- **Comparison** against simulated Studio captures (Cycles lighting, 16:9, magenta backdrop):
  - the correct model passed: silhouette 0.94-0.96, colour 0.82-0.92
  - a wrong colour (0.24), a wrong shape (0.55) and a 90° rotation (0.73) all failed
- **The Luau scripts** run in Lune on a synthetic place and type-check with luau-lsp:
  - apply matched importer-style names
  - the check passed the good import and a second copy, and failed overlays, coincident
    duplicates, extra parts, wrong size, wrong colour and scripts
- **Not yet checked:** Studio itself, and Roblox's real FBX import axes. The positions and
  sizes checks will catch a mismatch on the first real import.
