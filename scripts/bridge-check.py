#!/usr/bin/env python3
"""bridge-check.py - is the user's Studio bridge reachable from here? (cloud side, cheap)

Runs on the agent's machine (e.g. the Grok Bot cloud computer), Python 3.8+ stdlib only. No
command runs on the user's PC, so no approval is needed: every Bot can run this at the start
of a task.

Usage:
  python3 bridge-check.py [--studio] [--wait SECONDS] [--bridge-json PATH]

  default   GET <bridge>/healthz (gateway + tunnel up?)                       ~0.2-1 s
  --studio  also open an MCP session and call list_roblox_studios (read-only)  ~1-2 s
  --wait N  keep checking every 2 s until it passes or N seconds are up (use right after
            a restart of the bridge on the PC)

Transient failures (DNS, connection reset, HTTP 502/503/504/530, "fetch failed") are retried
with backoff (1 s, 3 s, 8 s) before reporting "down".

Prints one JSON object, e.g.
  {"bridge": "up", "studio": "ok", "places": ["My Place (placeId: 123)"], "ms": 640}
  {"bridge": "down", "error": "HTTP 530 ...", "fix": "..."}
Exit code: 0 = up (and Studio answered, with --studio), 1 = down or Studio failed,
2 = no bridge session file (the bridge was never connected from here).

Reads /workspace/grok-studio/.bridge.json (written by connect-studio): JSON, or the bridge's
KEY=... / STUDIO_URL=... lines. Never prints the key.

If the Grok Bot secret GROK_STUDIO_BRIDGE_KEY is set and the file's key is rejected (401),
the secret is tried too; when it works, .bridge.json is updated with it (mode 600) and the
result says "healed". So a stale session file heals itself without a PC command.
"""
import os
import argparse
import json
import sys
import time
import urllib.error
import urllib.request

DEFAULT_BRIDGE_JSON = "/workspace/grok-studio/.bridge.json"
LINE_KEYS = {"KEY": "api_key", "STUDIO_URL": "studio_url", "FILES_URL": "files_url", "BLENDER_URL": "blender_url",
             "PC_DROP_DIR": "pc_drop_dir", "PC_HTTP_BASE": "pc_http_base", "TUNNEL": "tunnel", "PC_OS": "pc_os"}
TRANSIENT_HTTP = {502, 503, 504, 520, 521, 522, 523, 524, 530}
BACKOFF = (1, 3, 8)
RETRY = True   # --wait polls instead


def load_bridge(path):
    with open(path, encoding="utf-8-sig") as f:
        text = f.read()
    if text.lstrip().startswith("{"):
        return json.loads(text)
    out = {}
    for line in text.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            k = k.strip()
            if k in LINE_KEYS:
                out[LINE_KEYS[k]] = v.strip()
    return out


class Transient(Exception):
    pass


