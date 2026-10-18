#!/usr/bin/env python3
"""Upload one file to Roblox as an asset through the Open Cloud Assets API, wait for it, print the id.

    python3 opencloud_upload.py <file> --name "Lava Rock" [--type Model] [--description "..."]
                                [--timeout 600] [--dry-run]

Prints one JSON line: {"assetId": "123", "assetType": "Model", "displayName": ..., "operationId": ...}
Then insert it in Studio with the Studio MCP `insert_asset` tool (Models arrive as packages).

Environment (store the key as a Grok Bot secret, never in a file under /workspace):
    ROBLOX_OPEN_CLOUD_API_KEY   API key with the Assets API (read + write) permission
    ROBLOX_CREATOR_USER_ID      or ROBLOX_CREATOR_GROUP_ID: who owns the new asset
                                (the game's owner, so the game may use it)

The key is sent only in the x-api-key header and is never printed (also not in errors).
--dry-run prints the request it would send, without the key and without network access.

Docs: https://create.roblox.com/docs/cloud/guides/usage-assets
  Model: .fbx .gltf .glb .rbxm .rbxmx (uploads as a package) - Animation: .rbxm .rbxmx only -
  Decal/Image: .png .jpeg .bmp .tga - Audio: .mp3 .ogg .wav .flac. Max 20 MB per upload.
Python standard library only.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

API = "https://apis.roblox.com/assets/v1"
MAX_BYTES = 20 * 1024 * 1024

CONTENT_TYPES = {
    ".fbx": "model/fbx",
    ".gltf": "model/gltf+json",
    ".glb": "model/gltf-binary",
    ".rbxm": "model/x-rbxm",
    ".rbxmx": "model/x-rbxmx",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".bmp": "image/bmp",
    ".tga": "image/tga",
    ".mp3": "audio/mpeg",
    ".ogg": "audio/ogg",
    ".wav": "audio/wav",
    ".flac": "audio/flac",
}
ALLOWED = {
    "Model": {".fbx", ".gltf", ".glb", ".rbxm", ".rbxmx"},
    "Animation": {".rbxm", ".rbxmx"},
    "Decal": {".png", ".jpg", ".jpeg", ".bmp", ".tga"},
    "Image": {".png", ".jpg", ".jpeg", ".bmp", ".tga"},
    "Audio": {".mp3", ".ogg", ".wav", ".flac"},
}


def fail(msg, code=1, key=None):
    if key:
        msg = msg.replace(key, "<redacted>")
    print(f"[opencloud_upload] ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def multipart(fields, file_field, filename, content_type, data):
    boundary = f"----grokstudio{uuid.uuid4().hex}"
    out = bytearray()
    for name, value in fields.items():
        out += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"\r\n\r\n".encode()
        out += value.encode("utf-8") + b"\r\n"
    out += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{file_field}\"; "
            f"filename=\"{filename}\"\r\nContent-Type: {content_type}\r\n\r\n").encode()
    out += data + f"\r\n--{boundary}--\r\n".encode()
    return bytes(out), f"multipart/form-data; boundary={boundary}"


def call(method, url, key, body=None, content_type=None, retries=4):
    """HTTP call with retry on 429/5xx. Returns parsed JSON."""
    delay = 2.0
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=body, method=method)
        req.add_header("x-api-key", key)
        if content_type:
            req.add_header("Content-Type", content_type)
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.loads(resp.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as e:
            text = e.read().decode("utf-8", "replace")[:800]
            if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(delay)
                delay *= 2
                continue
            hint = {
                401: " (key invalid or expired)",
                403: " (key lacks the Assets API write permission, or the creator id does not match the key's owner)",
            }.get(e.code, "")
            fail(f"{method} {url} -> HTTP {e.code}{hint}: {text}", 3, key)
        except urllib.error.URLError as e:
            if attempt < retries:
                time.sleep(delay)
                delay *= 2
                continue
            fail(f"{method} {url} -> {e.reason}", 3, key)
    fail("unreachable", 3, key)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("file")
    ap.add_argument("--name", required=True, help="display name (<= 50 chars)")
    ap.add_argument("--type", default="Model", choices=sorted(ALLOWED))
    ap.add_argument("--description", default="Made with grok-studio")
    ap.add_argument("--timeout", type=int, default=600, help="seconds to wait for processing")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    ext = os.path.splitext(a.file)[1].lower()
    if ext not in ALLOWED[a.type]:
        fail(f"{a.type} assets accept {sorted(ALLOWED[a.type])}, not {ext or 'no extension'}", 2)
    if not os.path.isfile(a.file):
        fail(f"file not found: {a.file}", 2)
    size = os.path.getsize(a.file)
    if size > MAX_BYTES:
        fail(f"{a.file} is {size} bytes; Open Cloud accepts at most {MAX_BYTES}", 2)

    user_id = os.environ.get("ROBLOX_CREATOR_USER_ID", "").strip()
    group_id = os.environ.get("ROBLOX_CREATOR_GROUP_ID", "").strip()
    if group_id:
        creator = {"groupId": group_id}
    elif user_id:
        creator = {"userId": user_id}
    else:
        creator = None
    request = {
        "assetType": a.type,
        "displayName": a.name[:50],
        "description": a.description[:1000],
        "creationContext": {"creator": creator or {"userId": "<ROBLOX_CREATOR_USER_ID>"}},
    }
    key = os.environ.get("ROBLOX_OPEN_CLOUD_API_KEY", "").strip()

    if a.dry_run:
        print(json.dumps({
            "dryRun": True,
            "method": "POST",
            "url": f"{API}/assets",
            "headers": {"x-api-key": f"<{len(key)} chars, redacted>" if key else "<missing: set ROBLOX_OPEN_CLOUD_API_KEY>"},
            "multipart": {
                "request": request,
                "fileContent": {"filename": os.path.basename(a.file), "contentType": CONTENT_TYPES[ext], "bytes": size},
            },
            "then": f"GET {API}/operations/<operationId> until done",
            "ready": bool(key and creator),
        }, indent=2))
        return

    if not key:
        fail("ROBLOX_OPEN_CLOUD_API_KEY is not set (ask the Lead / the user for an Open Cloud key)", 2)
    if not creator:
        fail("set ROBLOX_CREATOR_USER_ID or ROBLOX_CREATOR_GROUP_ID (the game's owner)", 2)

    with open(a.file, "rb") as f:
        data = f.read()
    body, ctype = multipart({"request": json.dumps(request)}, "fileContent",
                            os.path.basename(a.file), CONTENT_TYPES[ext], data)
    op = call("POST", f"{API}/assets", key, body, ctype)
    path = op.get("path", "")
    op_id = path.split("/")[-1] if path else op.get("operationId")
    if not op_id:
        fail(f"unexpected response (no operation path): {json.dumps(op)[:500]}", 3, key)

    deadline = time.time() + a.timeout
    delay = 2.0
    while not op.get("done"):
        if time.time() > deadline:
            fail(f"operation {op_id} still processing after {a.timeout}s; poll {API}/operations/{op_id} later", 4, key)
        time.sleep(delay)
        delay = min(delay * 1.5, 15)
        op = call("GET", f"{API}/operations/{op_id}", key)

    if "error" in op:
        fail(f"upload failed: {json.dumps(op['error'])[:500]}", 3, key)
    resp = op.get("response", {})
    asset_id = resp.get("assetId") or resp.get("path", "").split("/")[-1]
    moderation = (resp.get("moderationResult") or {}).get("moderationState")
    print(json.dumps({
        "assetId": str(asset_id), "assetType": resp.get("assetType", a.type),
        "displayName": resp.get("displayName", a.name), "operationId": op_id,
        "moderation": moderation,
    }))


if __name__ == "__main__":
    main()
