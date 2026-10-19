#!/usr/bin/env python3
"""Roblox Open Cloud helper for grok-studio: check the API key, upload assets, poll uploads.

    python3 opencloud_upload.py introspect [--dry-run]
        Checks ROBLOX_OPEN_CLOUD_API_KEY: enabled, expiry, scopes, the owner's user id, and
        whether the key may upload for the place owner (from .bridge.json).
    python3 opencloud_upload.py upload <file> --name "Lava Rock" [--type Model]
                                [--description "..."] [--wait | --no-wait] [--timeout 600] [--dry-run]
        Uploads one file; with --wait (default) polls until processed and prints the assetId.
    python3 opencloud_upload.py status <operationId> [--wait] [--timeout 600]
        Polls an upload started with --no-wait.
    (`opencloud_upload.py <file> --name ...` without a subcommand still means upload.)

Every command prints one JSON line. Then insert a Model with the Studio MCP `insert_asset`
tool (Models arrive as packages).

Environment (Grok Bot: secrets exposed as environment variables on the cloud computer;
never put the key in a file under /workspace, a message, or a log):
    ROBLOX_OPEN_CLOUD_API_KEY   API key with the Assets API: Read + Write
    ROBLOX_CREATOR_USER_ID      or ROBLOX_CREATOR_GROUP_ID: who owns new assets (the game's
                                owner, or the game can't use them). Optional: without them the
                                place owner that /setup-bridge saved in .bridge.json
                                (place_creator_type / place_creator_id) is used, so no secret
                                has to be created by hand.

The key is sent only in the x-api-key header (or the introspect body, as Roblox documents)
and is never printed, also not in error messages. --dry-run shows the request with the key
redacted and sends nothing.

Docs (fetched Oct 2026):
  Assets:     https://create.roblox.com/docs/cloud/guides/usage-assets
              POST https://apis.roblox.com/assets/v1/assets (multipart: request + fileContent),
              GET  https://apis.roblox.com/assets/v1/operations/{operationId}
              Model: .fbx .gltf .glb .rbxm .rbxmx (as a package) - Animation: .rbxm .rbxmx only -
              Decal/Image: .png .jpeg .bmp .tga - Audio: .mp3 .ogg .wav .flac. Max 20 MB.
  Introspect: https://create.roblox.com/docs/cloud/auth/api-keys#introspect-api-keys
              POST https://apis.roblox.com/api-keys/v1/introspect  {"apiKey": "<key>"}
              -> name, authorizedUserId, scopes[{name, operations, userIds, groupIds, ...}],
                 enabled, expired, expirationTimeUtc
Python standard library only.
"""
import argparse
import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid

ASSETS_API = "https://apis.roblox.com/assets/v1"
INTROSPECT_URL = "https://apis.roblox.com/api-keys/v1/introspect"
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


BRIDGE_JSON = os.environ.get("GROK_STUDIO_BRIDGE_JSON", "/workspace/grok-studio/.bridge.json")


def place_owner():
    """The Studio place's owner as setup recorded it: ("Group"|"User", "<id>") or (None, None)."""
    try:
        with open(BRIDGE_JSON, encoding="utf-8-sig") as f:
            b = json.load(f)
    except (OSError, ValueError):
        return None, None
    kind, cid = str(b.get("place_creator_type") or ""), str(b.get("place_creator_id") or "")
    kind = "Group" if "group" in kind.lower() else "User" if "user" in kind.lower() else None
    return (kind, cid) if kind and cid.isdigit() else (None, None)


def resolve_creator():
    """(creator dict, source). Env secrets win, then the place owner from .bridge.json."""
    group_id = os.environ.get("ROBLOX_CREATOR_GROUP_ID", "").strip()
    user_id = os.environ.get("ROBLOX_CREATOR_USER_ID", "").strip()
    if group_id:
        return {"groupId": group_id}, "ROBLOX_CREATOR_GROUP_ID"
    if user_id:
        return {"userId": user_id}, "ROBLOX_CREATOR_USER_ID"
    kind, cid = place_owner()
    if kind == "Group":
        return {"groupId": cid}, "place owner (.bridge.json)"
    if kind == "User":
        return {"userId": cid}, "place owner (.bridge.json)"
    return None, None


def env_key():
    return os.environ.get("ROBLOX_OPEN_CLOUD_API_KEY", "").strip()


def redacted(key):
    return f"<{len(key)} chars, redacted>" if key else "<missing: set ROBLOX_OPEN_CLOUD_API_KEY>"


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