def request(url, key=None, body=None, session=None, timeout=15, parse=True):
    headers = {"User-Agent": "grok-studio-bridge-check/0.2", "ngrok-skip-browser-warning": "1"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    if body is not None:
        headers["Content-Type"] = "application/json"
        headers["Accept"] = "application/json, text/event-stream"
    if session:
        headers["Mcp-Session-Id"] = session
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        snippet = e.read(300).decode("utf-8", "replace").strip()
        if e.code in TRANSIENT_HTTP:
            raise Transient(f"HTTP {e.code} {snippet[:160]}")
        raise RuntimeError(f"HTTP {e.code} {snippet[:160]}")
    except (urllib.error.URLError, ConnectionError, TimeoutError, OSError) as e:
        raise Transient(f"fetch failed: {getattr(e, 'reason', e)}")
    with resp:
        sid = resp.headers.get("Mcp-Session-Id")
        ctype = resp.headers.get("Content-Type", "")
        raw = resp.read().decode("utf-8", "replace")
    if not parse:
        return sid, []
    if "text/event-stream" in ctype:
        msgs = []
        for block in raw.replace("\r\n", "\n").split("\n\n"):
            data_lines = [l[5:].lstrip() for l in block.split("\n") if l.startswith("data:")]
            if data_lines:
                msgs.append(json.loads("\n".join(data_lines)))
        return sid, msgs
    return sid, ([json.loads(raw)] if raw.strip() else [])


def with_retry(fn):
    last = None
    for delay in (0,) + (BACKOFF if RETRY else ()):
        if delay:
            time.sleep(delay)
        try:
            return fn()
        except Transient as e:
            last = e
    raise last


def env_bridge_key():
    return os.environ.get("GROK_STUDIO_BRIDGE_KEY", "").strip()


def save_key(path, key):
    """Write the working key into the session file (JSON only), keeping mode 600."""
    try:
        with open(path, encoding="utf-8-sig") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return False
    data["api_key"] = key
    tmp = path + ".tmp"
    old = os.umask(0o077)
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    finally:
        os.umask(old)
    return True


def fix_for(err):
    e = str(err)
    if "401" in e:
        return ("The bridge rejected the key: its key was rotated or .bridge.json is stale. Run connect-studio "
                "(it re-reads the session and updates the connector). If you know the current key, save it as the "
                "secret GROK_STUDIO_BRIDGE_KEY and re-run: bridge-check then fixes .bridge.json by itself.")
    if "530" in e or "1033" in e or "ERR_NGROK_3200" in e or "404" in e and "ngrok" in e:
        return "The tunnel is down (the PC is asleep/offline, or the bridge stopped). Run connect-studio: it checks status on the PC and restarts the bridge."
    if "fetch failed" in e or "Name or service" in e or "getaddrinfo" in e:
        return "The bridge URL doesn't answer (PC offline/asleep, or a Cloudflare URL that changed). Run connect-studio."
    return "Run connect-studio to check and repair the bridge."


def main():
    global RETRY
    ap = argparse.ArgumentParser(description="Check the grok-studio bridge from the cloud side.")
    ap.add_argument("--studio", action="store_true", help="also call list_roblox_studios (read-only)")
    ap.add_argument("--wait", type=float, default=0, help="poll until it passes or this many seconds pass")
    ap.add_argument("--bridge-json", default=DEFAULT_BRIDGE_JSON)
    args = ap.parse_args()
    if args.wait <= 0:
        return check(args, time.time())
    RETRY = False
    t0, deadline = time.time(), time.time() + args.wait
    while True:
        code, line = check(args, t0, quiet=True)
        if code == 0 or code == 2 or time.time() + 2 > deadline:
            print(line)
            return code
        time.sleep(2)


def check(args, t0, quiet=False):
    """Returns the exit code; prints (or, quiet, returns (code, line)) one JSON line."""
    def done(code, obj):
        line = json.dumps(obj)
        if quiet:
            return code, line
        print(line)
        return code

    try:
        b = load_bridge(args.bridge_json)
    except FileNotFoundError:
        return done(2, {"bridge": "unknown", "error": f"{args.bridge_json} not found", "fix": "Studio was never connected from here: run connect-studio."})
    except (OSError, ValueError) as e:
        return done(2, {"bridge": "unknown", "error": f"cannot read {args.bridge_json}: {e}", "fix": "Run connect-studio."})
    url, key = b.get("studio_url") or b.get("files_url"), b.get("api_key") or env_bridge_key()
    if not url or not key:
        return done(2, {"bridge": "unknown", "error": "no studio_url/api_key in the session file", "fix": "Run connect-studio."})
    base = url.rsplit("/", 2)[0]   # https://host/roblox-studio/mcp -> https://host
    out = {"url": base}
    try:
        with_retry(lambda: request(base + "/healthz", timeout=10, parse=False))
        out["bridge"] = "up"
    except Exception as e:
        out.update(bridge="down", error=str(e), fix=fix_for(e), ms=int((time.time() - t0) * 1000))
        return done(1, out)
    if args.studio:
        studio_url = b.get("studio_url")
        keys = [key]
        if env_bridge_key() and env_bridge_key() != key:
            keys.append(env_bridge_key())
        for i, k in enumerate(keys):
            try:
                res = list_places(studio_url, k)
                out.pop("error", None)
                out.pop("fix", None)
                out.update(res)
                if i > 0:
                    healed = save_key(args.bridge_json, k)
                    out["healed"] = ("api_key in .bridge.json replaced by GROK_STUDIO_BRIDGE_KEY" if healed
                                     else "GROK_STUDIO_BRIDGE_KEY works but .bridge.json could not be updated")
                break
            except Exception as e:
                out.update(studio="error", error=str(e), fix=fix_for(e))
                if "401" not in str(e):
                    break
    out["ms"] = int((time.time() - t0) * 1000)
    return done(0 if out.get("studio", "ok") == "ok" else 1, out)


def list_places(studio_url, key):
    """Open an MCP session, call list_roblox_studios (read-only), close it."""
    if not studio_url:
        raise RuntimeError("the bridge was started without Studio (--no-studio)")
    sid, msgs = with_retry(lambda: request(studio_url, key, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
        "protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "grok-studio-bridge-check", "version": "0.2"}}}))
    try:
        request(studio_url, key, {"jsonrpc": "2.0", "method": "notifications/initialized"}, sid)
        _, msgs = request(studio_url, key, {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                                           "params": {"name": "list_roblox_studios", "arguments": {}}}, sid, timeout=30)
    finally:
        try:  # end the session so its Studio MCP process exits
            req = urllib.request.Request(studio_url, headers={"Authorization": f"Bearer {key}", "Mcp-Session-Id": sid or ""}, method="DELETE")
            urllib.request.urlopen(req, timeout=5).close()
        except Exception:
            pass
    res = next((m for m in msgs if m.get("id") == 2), {})
    if "error" in res:
        raise RuntimeError(res["error"].get("message"))
    text = "".join(c.get("text", "") for c in res.get("result", {}).get("content", []))
    try:
        places = [s.get("name") for s in json.loads(text).get("studios", [])]
    except ValueError:
        places = []
    out = {"places": places, "studio": "ok" if places else "no-places"}
    if not places:
        out["fix"] = "Studio is reachable but no place is open (or 'Enable Studio as MCP server' is off). Ask the user to open the place."
    return out


if __name__ == "__main__":
    sys.exit(main())
