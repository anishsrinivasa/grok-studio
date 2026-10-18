"""
asset_harness.py - one asset per .blend, numbered checkpoints, rollback, review sheets.

Layout (see skills/team-protocol):
    <GS_ROOT>/games/<slug>/blender/<id>.blend          the working file (one writer only)
    <GS_ROOT>/games/<slug>/blender/<id>/NN_<label>.blend  checkpoints, never edited
    <GS_ROOT>/games/<slug>/renders/<id>_review_NN.png   review sheets
    <GS_ROOT>/games/<slug>/exports/<id>.fbx             export
GS_ROOT defaults to /workspace/grok-studio; the slug defaults to the `current-game` file.

A job script (run with `cloud_blender.sh run job.py -- --id lava_rock`):

    from asset_harness import *
    a = open_asset(job_args()["id"])           # opens <id>.blend, or starts an empty one
    ...model inside collection a["collection"]...
    checkpoint(a, "blockout")
    print(review_sheet(a))                      # look at the PNG it names
    print(audit(names=asset_object_names(a)))
    print(export_asset(a))

Every job runs in a fresh Blender process: open_asset() at the start, and whatever the job
changes is lost unless it calls save_asset() or checkpoint(). The objects that make up the
asset live in the collection "Asset_<id>". Review and export use only that collection.

list_checkpoints() and rollback() also work in plain Python (no Blender needed).
"""
import json
import math
import os
import re
import shutil
import sys
import tempfile
import time

try:
    import bpy
    from mathutils import Vector
    from roblox_export import (  # noqa: F401  (re-exported for job scripts)
        ROBLOX_TRI_LIMIT, apply_transforms, audit, export_fbx, flat_material,
        setup_scene_for_roblox, triangle_count,
    )
except ImportError:  # plain Python: checkpoint listing and rollback only
    bpy = None

GS_ROOT = os.environ.get("GS_ROOT", "/workspace/grok-studio")

REVIEW_LAYOUT = [
    "front (from -Y, ortho)", "right side (from +X, ortho)", "top (from +Z, ortho)",
    "3/4 view with a 5-stud figure for scale", "3/4 wireframe (edge density)", "back 3/4",
]


# --------------------------------------------------------------------------- paths & args

def job_args(argv=None):
    """Parse the arguments after `--` as --key value pairs (a bare --flag becomes True)."""
    argv = sys.argv if argv is None else argv
    rest = argv[argv.index("--") + 1:] if "--" in argv else []
    out, i = {}, 0
    while i < len(rest):
        key = rest[i]
        if not key.startswith("--"):
            raise SystemExit(f"job_args: unexpected argument {key!r}")
        key = key[2:].replace("-", "_")
        if i + 1 < len(rest) and not rest[i + 1].startswith("--"):
            out[key] = rest[i + 1]
            i += 2
        else:
            out[key] = True
            i += 1
    return out


def current_slug(root=None):
    root = root or GS_ROOT
    try:
        with open(os.path.join(root, "current-game"), encoding="utf-8") as f:
            slug = f.read().strip()
    except FileNotFoundError:
        raise SystemExit(f"no {root}/current-game file: pass slug= or ask the Lead which game this is")
    if not slug:
        raise SystemExit(f"{root}/current-game is empty")
    return slug


def asset_paths(asset_id, slug=None, root=None):
    """All paths for one asset (or rig/animation) id. Creates the folders."""
    if not re.fullmatch(r"[A-Za-z0-9_-]+", asset_id or ""):
        raise SystemExit(f"asset id must be letters, digits, _ or - (got {asset_id!r})")
    root = root or GS_ROOT
    game = os.path.join(root, "games", slug or current_slug(root))
    p = {
        "id": asset_id,
        "game": game,
        "blend": os.path.join(game, "blender", f"{asset_id}.blend"),
        "checkpoints": os.path.join(game, "blender", asset_id),
        "renders": os.path.join(game, "renders"),
        "exports": os.path.join(game, "exports"),
        "fbx": os.path.join(game, "exports", f"{asset_id}.fbx"),
        "collection": f"Asset_{asset_id}",
    }
    for key in ("checkpoints", "renders", "exports"):
        os.makedirs(p[key], exist_ok=True)
    return p