def call(method, url, key, body=None, content_type=None, header_key=True, retries=4):
    """HTTP call with retry on 429/5xx and network errors. Returns parsed JSON."""
    delay = 2.0
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=body, method=method)
        if header_key:
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
                400: " (bad request: check the file type and the request fields)",
                401: " (key invalid, disabled or expired: run `introspect`)",
                403: " (key lacks permission, its IP allowlist excludes this computer, or the creator id"
                     " doesn't match the key's owner: run `introspect`)",
            }.get(e.code, "")
            fail(f"{method} {url} -> HTTP {e.code}{hint}: {text}", 3, key)
        except urllib.error.URLError as e:
            if attempt < retries:
                time.sleep(delay)
                delay *= 2
                continue
            fail(f"{method} {url} -> {e.reason}", 3, key)
    fail("unreachable", 3, key)


# --------------------------------------------------------------------------- introspect

def _asset_access(scopes):
    access = {"read": False, "write": False, "userIds": [], "groupIds": []}
    for s in scopes or []:
        if not str(s.get("name", "")).lower().startswith("asset"):
            continue
        ops = {str(o).lower() for o in s.get("operations", [])}
        access["read"] = access["read"] or "read" in ops
        access["write"] = access["write"] or "write" in ops
        access["userIds"] += [str(u) for u in s.get("userIds", []) or []]
        access["groupIds"] += [str(g) for g in s.get("groupIds", []) or []]
    return access


def cmd_introspect(a):
    key = env_key()
    if a.dry_run:
        print(json.dumps({"dryRun": True, "method": "POST", "url": INTROSPECT_URL,
                          "headers": {"Content-Type": "application/json"},
                          "body": {"apiKey": redacted(key)}, "ready": bool(key)}, indent=2))
        return
    if not key:
        fail("ROBLOX_OPEN_CLOUD_API_KEY is not set", 2)
    info = call("POST", INTROSPECT_URL, key, json.dumps({"apiKey": key}).encode(),
                "application/json", header_key=False)
    assets = _asset_access(info.get("scopes"))
    problems = []
    if info.get("enabled") is False:
        problems.append("key is disabled (Creator Dashboard > Credentials: Enable Key)")
    if info.get("expired"):
        problems.append("key is expired (set a new expiration date or remove it)")
    days = None
    exp = info.get("expirationTimeUtc")
    if exp:
        try:
            when = datetime.datetime.fromisoformat(exp.replace("Z", "+00:00"))
            days = round((when - datetime.datetime.now(datetime.timezone.utc)).total_seconds() / 86400, 1)
            if 0 <= days < 7:
                problems.append(f"key expires in {days} days")
        except ValueError:
            pass
    if not assets["write"]:
        problems.append("no Assets API write permission (needed to upload)")
    if not assets["read"]:
        problems.append("no Assets API read permission (needed to poll uploads)")
    owner = info.get("authorizedUserId")
    creator, source = resolve_creator()
    kind, cid = place_owner()
    covers = None
    if creator:
        ids = assets["groupIds"] if "groupId" in creator else assets["userIds"]
        want = creator.get("groupId") or creator.get("userId")
        covers = "*" in ids or want in ids or ("userId" in creator and not ids and str(owner) == want)
        if not covers:
            problems.append(f"the key's Assets scope does not include {('group ' + want) if 'groupId' in creator else ('user ' + want)} "
                            "(Creator Dashboard > Credentials > the key > Assets API: add it)")
    print(json.dumps({
        "name": info.get("name"),
        "authorizedUserId": owner,
        "enabled": info.get("enabled"),
        "expired": info.get("expired"),
        "expirationTimeUtc": exp,
        "expiresInDays": days,
        "assets": assets,
        "scopes": [{"name": s.get("name"), "operations": s.get("operations")} for s in info.get("scopes", [])],
        "usable": not problems,
        "problems": problems,
        "placeOwner": {"type": kind, "id": cid} if kind else None,
        "uploadCreator": creator, "uploadCreatorSource": source,
        "note": ("Uploads go to the place owner recorded in .bridge.json; nothing to save."
                 if source and "place owner" in source else
                 "Uploads use the creator from the environment." if creator else
                 "No creator yet: /setup-bridge Step 3 records the place owner in .bridge.json. Keys unused "
                 "or unchanged for 60 days auto-expire."),
    }))
    if problems:
        sys.exit(5)


# --------------------------------------------------------------------------- upload / status

def poll(op_id, key, timeout):
    deadline = time.time() + timeout
    delay = 2.0
    while True:
        op = call("GET", f"{ASSETS_API}/operations/{op_id}", key)
        if op.get("done"):
            return op
        if time.time() > deadline:
            print(json.dumps({"operationId": op_id, "done": False,
                              "hint": f"still processing after {timeout}s; run: status {op_id} --wait"}))
            sys.exit(4)
        time.sleep(delay)
        delay = min(delay * 1.5, 15)


