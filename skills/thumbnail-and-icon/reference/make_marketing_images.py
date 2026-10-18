#!/usr/bin/env python3
"""
make_marketing_images.py - turn raw captures/renders into Roblox-ready icon and thumbnails.

  icon:      512x512 square PNG            (https://create.roblox.com/docs/production/publishing/experience-icons)
  thumbnail: 1920x1080 16:9, < 3 MB         (https://create.roblox.com/docs/production/publishing/thumbnails)

Usage:
  uv run --with pillow python make_marketing_images.py icon  in.png  out/icon-512.png [--title "Lava Leap"]
  uv run --with pillow python make_marketing_images.py thumb in.png  out/thumb-1.png  [--title "Lava Leap"]

Center-crops to the target aspect (use --focus x,y in 0..1 to move the crop center), resizes
with Lanczos, optional title text with outline, then checks size limits.
"""
import argparse
import os
import sys

from PIL import Image, ImageDraw, ImageFont, ImageEnhance

SPECS = {
    "icon": (512, 512),
    "thumb": (1920, 1080),
}
MAX_THUMB_BYTES = 3 * 1024 * 1024


def crop_to_aspect(img, target_w, target_h, focus=(0.5, 0.5)):
    src_w, src_h = img.size
    target_ratio = target_w / target_h
    if src_w / src_h > target_ratio:  # too wide -> crop width
        new_w, new_h = int(src_h * target_ratio), src_h
    else:  # too tall -> crop height
        new_w, new_h = src_w, int(src_w / target_ratio)
    cx, cy = focus[0] * src_w, focus[1] * src_h
    left = min(max(0, int(cx - new_w / 2)), src_w - new_w)
    top = min(max(0, int(cy - new_h / 2)), src_h - new_h)
    return img.crop((left, top, left + new_w, top + new_h))


def load_font(size):
    for name in ("DejaVuSans-Bold.ttf", "Arial Bold.ttf", "arialbd.ttf", "Helvetica.ttc"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_title(img, text, kind):
    draw = ImageDraw.Draw(img)
    w, h = img.size
    size = int(h * (0.12 if kind == "thumb" else 0.16))
    font = load_font(size)
    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=max(2, size // 12))
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (w - tw) // 2
    y = int(h * 0.06) if kind == "thumb" else h - th - int(h * 0.08)
    draw.text((x, y), text, font=font, fill="white", stroke_width=max(2, size // 12), stroke_fill="black")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=SPECS.keys())
    ap.add_argument("src")
    ap.add_argument("dst")
    ap.add_argument("--title", default=None, help="Short title overlay (keep icons text-free if possible)")
    ap.add_argument("--focus", default="0.5,0.5")
    ap.add_argument("--punch", type=float, default=1.08, help="Saturation/contrast boost (1.0 = none)")
    args = ap.parse_args()

    tw, th = SPECS[args.kind]
    fx, fy = (float(v) for v in args.focus.split(","))
    img = Image.open(args.src).convert("RGB")
    if img.width < tw or img.height < th:
        print(f"warning: source {img.size} is smaller than {tw}x{th}; output will be upscaled (blurry). "
              "Re-render/capture at a higher resolution if possible.", file=sys.stderr)
    img = crop_to_aspect(img, tw, th, (fx, fy)).resize((tw, th), Image.LANCZOS)
    if args.punch != 1.0:
        img = ImageEnhance.Color(img).enhance(args.punch)
        img = ImageEnhance.Contrast(img).enhance(1 + (args.punch - 1) / 2)
    if args.title:
        draw_title(img, args.title, args.kind)

    os.makedirs(os.path.dirname(os.path.abspath(args.dst)), exist_ok=True)
    img.save(args.dst, "PNG", optimize=True)
    size = os.path.getsize(args.dst)
    if args.kind == "thumb" and size > MAX_THUMB_BYTES:
        jpg = os.path.splitext(args.dst)[0] + ".jpg"
        img.save(jpg, "JPEG", quality=90, optimize=True)
        print(f"PNG was {size} bytes (> 3 MB); wrote {jpg} ({os.path.getsize(jpg)} bytes) instead")
    else:
        print(f"wrote {args.dst} {img.size} {size} bytes")


if __name__ == "__main__":
    main()