# --------------------------------------------------------------------------- checkpoints

def list_checkpoints(paths):
    """[(number, label, path)] oldest first."""
    out = []
    if os.path.isdir(paths["checkpoints"]):
        for name in os.listdir(paths["checkpoints"]):
            m = re.fullmatch(r"(\d{2,})_([a-z0-9-]+)\.blend", name)
            if m:
                out.append((int(m.group(1)), m.group(2), os.path.join(paths["checkpoints"], name)))
    return sorted(out)


def rollback(paths, number=None):
    """Make checkpoint `number` (default: the newest) the working file again.

    Works without Blender (it is a file copy). Inside a Blender job, the checkpoint is also
    reopened so the job continues from it. Later checkpoints are kept, not deleted.
    """
    cps = list_checkpoints(paths)
    if not cps:
        raise SystemExit(f"no checkpoints for {paths['id']}")
    pick = cps[-1] if number is None else next((c for c in cps if c[0] == int(number)), None)
    if pick is None:
        raise SystemExit(f"no checkpoint {number} for {paths['id']}; have {[c[0] for c in cps]}")
    shutil.copyfile(pick[2], paths["blend"])
    if bpy is not None:
        bpy.ops.wm.open_mainfile(filepath=paths["blend"])
    return f"rolled back {paths['id']} to checkpoint {pick[0]:02d}_{pick[1]}"


# --------------------------------------------------------------------------- Blender-only

def _require_bpy():
    if bpy is None:
        raise SystemExit("this function needs Blender (run it with cloud_blender.sh run)")


def open_asset(asset_id, slug=None, root=None, fresh=False):
    """Open <id>.blend, or start an empty stud-scale scene if it doesn't exist (or fresh=True).

    Returns the asset_paths() dict. The asset's objects go in collection paths["collection"].
    """
    _require_bpy()
    paths = asset_paths(asset_id, slug, root)
    if os.path.exists(paths["blend"]) and not fresh:
        bpy.ops.wm.open_mainfile(filepath=paths["blend"])
    else:
        bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.preferences.filepaths.save_version = 0  # no .blend1 clutter in /workspace
    setup_scene_for_roblox()
    asset_collection(paths)
    return paths


def asset_collection(paths):
    """The Asset_<id> collection (created and linked to the scene if missing)."""
    _require_bpy()
    name = paths["collection"]
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
    if coll.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(coll)
    return coll


def link_to_asset(paths, obj):
    """Move an object into the asset collection (out of every other collection)."""
    coll = asset_collection(paths)
    for c in list(obj.users_collection):
        if c is not coll:
            c.objects.unlink(obj)
    if obj.name not in coll.objects:
        coll.objects.link(obj)
    return obj


def asset_object_names(paths):
    _require_bpy()
    coll = bpy.data.collections.get(paths["collection"])
    return [o.name for o in coll.all_objects] if coll else []


def save_asset(paths):
    _require_bpy()
    bpy.ops.wm.save_as_mainfile(filepath=paths["blend"])
    return paths["blend"]


def checkpoint(paths, label):
    """Save the working file, then a numbered copy NN_<label>.blend. Returns the copy's path."""
    _require_bpy()
    label = re.sub(r"[^a-z0-9-]+", "-", label.lower()).strip("-") or "step"
    save_asset(paths)
    cps = list_checkpoints(paths)
    n = cps[-1][0] + 1 if cps else 0
    path = os.path.join(paths["checkpoints"], f"{n:02d}_{label}.blend")
    bpy.ops.wm.save_as_mainfile(filepath=path, copy=True)
    return path


def export_asset(paths, names=None, with_animation=False):
    """Export the asset collection (or `names`) to exports/<id>.fbx. Returns path and size."""
    _require_bpy()
    names = names or [n for n in asset_object_names(paths)
                      if bpy.data.objects[n].type in {"MESH", "ARMATURE", "EMPTY"}]
    if not names:
        raise SystemExit(f"nothing to export: collection {paths['collection']} is empty")
    export_fbx(paths["fbx"], names, with_animation=with_animation)
    return {"fbx": paths["fbx"], "bytes": os.path.getsize(paths["fbx"]), "objects": names}


