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
MIN_COLOR = 0.70   # colour histogram intersection (used when no palette is given)
MIN_PALETTE = 0.75  # palette share agreement, 1 - L1/2 over the manifest's hue groups
MIN_KEEP = 0.35    # a colour group with >= 3 % of the render must keep >= 35 % of that share
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
    # Workbench shows a material's viewport colour (diffuse_color), not its node Base Color:
    # a .blend made without flat_material rendered all grey (seen on the lion). Paint each
    # part's material with the manifest hex for the render and put it back afterwards.
    saved_colours = []
    for p in manifest["parts"]:
        obj = bpy.data.objects[p["name"]]
        mat = obj.material_slots[0].material if obj.material_slots else None
        if mat is not None:
            saved_colours.append((mat, tuple(mat.diffuse_color)))
            h = p["hex"].lstrip("#")
            srgb = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
            lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in srgb]
            mat.diffuse_color = (lin[0], lin[1], lin[2], 1.0)
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
        for mat, colour in saved_colours:
            mat.diffuse_color = colour
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
    bh, bs, _ = colorsys.rgb_to_hsv(*[min(max(c, 0.0), 1.0) for c in bg])
    out = []
    for p in px:
        c = _chroma(p)
        dc = math.hypot(c[0] - cb[0], c[1] - cb[1])
        dl = abs((p[0] + p[1] + p[2]) / 3 - lb)
        fg = dc > 0.07 or dl > 0.30
        if fg and bs > 0.5:
            # Studio lights the backdrop unevenly (a sun highlight turns pure green into pale
            # green): same hue and still clearly saturated = backdrop. pick_backdrop keeps
            # part colours far from the backdrop hue.
            h, sat, _ = colorsys.rgb_to_hsv(*[min(max(x, 0.0), 1.0) for x in p[:3]])
            dh = min(abs(h - bh), 1 - abs(h - bh))
            if dh < 0.07 and sat > 0.2:
                fg = False
        out.append(fg)
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


def _hsv(c):
    return colorsys.rgb_to_hsv(min(max(c[0], 0.0), 1.0), min(max(c[1], 0.0), 1.0), min(max(c[2], 0.0), 1.0))


def _hue_dist(a, b):
    d = abs(a - b)
    return min(d, 1 - d)


def palette_groups(palette, merge=0.06):
    """Group the palette by hue (within ~22°), plus "light" / "dark" groups for greys.

    Measured live: Studio lights pastel parts much brighter than Workbench renders them (the
    lion's #F6C57F fur came out near #FFF0D0), so brightness and saturation can't tell
    #F6C57F, #FFE6BF and #FFD9A0 apart, but the hue survives. Returns
    [{"name", "hue" (or None), "colours": [hex]}]."""
    groups = []
    for hx in palette:
        h, sat, v = _hsv(_hex_rgb(hx))
        if sat < 0.15:
            name = "light" if v >= 0.5 else "dark"
            g = next((x for x in groups if x["name"] == name), None)
            if g is None:
                groups.append({"name": name, "hue": None, "colours": [hx]})
            else:
                g["colours"].append(hx)
            continue
        g = next((x for x in groups if x["hue"] is not None and _hue_dist(x["hue"], h) < merge), None)
        if g is None:
            groups.append({"name": hx, "hue": h, "colours": [hx]})
        else:
            g["colours"].append(hx)
            g["name"] = "+".join(g["colours"])
    return groups


def _group_shares(px, mask, groups):
    """Share of the model's pixels in each palette group (by hue; greys by brightness)."""
    hued = [i for i, g in enumerate(groups) if g["hue"] is not None]
    light = next((i for i, g in enumerate(groups) if g["name"] == "light"), None)
    dark = next((i for i, g in enumerate(groups) if g["name"] == "dark"), None)
    counts = [0] * len(groups)
    n = 0
    for p, m in zip(px, mask):
        if not m:
            continue
        h, sat, v = _hsv(p)
        n += 1
        best = None
        if hued and sat >= 0.08:
            best = hued[0]
            for i in hued[1:]:
                if _hue_dist(groups[i]["hue"], h) < _hue_dist(groups[best]["hue"], h):
                    best = i
            # A hue far from every palette hue is not one of them: Studio's Metal turns the
            # lamp's dark grey iron navy blue; count it by brightness instead.
            if _hue_dist(groups[best]["hue"], h) > 0.1 and (light is not None or dark is not None):
                best = None
        if best is None:
            if light is None and dark is None:
                continue
            best = light if (v >= 0.5 and light is not None) or dark is None else dark
        counts[best] += 1
    return [c / n for c in counts] if n else counts


def palette_from_manifest(manifest):
    """The distinct part colours of a manifest (for compare_images(palette=...))."""
    out = []
    for p in manifest["parts"]:
        if p["hex"].upper() not in out:
            out.append(p["hex"].upper())
    return out


def compare_images(render_png, capture_png, size=128, min_iou=MIN_IOU, min_color=MIN_COLOR, palette=None,
                   min_palette=MIN_PALETTE, min_keep=MIN_KEEP):
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
    pal = None
    if palette:
        # Measured live: the hue histogram passed a capture whose Neon-blue top was hidden
        # (0.735) and failed the correct capture (0.66, Neon renders cyan in Studio). Grouping
        # pixels by the manifest's own hues and requiring every visible group to survive
        # catches a missing or hidden part and tolerates lighting, Neon and pastels.
        groups = palette_groups(palette)
        names = [g["name"] for g in groups]
        sa = _group_shares(a, ma, groups)
        sb = _group_shares(b, mb, groups)
        agree = 1 - 0.5 * sum(abs(x - y) for x, y in zip(sa, sb))
        missing = [names[i] for i in range(len(groups)) if sa[i] >= 0.03 and sb[i] < min_keep * sa[i]]
        pal_ok = visible and agree >= min_palette and not missing
        pal = {"agreement": round(agree, 3), "missing": missing, "pass": pal_ok,
               "render": dict((names[i], round(sa[i], 3)) for i in range(len(groups))),
               "capture": dict((names[i], round(sb[i], 3)) for i in range(len(groups)))}
        col_ok = pal_ok
    return {
        "pass": sil_ok and col_ok,
        "palette": pal,
        "silhouette": {"iouNormalized": round(iou_n, 3), "iouRaw": round(_iou(ma, mb), 3),
                       "aspect": [round(aspect_a, 3), round(aspect_b, 3)], "pass": sil_ok},
        "color": {"intersection": round(colour, 3), "render": _top(ha), "capture": _top(hb), "pass": col_ok},
        "foreground": {"render": round(fa, 3), "capture": round(fb, 3)},
        "captureBackground": None if bg is None else "#%02X%02X%02X" % tuple(round(min(max(c, 0), 1) * 255) for c in bg),
        "thresholds": {"iouNormalized": min_iou, "color": min_color, "palette": min_palette, "keep": min_keep},
        "note": None if visible else "model not visible in one of the images",
    }
