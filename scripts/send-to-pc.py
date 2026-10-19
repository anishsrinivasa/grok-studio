#!/usr/bin/env python3
"""send-to-pc.py - copy a file from the cloud computer to the user's PC through the bridge.

Runs on the agent's machine (e.g. Grok Bot's cloud computer), Python 3.8+ stdlib only.
It talks MCP (Streamable HTTP) to the bridge's file drop (bridge/files-server.mjs, served at
<tunnel>/files/mcp) and calls put_file in chunks, so a file of any size gets there without
the model having to type its bytes.

Usage:
  python3 send-to-pc.py <file> [dest/relative/path] [--bridge-json PATH] [--chunk-kb 256]

  dest defaults to "<current-game>/<file name>" (current-game from
  /workspace/grok-studio/current-game, if present) - a path inside the drop folder.

Prints one JSON line on success:
  {"localPath": "C:\\Users\\...\\grok-studio\\drop\\...", "httpUrl": "http://127.0.0.1:8766/<token>/...", "bytes": 12345, "path": "..."}
  localPath is valid on the PC (Studio's store_image, the 3D Importer).
  httpUrl is reachable from Roblox Studio on the PC only (Studio's upload_image).

If the key in the session file is rejected, the Grok Bot secret GROK_STUDIO_BRIDGE_KEY is tried.
The bridge session file (/workspace/grok-studio/.bridge.json, written by connect-studio: JSON or
the bridge's KEY=... lines) holds the API key. This script never prints it. Transient failures
(tunnel blips, "fetch failed", HTTP 502/503/504/530) are retried with backoff (1 s, 3 s, 8 s).
"""
import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request

DEFAULT_BRIDGE_JSON = "/workspace/grok-studio/.bridge.json"
CURRENT_GAME = "/workspace/grok-studio/current-game"
PROTOCOL_VERSION = "2025-06-18"
TIMEOUT = 120
TRANSIENT_HTTP = {502, 503, 504, 520, 521, 522, 523, 524, 530}
BACKOFF = (1, 3, 8)   # seconds between retries of a transient failure ("fetch failed", tunnel blips)
LINE_KEYS = {"KEY": "api_key", "STUDIO_URL": "studio_url", "FILES_URL": "files_url",
             "PC_DROP_DIR": "pc_drop_dir", "PC_HTTP_BASE": "pc_http_base", "PC_OS": "pc_os"}


def load_bridge(path):
    """The session file: JSON, or the bridge's KEY=... / FILES_URL=... lines."""
    with open(path, encoding="utf-8-sig") as f:
        text = f.read()
    if text.lstrip().startswith("{"):
        return json.loads(text)
    out = {}
    for line in text.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            if k.strip() in LINE_KEYS:
                out[LINE_KEYS[k.strip()]] = v.strip()
    return out


class Unauthorized(Exception):
    pass


def die(msg, code=1):
    sys.stderr.write(f"[send-to-pc] ERROR: {msg}\n")
    sys.exit(code)


class McpHttp:
    """Minimal MCP Streamable HTTP client: one session, JSON or SSE responses."""

    def __init__(self, url, key):
        self.url = url
        self.key = key
        self.session_id = None
        self.protocol = None
        self.next_id = 1

    def _headers(self):
        h = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {self.key}",
            "User-Agent": "grok-studio-send-to-pc/0.2",
            "ngrok-skip-browser-warning": "1",
        }
        if self.session_id:
            h["Mcp-Session-Id"] = self.session_id
        if self.protocol:
            h["MCP-Protocol-Version"] = self.protocol
        return h

    def _post(self, payload):
        data = json.dumps(payload).encode("utf-8")
        for attempt, delay in enumerate((0,) + BACKOFF):
            if delay:
                time.sleep(delay)
            req = urllib.request.Request(self.url, data=data, headers=self._headers(), method="POST")
            try:
                resp = urllib.request.urlopen(req, timeout=TIMEOUT)
                break
            except urllib.error.HTTPError as e:
                body = e.read(500).decode("utf-8", "replace")
                if e.code in TRANSIENT_HTTP and attempt < len(BACKOFF):
                    continue
                if e.code == 401:
                    raise Unauthorized()
                if e.code == 404 and self.session_id:
                    die("the bridge session expired (404, the bridge restarted). Re-run this command.")
                die(f"HTTP {e.code} from the bridge: {body.strip()[:300]}. Run connect-studio if it persists.")
            except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
                if attempt < len(BACKOFF):
                    continue
                die(f"cannot reach the bridge ({getattr(e, 'reason', e)}). The PC may be asleep or offline: run connect-studio.")
        sid = resp.headers.get("Mcp-Session-Id")
        if sid:
            self.session_id = sid
        ctype = resp.headers.get("Content-Type", "")
        return resp, ctype

    def request(self, method, params):
        rid = self.next_id
        self.next_id += 1
        resp, ctype = self._post({"jsonrpc": "2.0", "id": rid, "method": method, "params": params})
        with resp:
            if "text/event-stream" in ctype:
                msg = self._read_sse(resp, rid)
            else:
                raw = resp.read().decode("utf-8")
                msg = json.loads(raw) if raw.strip() else None
                if isinstance(msg, list):
                    msg = next((m for m in msg if m.get("id") == rid), None)
        if msg is None:
            die(f"no response to {method}")
        if "error" in msg:
            die(f"{method} failed: {msg['error'].get('message')}")
        return msg.get("result")

    @staticmethod
    def _read_sse(resp, rid):
        data_lines = []
        for raw in resp:
            line = raw.decode("utf-8").rstrip("\r\n")
            if line.startswith("data:"):
                data_lines.append(line[5:].lstrip(" "))
            elif line == "":
                if data_lines:
                    try:
                        msg = json.loads("\n".join(data_lines))
                    except json.JSONDecodeError:
                        msg = None
                    data_lines = []
                    if isinstance(msg, dict) and msg.get("id") == rid and ("result" in msg or "error" in msg):
                        return msg
        if data_lines:
            msg = json.loads("\n".join(data_lines))
            if isinstance(msg, dict) and msg.get("id") == rid:
                return msg
        return None

    def notify(self, method, params=None):
        payload = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params
        resp, _ = self._post(payload)
        resp.close()

    def close(self):
        if not self.session_id:
            return
        req = urllib.request.Request(self.url, headers=self._headers(), method="DELETE")
        try:
            urllib.request.urlopen(req, timeout=15).close()
        except Exception:
            pass  # the session times out on its own