# --------------------------------------------------------------------------- review sheet

def _set_engine(scene, wanted):
    """Assign a render engine by trying identifiers (they differ between Blender versions)."""
    for engine in wanted:
        try:
            scene.render.engine = engine
            return scene.render.engine
        except TypeError:
            continue
    raise SystemExit(f"none of the render engines {wanted} exist in this Blender")


def _enum_has(prop_owner, prop, value):
    try:
        return value in {i.identifier for i in prop_owner.bl_rna.properties[prop].enum_items}
    except (KeyError, AttributeError):
        return False


def _world_bounds(objs):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    lo = Vector((math.inf,) * 3)
    hi = Vector((-math.inf,) * 3)
    for obj in objs:
        ev = obj.evaluated_get(depsgraph)
        for corner in ev.bound_box:
            w = ev.matrix_world @ Vector(corner)
            lo = Vector(map(min, lo, w))
            hi = Vector(map(max, hi, w))
    return lo, hi


def _make_material(name, rgb):
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.diffuse_color = (*rgb, 1.0)
    if mat.node_tree:
        bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (*rgb, 1.0)
    return mat


def _scale_figure(coll, base, height_ref):
    """A blocky 5-stud avatar stand-in (legs 2, torso 2, head 1) standing at `base`."""
    mat = _make_material("_GS_ScaleFigure", (0.35, 0.38, 0.42))
    parts = [((0, 0, 1.0), (2, 1, 2)), ((0, 0, 3.0), (2, 1, 2)), ((0, 0, 4.5), (1, 1, 1))]
    objs = []
    for (x, y, z), (sx, sy, sz) in parts:
        mesh = bpy.data.meshes.new("_GS_ScaleFigure")
        bpy_verts = [(x + dx * sx / 2, y + dy * sy / 2, z + dz * sz / 2)
                     for dx in (-1, 1) for dy in (-1, 1) for dz in (-1, 1)]
        faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
        mesh.from_pydata(bpy_verts, [], faces)
        mesh.materials.append(mat)
        obj = bpy.data.objects.new("_GS_ScaleFigure", mesh)
        obj.location = base
        coll.objects.link(obj)
        objs.append(obj)
    return objs


def _aim(cam, target, direction, distance):
    cam.location = target + direction.normalized() * distance
    up = "Y" if abs(direction.normalized().z) > 0.99 else "Z"
    if up == "Y":  # looking straight down: keep +Y up in the image
        cam.rotation_euler = (0.0, 0.0, 0.0)
    else:
        cam.rotation_euler = (-direction).to_track_quat("-Z", "Y").to_euler()


