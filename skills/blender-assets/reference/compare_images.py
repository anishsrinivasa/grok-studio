"""
compare_images.py - does the model in Studio look like the Blender model?

Same rules as gs_core.py: runs headless in the cloud or pasted into the Blender MCP
`execute_blender_code` tool (safe mode included), so it imports only bpy, mathutils, math,
json and colorsys. In MCP mode send this whole file plus one
`print("GS_RESULT " + json.dumps(...))` call and read that line.

  1. render_compare(manifest, view, out_png) - in Blender: the asset alone, transparent
     background, camera derived from the manifest bounds. Returns the matching Studio camera
     (offsets from the model pivot in Roblox axes, field of view) and a backdrop colour that
     is far from every part colour.
  2. capture_booth.luau - in Studio: clones the model into a booth in front of that backdrop
     and returns camera_position / look_at_position for screen_capture. Save the capture as
     a PNG/JPG file.
  3. compare_images(render_png, capture_png) - silhouette overlap and colour histogram scores
     with a pass/fail. Look at both images as well: the scores catch wrong shapes, missing
     parts and wrong colours, not every detail.

Field of view: Roblox's Camera.FieldOfView is vertical (default 70). Both images are cut to
the centred square before comparing, so the Studio window's aspect ratio doesn't matter.
"""
import colorsys
import json
import math

import bpy
from mathutils import Vector

# Camera direction from the target, Roblox axes. Roblox -Z = Blender -Y = the side Blender's
# Front view sees (gs_core.roblox_vec: Roblox (x, y, z) = Blender (-x, z, y)).
VIEWS = {"front": (0.0, 0.0, -1.0), "three_quarter": (-1.0, 0.75, -1.0)}
BACKDROPS = ["#FF00FF", "#00FFFF", "#00FF00", "#FFFF00", "#0000FF", "#FF0000"]
MIN_IOU = 0.80     # silhouette overlap after normalising position and scale
MIN_COLOR = 0.70   # colour histogram intersection
HUE_NAMES = ["red", "orange", "yellow", "lime", "green", "spring", "cyan", "azure",
             "blue", "violet", "magenta", "rose", "dark", "grey", "light"]


def _blender_vec(r):
    """Roblox (x, y, z) -> Blender; same mapping as gs_core.blender_vec."""
    return Vector((-r[0], r[2], r[1]))


def _hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def compare_camera(manifest, view="front", fov=70.0, margin=1.15):
    """Camera for both sides, relative to the model pivot (bottom centre), Roblox axes, studs."""
    if view not in VIEWS:
        raise ValueError("view must be one of %s" % sorted(VIEWS))
    sx, sy, sz = manifest["size"]
    target = Vector((0.0, sy / 2, 0.0))
    radius = max(0.5 * math.sqrt(sx * sx + sy * sy + sz * sz), 0.25)
    direction = Vector(VIEWS[view]).normalized()
    dist = radius / math.sin(math.radians(fov) / 2) * margin
    pos = target + direction * dist
    return {
        "view": view, "fieldOfView": fov, "distance": round(dist, 4),
        "position": [round(c, 4) for c in pos], "lookAt": [round(c, 4) for c in target],
    }


def pick_backdrop(manifest):
    """The candidate colour farthest from every part colour (for chroma keying the capture)."""
    colours = [_hex_rgb(p["hex"]) for p in manifest["parts"]] or [(0.5, 0.5, 0.5)]
    best, best_d = BACKDROPS[0], -1.0
    for cand in BACKDROPS:
        c = _hex_rgb(cand)
        d = min(math.dist(c, p) for p in colours)
        if d > best_d:
            best, best_d = cand, d
    return best


def _set_engine(scene, wanted):
    for engine in wanted:
        try:
            scene.render.engine = engine
            return scene.render.engine
        except TypeError:
            continue
    raise ValueError("none of the render engines %s exist" % (wanted,))