def main():
    ap = argparse.ArgumentParser(description="Copy a file to the user's PC through the grok-studio bridge.")
    ap.add_argument("file")
    ap.add_argument("dest", nargs="?", help="relative path inside the drop folder")
    ap.add_argument("--bridge-json", default=DEFAULT_BRIDGE_JSON)
    ap.add_argument("--chunk-kb", type=int, default=256)
    args = ap.parse_args()

    if not os.path.isfile(args.file):
        die(f"not a file: {args.file}")
    try:
        bridge = load_bridge(args.bridge_json)
    except FileNotFoundError:
        die(f"{args.bridge_json} not found: Studio isn't connected yet (run connect-studio).")
    except (OSError, ValueError) as e:
        die(f"cannot read {args.bridge_json}: {e}")
    env_key = os.environ.get("GROK_STUDIO_BRIDGE_KEY", "").strip()
    url, key = bridge.get("files_url"), bridge.get("api_key") or env_key
    if not url or not key:
        die(f"{args.bridge_json} has no files_url/api_key (bridge started without the file drop?).")

    dest = args.dest
    if not dest:
        name = os.path.basename(args.file)
        game = ""
        try:
            with open(CURRENT_GAME, encoding="utf-8") as f:
                game = f.read().strip()
        except OSError:
            pass
        dest = f"{game}/{name}" if game else name
    dest = dest.replace("\\", "/").lstrip("/")

    chunk = max(16, min(args.chunk_kb, 8192)) * 1024
    # The session file's key first; if it is stale (401), the GROK_STUDIO_BRIDGE_KEY secret.
    init = None
    for k in [key] + ([env_key] if env_key and env_key != key else []):
        client = McpHttp(url, k)
        try:
            init = client.request("initialize", {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "grok-studio-send-to-pc", "version": "0.2.0"},
            })
            break
        except Unauthorized:
            continue
    else:
        die("the bridge rejected the API key (401): the key was rotated or the session file is stale. "
            "Run `bridge-check.py --studio` (it heals .bridge.json from the GROK_STUDIO_BRIDGE_KEY secret) or connect-studio.")
    client.protocol = (init or {}).get("protocolVersion", PROTOCOL_VERSION)
    client.notify("notifications/initialized")

    result = None
    size = os.path.getsize(args.file)
    with open(args.file, "rb") as f:
        first = True
        while True:
            block = f.read(chunk)
            if not block and not first:
                break
            res = client.request("tools/call", {
                "name": "put_file",
                "arguments": {"path": dest, "base64": base64.b64encode(block).decode("ascii"), "append": not first},
            })
            if res.get("isError"):
                text = " ".join(c.get("text", "") for c in res.get("content", []))
                client.close()
                die(f"put_file failed: {text}")
            result = res.get("structuredContent")
            if result is None:
                result = json.loads(res["content"][0]["text"])
            first = False
            if not block:
                break
    client.close()
    if result.get("bytes") != size:
        die(f"size mismatch after upload: sent {size} bytes, the PC has {result.get('bytes')}")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