def finish(op, op_id, fallback_type, fallback_name, key):
    if "error" in op:
        fail(f"upload failed: {json.dumps(op['error'])[:500]}", 3, key)
    resp = op.get("response", {})
    asset_id = resp.get("assetId") or resp.get("path", "").split("/")[-1]
    print(json.dumps({
        "assetId": str(asset_id), "assetType": resp.get("assetType", fallback_type),
        "displayName": resp.get("displayName", fallback_name), "operationId": op_id,
        "moderation": (resp.get("moderationResult") or {}).get("moderationState"),
    }))


def cmd_upload(a):
    ext = os.path.splitext(a.file)[1].lower()
    if ext not in ALLOWED[a.type]:
        fail(f"{a.type} assets accept {sorted(ALLOWED[a.type])}, not {ext or 'no extension'}", 2)
    if not os.path.isfile(a.file):
        fail(f"file not found: {a.file}", 2)
    size = os.path.getsize(a.file)
    if size > MAX_BYTES:
        fail(f"{a.file} is {size} bytes; Open Cloud accepts at most {MAX_BYTES}", 2)

    creator, creator_source = resolve_creator()
    request = {
        "assetType": a.type,
        "displayName": a.name[:50],
        "description": a.description[:1000],
        "creationContext": {"creator": creator or {"userId": "<ROBLOX_CREATOR_USER_ID>"}},
    }
    key = env_key()
    if a.dry_run:
        print(json.dumps({
            "dryRun": True, "method": "POST", "url": f"{ASSETS_API}/assets",
            "headers": {"x-api-key": redacted(key)},
            "multipart": {"request": request,
                          "fileContent": {"filename": os.path.basename(a.file),
                                          "contentType": CONTENT_TYPES[ext], "bytes": size}},
            "then": f"GET {ASSETS_API}/operations/<operationId> until done" if a.wait else "print operationId",
            "creatorSource": creator_source,
            "ready": bool(key and creator),
        }, indent=2))
        return
    if not key:
        fail("ROBLOX_OPEN_CLOUD_API_KEY is not set (ask the Lead / the user for an Open Cloud key)", 2)
    if not creator:
        fail("no creator: run /setup-bridge Step 3 (it saves the place owner in .bridge.json), or set "
             "ROBLOX_CREATOR_GROUP_ID / ROBLOX_CREATOR_USER_ID to the game's owner", 2)

    with open(a.file, "rb") as f:
        data = f.read()
    body, ctype = multipart({"request": json.dumps(request)}, "fileContent",
                            os.path.basename(a.file), CONTENT_TYPES[ext], data)
    op = call("POST", f"{ASSETS_API}/assets", key, body, ctype)
    path = op.get("path", "")
    op_id = path.split("/")[-1] if path else op.get("operationId")
    if not op_id:
        fail(f"unexpected response (no operation path): {json.dumps(op)[:500]}", 3, key)
    if not a.wait and not op.get("done"):
        print(json.dumps({"operationId": op_id, "done": False, "next": f"status {op_id} --wait"}))
        return
    if not op.get("done"):
        op = poll(op_id, key, a.timeout)
    finish(op, op_id, a.type, a.name, key)


def cmd_status(a):
    key = env_key()
    if not key:
        fail("ROBLOX_OPEN_CLOUD_API_KEY is not set", 2)
    op = poll(a.operation_id, key, a.timeout) if a.wait else call("GET", f"{ASSETS_API}/operations/{a.operation_id}", key)
    if not op.get("done"):
        print(json.dumps({"operationId": a.operation_id, "done": False}))
        return
    finish(op, a.operation_id, None, None, key)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] not in {"introspect", "upload", "status", "-h", "--help"}:
        argv.insert(0, "upload")  # older form: opencloud_upload.py <file> --name ...
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("introspect", help="check the API key (scopes, expiry, owner user id)")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(fn=cmd_introspect)

    p = sub.add_parser("upload", help="upload one file as an asset")
    p.add_argument("file")
    p.add_argument("--name", required=True, help="display name (<= 50 chars)")
    p.add_argument("--type", default="Model", choices=sorted(ALLOWED))
    p.add_argument("--description", default="Made with grok-studio")
    w = p.add_mutually_exclusive_group()
    w.add_argument("--wait", dest="wait", action="store_true", default=True, help="poll until processed (default)")
    w.add_argument("--no-wait", dest="wait", action="store_false", help="print the operationId and return")
    p.add_argument("--timeout", type=int, default=600, help="seconds to wait for processing")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(fn=cmd_upload)

    p = sub.add_parser("status", help="poll an upload started with --no-wait")
    p.add_argument("operation_id")
    p.add_argument("--wait", action="store_true")
    p.add_argument("--timeout", type=int, default=600)
    p.set_defaults(fn=cmd_status)

    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
