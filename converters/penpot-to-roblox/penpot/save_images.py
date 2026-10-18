#!/usr/bin/env python3
"""Save the images returned by export_images.js and (optionally) upload them to Roblox.

    python3 save_images.py <export_result.json> <outdir> [--upload]

Writes <outdir>/<key>.png (or .jpg) for every image. With --upload, uploads each file once
through <plugin>/scripts/opencloud_upload.py --type Image (needs the Open Cloud secrets) and
writes <outdir>/images.json = {"<spec image key>": "rbxassetid://<id>"}, the map the Luau
builder takes. Uploads are cached by SHA-256 in <outdir>/uploads.json, so re-running never
uploads the same bytes twice. Python standard library only.
"""
import base64
import hashlib
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
UPLOADER = os.path.normpath(os.path.join(HERE, "..", "..", "..", "scripts", "opencloud_upload.py"))


def main(argv):
    if len(argv) < 3:
        sys.exit(__doc__)
    result_path, outdir, upload = argv[1], argv[2], "--upload" in argv[3:]
    with open(result_path, encoding="utf-8") as f:
        items = json.load(f)
    os.makedirs(outdir, exist_ok=True)
    cache_path = os.path.join(outdir, "uploads.json")
    cache = json.load(open(cache_path, encoding="utf-8")) if os.path.exists(cache_path) else {}
    images_path = os.path.join(outdir, "images.json")
    images = json.load(open(images_path, encoding="utf-8")) if os.path.exists(images_path) else {}
    for item in items:
        if "png" not in item:
            print(f"skip {item.get('key')}: {item.get('error', 'no data')}", file=sys.stderr)
            continue
        data = base64.b64decode(item["png"])
        ext = ".jpg" if data[:3] == b"\xff\xd8\xff" else ".png"
        path = os.path.join(outdir, re.sub(r"[^A-Za-z0-9_-]+", "_", item["key"]) + ext)
        with open(path, "wb") as f:
            f.write(data)
        digest = hashlib.sha256(data).hexdigest()
        print(f"saved {path} ({len(data)} bytes)")
        if not upload:
            continue
        if digest not in cache:
            name = re.sub(r"[^A-Za-z0-9 _-]+", " ", item.get("name") or item["key"]).strip()[:50] or "UI image"
            out = subprocess.run([sys.executable, UPLOADER, path, "--name", name, "--type", "Image"],
                                 capture_output=True, text=True)
            if out.returncode != 0:
                print(f"upload failed for {path}: {out.stderr.strip()}", file=sys.stderr)
                continue
            cache[digest] = "rbxassetid://" + json.loads(out.stdout.strip().splitlines()[-1])["assetId"]
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache, f, indent=1)
        images[item["key"]] = cache[digest]
        print(f"  {item['key']} -> {cache[digest]}")
    if upload:
        with open(images_path, "w", encoding="utf-8") as f:
            json.dump(images, f, indent=1)
        print(f"wrote {images_path}")


if __name__ == "__main__":
    main(sys.argv)