def review_sheet(paths, names=None, size=480, round_no=None, engine=None, scale_figure=True):
    """Render a 3x2 review sheet of the asset and return what to look at.

    Layout (left to right, top row first): see REVIEW_LAYOUT. Ortho views show true
    proportions; the 3/4 view has a 5-stud-tall figure beside the asset (a default avatar is
    about 5 studs) so the size in studs can be judged; the wireframe shows edge density.
    The working file is not changed. Engine: `engine`, else $GS_RENDER_ENGINE (written by
    `cloud_blender.sh probe`), else Workbench, falling back to EEVEE then Cycles CPU.
    """
    _require_bpy()
    import numpy as np

    scene = bpy.context.scene
    objs = [bpy.data.objects[n] for n in (names or asset_object_names(paths))
            if n in bpy.data.objects and bpy.data.objects[n].type == "MESH"]
    if not objs:
        raise SystemExit(f"nothing to review: no mesh objects in {paths['collection']}")

    if round_no is None:
        taken = [int(m.group(1)) for f in os.listdir(paths["renders"])
                 if (m := re.fullmatch(rf"{re.escape(paths['id'])}_review_(\d+)\.png", f))]
        round_no = max(taken, default=0) + 1
    out_png = os.path.join(paths["renders"], f"{paths['id']}_review_{round_no:02d}.png")

    t0 = time.time()
    order = [engine] if engine else []
    if os.environ.get("GS_RENDER_ENGINE"):
        order.append(os.environ["GS_RENDER_ENGINE"])
    order += ["BLENDER_WORKBENCH", "BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "CYCLES"]
    used = _set_engine(scene, order)

    # Everything temporary lives in one collection and is removed in `finally`.
    temp = bpy.data.collections.new("_GS_Review")
    scene.collection.children.link(temp)
    saved = {
        "camera": scene.camera, "res": (scene.render.resolution_x, scene.render.resolution_y,
                                        scene.render.resolution_percentage),
        "filepath": scene.render.filepath, "world": scene.world,
    }
    hidden = [o for o in scene.objects if o not in objs and not o.hide_render]
    tmpdir = tempfile.mkdtemp(prefix="gs-review-")
    wire_mods = []
    try:
        for o in hidden:
            o.hide_render = True
        scene.render.resolution_x = scene.render.resolution_y = size
        scene.render.resolution_percentage = 100
        scene.render.film_transparent = False
        scene.render.image_settings.file_format = "PNG"
        vs = scene.view_settings
        if _enum_has(vs, "view_transform", "Standard"):
            vs.view_transform = "Standard"  # true palette colours (AgX/Filmic desaturate)

        world = bpy.data.worlds.new("_GS_ReviewWorld")
        world.color = (0.62, 0.66, 0.70)
        scene.world = world
        if used == "CYCLES":
            scene.cycles.device = "CPU"
            scene.cycles.samples = 12
            if hasattr(scene.cycles, "use_denoising"):
                scene.cycles.use_denoising = True
            if world.node_tree is None:
                world.use_nodes = True
            bg = next((n for n in world.node_tree.nodes if n.type == "BACKGROUND"), None)
            if bg:
                bg.inputs[0].default_value = (0.62, 0.66, 0.70, 1.0)
                bg.inputs[1].default_value = 1.0
            sun_data = bpy.data.lights.new("_GS_Sun", "SUN")
            sun_data.energy = 3.0
            sun = bpy.data.objects.new("_GS_Sun", sun_data)
            sun.rotation_euler = (math.radians(50), math.radians(10), math.radians(35))
            temp.objects.link(sun)
        elif used == "BLENDER_WORKBENCH":
            sh = scene.display.shading
            sh.light = "STUDIO"
            sh.color_type = "MATERIAL"
            sh.show_object_outline = True
            sh.show_cavity = False
        else:  # EEVEE
            sun_data = bpy.data.lights.new("_GS_Sun", "SUN")
            sun_data.energy = 3.0
            sun = bpy.data.objects.new("_GS_Sun", sun_data)
            sun.rotation_euler = (math.radians(50), math.radians(10), math.radians(35))
            temp.objects.link(sun)

        lo, hi = _world_bounds(objs)
        center, dims = (lo + hi) / 2, hi - lo
        extent = max(max(dims), 0.5)

        figure = []
        if scale_figure:
            figure = _scale_figure(temp, Vector((hi.x + 1.0 + 1.0, center.y, lo.z)), dims.z)
            for o in figure:
                o.hide_render = True

        cam_data = bpy.data.cameras.new("_GS_Cam")
        cam = bpy.data.objects.new("_GS_Cam", cam_data)
        temp.objects.link(cam)
        scene.camera = cam
        cam_data.clip_end = extent * 100

        def shot(i, direction, ortho, show_figure=False, wire=False):
            for o in figure:
                o.hide_render = not show_figure
            vlo, vhi = lo, hi
            if show_figure and figure:
                flo, fhi = _world_bounds(figure)
                vlo, vhi = Vector(map(min, lo, flo)), Vector(map(max, hi, fhi))
            vc, vd = (vlo + vhi) / 2, vhi - vlo
            radius = max(vd.length / 2, 0.25)
            if ortho:
                cam_data.type = "ORTHO"
                d = direction.normalized()
                # visible width/height of the box seen along d
                if abs(d.z) > 0.99:
                    span = max(vd.x, vd.y)
                elif abs(d.x) > 0.99:
                    span = max(vd.y, vd.z)
                else:
                    span = max(vd.x, vd.z)
                cam_data.ortho_scale = max(span, 0.25) * 1.25
                _aim(cam, vc, direction, radius * 4 + 10)
            else:
                cam_data.type = "PERSP"
                cam_data.lens = 50
                fov = cam_data.angle
                _aim(cam, vc, direction, radius / math.sin(fov / 2) * 1.1)
            if wire:
                for o in objs:
                    m = o.modifiers.new("_GS_Wire", "WIREFRAME")
                    m.thickness = max(extent * 0.006, 0.01)
                    m.use_replace = True
                    m.use_even_offset = True
                    wire_mods.append((o, m))
                if used == "BLENDER_WORKBENCH":
                    scene.display.shading.color_type = "SINGLE"
                    scene.display.shading.single_color = (0.05, 0.05, 0.08)
            png = os.path.join(tmpdir, f"view{i}.png")
            scene.render.filepath = png
            bpy.ops.render.render(write_still=True)
            if wire:
                while wire_mods:
                    o, m = wire_mods.pop()
                    o.modifiers.remove(m)
                if used == "BLENDER_WORKBENCH":
                    scene.display.shading.color_type = "MATERIAL"
            return png

        views = [
            shot(0, Vector((0, -1, 0)), True),
            shot(1, Vector((1, 0, 0)), True),
            shot(2, Vector((0, 0, 1)), True),
            shot(3, Vector((1, -1, 0.75)), False, show_figure=True),
            shot(4, Vector((1, -1, 0.75)), False, wire=True),
            shot(5, Vector((-1, 1, 0.6)), False),
        ]

        # 3x2 grid with 6 px gutters, composed in numpy (Blender stores rows bottom-up).
        cols, rows, gap = 3, 2, 6
        width, height = cols * size + (cols + 1) * gap, rows * size + (rows + 1) * gap
        sheet = np.full((height, width, 4), (0.12, 0.12, 0.14, 1.0), dtype=np.float32)
        for i, png in enumerate(views):
            img = bpy.data.images.load(png, check_existing=False)
            px = np.empty(img.size[0] * img.size[1] * 4, dtype=np.float32)
            img.pixels.foreach_get(px)
            cell = px.reshape(img.size[1], img.size[0], 4)
            bpy.data.images.remove(img)
            r, c = divmod(i, cols)
            x0 = gap + c * (size + gap)
            y0 = height - (gap + r * (size + gap)) - size
            sheet[y0:y0 + size, x0:x0 + size] = cell[:size, :size]
        out = bpy.data.images.new("_GS_ReviewSheet", width, height, alpha=False)
        out.pixels.foreach_set(sheet.ravel())
        out.filepath_raw = out_png
        out.file_format = "PNG"
        out.save()
        bpy.data.images.remove(out)
    finally:
        for o, m in wire_mods:
            o.modifiers.remove(m)
        for o in hidden:
            o.hide_render = False
        scene.camera = saved["camera"]
        (scene.render.resolution_x, scene.render.resolution_y,
         scene.render.resolution_percentage) = saved["res"]
        scene.render.filepath = saved["filepath"]
        scene.world = saved["world"]
        for o in list(temp.all_objects):
            data = o.data
            bpy.data.objects.remove(o, do_unlink=True)
            if data is not None and data.users == 0:
                if isinstance(data, bpy.types.Mesh):
                    bpy.data.meshes.remove(data)
                elif isinstance(data, bpy.types.Camera):
                    bpy.data.cameras.remove(data)
                elif isinstance(data, bpy.types.Light):
                    bpy.data.lights.remove(data)
        bpy.data.collections.remove(temp)
        for w in [w for w in bpy.data.worlds if w.name.startswith("_GS_ReviewWorld") and w.users == 0]:
            bpy.data.worlds.remove(w)
        for m in [m for m in bpy.data.materials if m.name.startswith("_GS_ScaleFigure") and m.users == 0]:
            bpy.data.materials.remove(m)
        shutil.rmtree(tmpdir, ignore_errors=True)

    tris = {o.name: triangle_count(o) for o in objs}
    return {
        "png": out_png, "round": round_no, "engine": used, "seconds": round(time.time() - t0, 1),
        "layout": REVIEW_LAYOUT, "size_studs": [round(v, 2) for v in dims], "triangles": tris,
    }


def print_json(value):
    """Print a result as one JSON line (easy to read back from a shell)."""
    print("GS_RESULT " + json.dumps(value, default=str))
