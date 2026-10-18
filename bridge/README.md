# Bridge: local Studio + Blender MCP for remote agents

Roblox Studio's MCP server and the Blender MCP server only speak **stdio**, so they must be
started by a process on the PC that runs Studio/Blender. Remote agents (e.g. Grok Bot on a
cloud Linux box) can't do that. These scripts start both servers behind **one**
authenticated Streamable HTTP endpoint on `127.0.0.1` using
[supergateway](https://github.com/supercorp-ai/supergateway), and can expose it through an
[ngrok](https://ngrok.com) tunnel on your own account.

| Script | OS | Status |
|---|---|---|
| `start-bridge.ps1` | Windows (primary) | **Untested on Windows**; parse-checked with PowerShell 7 |
| `start-bridge.sh` | macOS | Not tested on macOS with real Studio/Blender; the full flow (gateway, API key 401/200, teardown) was smoke-tested on Linux with stand-in stdio servers |

## Prerequisites
- Node.js LTS (`npx`) - runs supergateway (pinned to major v4).
- uv (`uvx`) - runs `mcp-for-blender`; Blender open with the **MCP for Blender** add-on
  enabled (`uvx mcp-for-blender setup` installs it).
- Roblox Studio open with **Assistant > ... > Manage MCP Servers > Enable Studio as MCP server**.
- ngrok (for remote agents): install and run `ngrok config add-authtoken <token>` once.

## Run
```powershell
# Windows (PowerShell)
powershell -ExecutionPolicy Bypass -File .\bridge\start-bridge.ps1 -Tunnel
```
```bash
# macOS
./bridge/start-bridge.sh --tunnel
```
Options: port (`-Port` / `--port`, default 8765), reserved ngrok domain (`-NgrokUrl` /
`--ngrok-url`), `-NoStudio`/`--no-studio`, `-NoBlender`/`--no-blender`,
`-UnsafeBlender`/`--unsafe-blender` (turns off Blender safe mode - not recommended), `-Yes`/`--yes`.

The script prints:
```
Roblox Studio MCP : https://<random>.ngrok-free.app/roblox-studio/mcp
Blender MCP       : https://<random>.ngrok-free.app/blender/mcp
Auth header       : Authorization: Bearer <key>   (or X-API-Key: <key>)
```
Add each URL as a **custom connector** (remote MCP server, Streamable HTTP) in your bot,
with the auth header. Then install this plugin in the bot so it gets the skills.

## Security
- **Anyone with the URL + key can run arbitrary Luau in your open Studio places and Python in
  Blender on your PC.** Treat the key like a password.
- A new 256-bit key is generated every run; the gateway refuses requests without it (401)
  and binds to `127.0.0.1` only (not your LAN). Only `/healthz` is unauthenticated (returns "ok").
- Blender MCP safe mode (`BLENDER_MCP_SAFE_MODE=1`) is on by default.
- Run only during a build session. **Ctrl+C tears down** the gateway, both MCP servers, and
  the tunnel, and deletes the temp config. Remove the connectors from your bot afterwards.
- Your ngrok account can add more protection (IP allowlists, OAuth) via ngrok traffic
  policies if you need it.

## Why not mcp-proxy?
[mcp-proxy](https://github.com/sparfenyuk/mcp-proxy) (v0.13, actively maintained) bridges
stdio to SSE/Streamable HTTP and supports named servers, but has **no API-key option for its
server mode**; exposing it through a tunnel would let anyone who finds the URL control
Studio. If you prefer it for local-only use: `uvx mcp-proxy --port 8765 --named-server
blender 'uvx mcp-for-blender'` (no tunnel!).

## Alternatives
- Cloudflare quick tunnel instead of ngrok: `cloudflared tunnel --url http://127.0.0.1:8765`
  (not wired into the scripts).
- Tailscale Funnel / your own reverse proxy with TLS.
