# Bridge: Roblox Studio on your PC, reachable by the cloud bot team

Roblox Studio's MCP server is a **stdio** server: only a program on the PC that runs Studio
can start it. Cloud agents (Grok Bot's cloud computer) can't, and they can't reach your
`localhost` either. The bridge runs on your PC and fixes both:

```
cloud bots --HTTPS--> tunnel --> 127.0.0.1:8765  supergateway (API key required)
                                   |-- /roblox-studio/mcp --stdio--> Studio MCP (one process per bot session)
                                   |-- /files/mcp         --stdio--> files-server.mjs (file drop)
                                   '-- /blender/mcp       --stdio--> mcp-for-blender (opt-in)
Roblox Studio (this PC) --> 127.0.0.1:8766/<token>/...   read-only view of the drop folder
```

Normally you never run it by hand. `/setup-bridge` and the `connect-studio` skill install it
through local execution (each command runs on your PC after you approve it). This page is for
doing it yourself and for debugging.

## What it is

- **A supervisor** (`start-bridge.ps1` on Windows, `start-bridge.sh` on macOS). It starts
  supergateway, the drop folder's HTTP view and the tunnel, and restarts any of them that
  dies, with backoff. It also restarts a gateway that stops accepting connections, or a
  tunnel that stops answering.
- **A service.** `install-service` registers a per-user **Scheduled Task**
  (`\GrokStudio\GrokStudioBridge`: at logon, plus a 5-minute keep-alive that revives a
  crashed supervisor, hidden, no admin rights). On macOS it registers a **LaunchAgent**
  (`com.grokstudio.bridge`: at login, restarted if it crashes). It survives reboots.
- **Stable.** The API key is created once (`bridge.key`, readable only by you). With
  ngrok's free static domain the URL never changes either, so the bots register their
  connector once.
- **Fast.** supergateway is installed once with `npm ci` (pinned by `package.json` and
  `package-lock.json`) and run with `node`, not `npx`. Health checks use TCP/`curl`.
  Measured on Windows 11: about 2.5 s from launch to ready, about 7-10 s for a full
  `start`/`restart` through Task Scheduler.

## Commands

Windows: `powershell -ExecutionPolicy Bypass -File .\start-bridge.ps1 <command> [options]`
macOS: `bash start-bridge.sh <command> [options]`

| Command | Does |
|---|---|
| `install-service` | saves the config, creates the key, installs supergateway, registers the service, starts it, prints the session |
| `uninstall-service` | stops it and removes the service (`-Purge` / `--purge` also deletes key, config, logs, packages) |
| `status` | cheap JSON (about 1 s): `running, gateway_up, files_up, tunnel_up, url, tunnel, tunnel_stable, tunnel_error, state, key_present`; exit 0 healthy, 1 degraded, 3 not running. `-Deep` also asks the public URL and checks the service |
| `start`, `restart` | start or restart (through the service if installed) and print the session |
| `stop` | clean stop; stays stopped until `start` or the next reboot/login |
| `session` | prints the session, one field per line |
| `run` | the supervisor in the foreground (what the service runs; Ctrl+C stops) |

Options (PowerShell / bash):
- `-NgrokDomain` / `--ngrok-domain` (e.g. `name.ngrok-free.dev`)
- `-TunnelProvider ngrok|cloudflare|none` / `--tunnel-provider ...`
- `-Port` / `--port`
- `-NoStudio` / `--no-studio`, `-NoFiles` / `--no-files`, `-Blender` / `--blender`
- `-DropDir` / `--drop-dir`
- `-TaskName` / `--task-name` (the service name)
- `-RotateKey` / `--rotate-key`

The settings you pass are saved to `config.json` and reused.

The session output is one short field per line, so a terminal can't wrap a value in two.
The last line is always `SESSION_FILE=`:
```
STATUS=ready
KEY=<43 chars>
STUDIO_URL=https://name.ngrok-free.dev/roblox-studio/mcp
FILES_URL=https://name.ngrok-free.dev/files/mcp
PC_DROP_DIR=C:\Users\you\grok-studio\drop
PC_HTTP_BASE=http://127.0.0.1:8766/<token>
TUNNEL=ngrok
TUNNEL_STABLE=yes
PC_OS=windows
PORT=8765
SESSION_FILE=C:\Users\you\grok-studio\bridge\session.json
```

## Tunnels

| Provider | Account | URL | Notes |
|---|---|---|---|
| `ngrok` (default) | free account | **stable** with your static domain | the authtoken is read once from `NGROK_AUTHTOKEN` and saved to ngrok's own config, only if ngrok has none. A free account allows one ngrok agent at a time (`ERR_NGROK_108`) |
| `cloudflare` (fallback) | none | **changes every time the tunnel restarts** (`TUNNEL_STABLE=no`), so connectors must be updated | `cloudflared` 2026.9.3 is downloaded once into `bin\` and SHA-256 checked. Health comes from its local `/ready` metrics (port+2). The bridge never looks up a fresh `trycloudflare.com` name from the PC, because Windows caches "no such host" for minutes |
| `none` | - | `http://127.0.0.1:8765` | local agents and tests |

## Files it keeps (next to the script; ignored by git, see `.gitignore`)

| File | Contains |
|---|---|
| `bridge.key` | the API key (user-only ACL / `chmod 600`) |
| `session.json` | URLs, key, PIDs, state (user-only) |
| `config.json` | port, tunnel, ngrok domain, what is exposed, drop-folder token, tool paths (not secret) |
| `node_modules\` | supergateway 4.2.0 + dependencies |
| `logs\` | `supervisor.log`, plus one log per child process |
| `run\`, `bin\` | stop markers, the generated gateway config, the pinned cloudflared |

## File drop

`files-server.mjs` (Node, no dependencies) serves two things:
- `/files/mcp` with the `put_file` (chunked, `append`), `list_files` and `delete_file`
  tools. Paths are relative and sanitized: no `..`, no absolute paths, no reserved
  Windows names.
- A read-only, loopback-only HTTP view on port+1, with a random path token and a Host
  check, so Studio's `upload_image` (HTTP URL) and `store_image` (local path) can use
  dropped files.

The cloud side uses `scripts/send-to-pc.py <file> [dest]`, which chunks and retries
transient errors. `scripts/bridge-check.py [--studio]` is the cheap cloud-side health check.

## Security

- **Anyone with the URL + key can run Luau in your open Studio places and drop files on this
  PC** (and run Python in Blender, if you enable it). Treat the key like a password.
  `-RotateKey` replaces it.
- The gateway listens on `127.0.0.1` only and refuses requests without the key (401). Only
  `/healthz` is open (it returns `ok`). The key is read from `bridge.key` (`--apiKeyFile`),
  not from the command line or the environment.
- Blender MCP safe mode (`BLENDER_MCP_SAFE_MODE=1`) is on whenever Blender is enabled.
- `stop` when you don't need it, and `uninstall-service` to remove it.

## Tested (Windows 11, Studio open; never over a tunnel with Studio exposed)

- 5 concurrent sessions against `/roblox-studio/mcp`, read-only tools: 5/5 OK, 28 tools
  each, 0.4 s per session. One Studio MCP process per session, all gone after the
  sessions close.
- 50 parallel `get_studio_state` calls: 50/50 OK in 0.86 s.
- Missing or wrong key: 401. `/healthz`: 200.
- 1 MB binary through `send-to-pc.py`: byte-identical locally, through a Cloudflare quick
  tunnel (Streamable HTTP + SSE works through it), and via the HTTP view. Path traversal,
  absolute paths and reserved names are refused.
- Supervisor: a killed gateway or drop server is back within about 2 s. A killed
  cloudflared is back with a new URL in `session.json` within about 6 s.
- Scheduled Task without admin rights: install, start, restart, `-RotateKey` (old key 401,
  new key 200), stop (holds through a keep-alive tick), a hard-killed supervisor revived by
  the keep-alive, uninstall (task and folder removed, nothing left running).
- macOS: `start-bridge.sh` was exercised under Git Bash on Windows (run, status, session,
  stop, child restart, file round trip). **launchd and StudioMCP on a real Mac are
  untested.** ngrok with a static domain under the new supervisor is untested here (the
  tests never used the user's ngrok account).

## Why supergateway

[supergateway](https://github.com/supercorp-ai/supergateway) serves several stdio servers on
one port with an API key (`--apiKeyFile`) and stateful Streamable HTTP, one child per
session. [mcp-proxy](https://github.com/sparfenyuk/mcp-proxy) has no API-key option in
server mode, so anything reaching the port could drive Studio.