def render_compare(manifest, view="front", out_png="//compare.png", size=256, fov=70.0, engine=None):
    """Render the manifest's parts alone (transparent background) as Studio will see them.

    Returns {"png", "engine", "studio": {view, fieldOfView, distance, position, lookAt},
    "backdrop"}. Give "studio" and "backdrop" to capture_booth.luau.
    """
    scene = bpy.context.scene
    names = [p["name"] for p in manifest["parts"]]
    missing = [n for n in names if n not in bpy.data.objects]
    if missing:
        raise ValueError("render_compare: objects not in this .blend: %s" % missing)
    cam_spec = compare_camera(manifest, view, fov)
    pivot = Vector(manifest["pivot"]["blender"])
    loc = pivot + _blender_vec(cam_spec["position"])
    target = pivot + _blender_vec(cam_spec["lookAt"])

    prev = {
        "camera": scene.camera, "engine": scene.render.engine, "filepath": scene.render.filepath,
        "res": (scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage),
        "transparent": scene.render.film_transparent, "view_transform": scene.view_settings.view_transform,
        "format": scene.render.image_settings.file_format, "color_mode": scene.render.image_settings.color_mode,
        "light": scene.display.shading.light, "color_type": scene.display.shading.color_type,
        "outline": scene.display.shading.show_object_outline,
    }
    hidden = [o for o in scene.objects if o.name not in names and not o.hide_render]
    temp = []
    try:
        used = _set_engine(scene, ([engine] if engine else []) + ["BLENDER_WORKBENCH", "BLENDER_EEVEE", "BLENDER_EEVEE_NEXT", "CYCLES"])
        for o in hidden:
            o.hide_render = True
        try:
            scene.view_settings.view_transform = "Standard"
        except TypeError:
            pass
        if used == "BLENDER_WORKBENCH":
            scene.display.shading.light = "STUDIO"
            scene.display.shading.color_type = "MATERIAL"
            scene.display.shading.show_object_outline = False
        else:
            sun_data = bpy.data.lights.new("_gs_cmp_sun", "SUN")
            sun_data.energy = 3.0
            sun = bpy.data.objects.new("_gs_cmp_sun", sun_data)
            sun.rotation_euler = (math.radians(50), math.radians(10), math.radians(35))
            scene.collection.objects.link(sun)
            temp.append(sun)
            if used == "CYCLES":
                scene.cycles.device = "CPU"
                scene.cycles.samples = 16
        cam_data = bpy.data.cameras.new("_gs_cmp_cam")
        cam_data.sensor_fit = "VERTICAL"
        cam_data.angle_y = math.radians(fov)
        cam_data.clip_end = max(1000.0, cam_spec["distance"] * 10)
        cam = bpy.data.objects.new("_gs_cmp_cam", cam_data)
        cam.location = loc
        cam.rotation_euler = (target - loc).to_track_quat("-Z", "Y").to_euler()
        scene.collection.objects.link(cam)
        temp.append(cam)
        scene.camera = cam
        scene.render.resolution_x = scene.render.resolution_y = size
        scene.render.resolution_percentage = 100
        scene.render.film_transparent = True
        scene.render.image_settings.file_format = "PNG"
        scene.render.image_settings.color_mode = "RGBA"
        scene.render.filepath = out_png
        bpy.ops.render.render(write_still=True)
    finally:
        for o in hidden:
            o.hide_render = False
        for o in temp:
            data = o.data
            bpy.data.objects.remove(o, do_unlink=True)
            if isinstance(data, bpy.types.Camera):
                bpy.data.cameras.remove(data)
            elif isinstance(data, bpy.types.Light):
                bpy.data.lights.remove(data)
        scene.camera = prev["camera"]
        try:
            scene.render.engine = prev["engine"]
        except TypeError:
            pass
        scene.render.filepath = prev["filepath"]
        scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = prev["res"]
        scene.render.film_transparent = prev["transparent"]
        scene.view_settings.view_transform = prev["view_transform"]
        scene.render.image_settings.file_format = prev["format"]
        scene.render.image_settings.color_mode = prev["color_mode"]
        scene.display.shading.light = prev["light"]
        scene.display.shading.color_type = prev["color_type"]
        scene.display.shading.show_object_outline = prev["outline"]
    return {"png": out_png, "engine": used, "studio": cam_spec, "backdrop": pick_backdrop(manifest)}


# --------------------------------------------------------------------------- comparison

def _load_square(path, size):
    """Centre square of an image, scaled to size x size: list of (r, g, b, a), bottom row first."""
    img = bpy.data.images.load(path, check_existing=False)
    try:
        w, h = img.size[0], img.size[1]
        if w == 0 or h == 0:
            raise ValueError("could not read image %s" % path)
        if w >= h:
            nw, nh = max(size, int(round(w * size / h))), size
        else:
            nw, nh = size, max(size, int(round(h * size / w)))
        img.scale(nw, nh)
        ch = img.channels
        px = img.pixels[:]
    finally:
        bpy.data.images.remove(img)
    x0, y0 = (nw - size) // 2, (nh - size) // 2
    out = []
    for y in range(y0, y0 + size):
        base = y * nw
        for x in range(x0, x0 + size):
            i = (base + x) * ch
            out.append((px[i], px[i + 1], px[i + 2], px[i + 3] if ch == 4 else 1.0))
    return out


def _median(values):
    s = sorted(values)
    return s[len(s) // 2]


def _border_colour(px, size):
    idx = [i for i in range(size)] + [(size - 1) * size + i for i in range(size)]
    idx += [r * size for r in range(size)] + [r * size + size - 1 for r in range(size)]
    return tuple(_median([px[i][c] for i in idx]) for c in range(3))


def _chroma(c):
    s = c[0] + c[1] + c[2] + 1e-6
    return c[0] / s, c[1] / s


def _mask(px, size):
    """Foreground mask: alpha if the image has transparency, else chroma-key on the border colour."""
    if any(p[3] < 0.5 for p in px):
        return [p[3] >= 0.5 for p in px], None
    bg = _border_colour(px, size)
    cb = _chroma(bg)
    lb = (bg[0] + bg[1] + bg[2]) / 3
    out = []
    for p in px:
        c = _chroma(p)
        dc = math.hypot(c[0] - cb[0], c[1] - cb[1])
        dl = abs((p[0] + p[1] + p[2]) / 3 - lb)
        out.append(dc > 0.07 or dl > 0.30)
    return out, bg


def _bbox(mask, size):
    xs = [i % size for i, m in enumerate(mask) if m]
    ys = [i // size for i, m in enumerate(mask) if m]
    if not xs:
        return None
    return min(xs), min(ys), max(xs), max(ys)


def _normalised(mask, size, n=48):
    """The mask's bounding box resampled to n x n (position- and scale-free shape)."""
    bb = _bbox(mask, size)
    if bb is None:
        return [False] * (n * n), 0.0
    x0, y0, x1, y1 = bb
    bw, bh = x1 - x0 + 1, y1 - y0 + 1
    side = max(bw, bh)  # keep the aspect ratio: pad the short side
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    out = []
    for v in range(n):
        for u in range(n):
            x = int(round(cx - side / 2 + (u + 0.5) * side / n))
            y = int(round(cy - side / 2 + (v + 0.5) * side / n))
            out.append(0 <= x < size and 0 <= y < size and mask[y * size + x])
    return out, bw / bh


def _iou(a, b):
    inter = sum(1 for x, y in zip(a, b) if x and y)
    union = sum(1 for x, y in zip(a, b) if x or y)
    return inter / union if union else 0.0


def _histogram(px, mask):
    """12 soft hue bins for coloured pixels + dark / grey / light bins for unsaturated ones."""
    bins = [0.0] * 15
    n = 0
    for p, m in zip(px, mask):
        if not m:
            continue
        h, s, v = colorsys.rgb_to_hsv(min(max(p[0], 0.0), 1.0), min(max(p[1], 0.0), 1.0), min(max(p[2], 0.0), 1.0))
        n += 1
        if s < 0.25 or v < 0.12:
            bins[12 + min(2, int(v * 3))] += 1
        else:
            pos = h * 12 - 0.5
            k0 = math.floor(pos)
            frac = pos - k0
            bins[k0 % 12] += 1 - frac
            bins[(k0 + 1) % 12] += frac
    return ([b / n for b in bins] if n else bins), n


def _top(hist, k=3):
    order = sorted(((-v, i) for i, v in enumerate(hist)))[:k]  # no lambdas: safe mode rejects them
    return [[HUE_NAMES[i], round(-nv, 3)] for nv, i in order if -nv > 0.01]


def compare_images(render_png, capture_png, size=128, min_iou=MIN_IOU, min_color=MIN_COLOR):
    """Score a Blender render against a Studio capture of the same view.

    Silhouette: IoU after normalising position and scale (the Studio framing never matches to
    the pixel), plus the raw IoU for information. Colour: histogram intersection over the
    model's pixels (hue for coloured pixels, brightness for greys), robust to Studio's
    different lighting. pass = both scores above their thresholds and the model visible.
    """
    a = _load_square(render_png, size)
    b = _load_square(capture_png, size)
    ma, _ = _mask(a, size)
    mb, bg = _mask(b, size)
    fa = sum(ma) / len(ma)
    fb = sum(mb) / len(mb)
    na, aspect_a = _normalised(ma, size)
    nb, aspect_b = _normalised(mb, size)
    iou_n = _iou(na, nb)
    ha, _ = _histogram(a, ma)
    hb, _ = _histogram(b, mb)
    colour = sum(min(x, y) for x, y in zip(ha, hb))
    visible = fa > 0.005 and fb > 0.005
    sil_ok = visible and iou_n >= min_iou
    col_ok = visible and colour >= min_color
    return {
        "pass": sil_ok and col_ok,
        "silhouette": {"iouNormalized": round(iou_n, 3), "iouRaw": round(_iou(ma, mb), 3),
                       "aspect": [round(aspect_a, 3), round(aspect_b, 3)], "pass": sil_ok},
        "color": {"intersection": round(colour, 3), "render": _top(ha), "capture": _top(hb), "pass": col_ok},
        "foreground": {"render": round(fa, 3), "capture": round(fb, 3)},
        "captureBackground": None if bg is None else "#%02X%02X%02X" % tuple(round(min(max(c, 0), 1) * 255) for c in bg),
        "thresholds": {"iouNormalized": min_iou, "color": min_color},
        "note": None if visible else "model not visible in one of the images",
    }
