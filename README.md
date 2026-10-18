# grok-studio

Bridge that turns Roblox Studio's local stdio MCP server into a public HTTPS
endpoint so Grok (or any remote MCP client) can control Studio over the
internet.

```
Grok ──HTTPS + Bearer──▶ ngrok ──localhost:8787──▶ FastAPI + fastmcp proxy ──stdio──▶ StudioMCP.exe ──▶ Roblox Studio
```

## Prerequisites

- **Windows** with Roblox Studio installed
- **WSL** (Ubuntu) — the bridge runs here
- **Python 3.11+** and [uv](https://docs.astral.sh/uv/) installed in WSL
- **ngrok** installed in WSL with an account (free tier works)
- Studio's MCP server enabled (see below)

## 1. Enable MCP in Roblox Studio

1. Open Roblox Studio with a place loaded.
2. Go to **File → Studio Settings → AI / Assistant**.
3. Turn on **"Enable Studio as MCP server"** (or similar toggle).
4. Verify that `%LOCALAPPDATA%\Roblox\mcp.bat` exists on Windows.

## 2. Set up ngrok

```bash
# Add your authtoken (one-time)
ngrok config add-authtoken <YOUR_NGROK_TOKEN>

# Claim a free static domain at https://dashboard.ngrok.com/domains
# Then edit ngrok.yml and uncomment/set your domain:
#   domain: your-domain.ngrok-free.app
```

## 3. Configure the bridge

```bash
cd grok-studio

# Install dependencies
uv sync

# Create your .env from the example
cp .env.example .env

# Generate a secure bridge token
openssl rand -hex 32
# Paste the output into .env as BRIDGE_TOKEN=<token>
```

Your `.env` should look like:

```
BRIDGE_TOKEN=<your-generated-token>
PORT=8787
RBX_MCP_COMMAND=cmd.exe
RBX_MCP_ARGS=/c %LOCALAPPDATA%\Roblox\mcp.bat
NGROK_DOMAIN=your-domain.ngrok-free.app
```

## 4. Run

Open two terminals in WSL:

**Terminal 1 — Bridge:**
```bash
uv run uvicorn app:app --port 8787
```

**Terminal 2 — Tunnel:**
```bash
./scripts/tunnel.sh
```

## 5. Verify

```bash
# Health check (no auth needed)
curl http://localhost:8787/healthz

# List tools via the test client (localhost)
uv run scripts/test_client.py http://localhost:8787/mcp <BRIDGE_TOKEN>

# List tools via ngrok (public URL)
uv run scripts/test_client.py https://your-domain.ngrok-free.app/mcp <BRIDGE_TOKEN>

# Confirm auth works — this should return 401
curl https://your-domain.ngrok-free.app/mcp
```

## 6. Connect Grok

Configure your xAI remote MCP tool with:

| Field            | Value                                        |
| ---------------- | -------------------------------------------- |
| `server_url`     | `https://your-domain.ngrok-free.app/mcp`     |
| `server_label`   | `roblox_studio`                              |
| `authorization`  | `Bearer <BRIDGE_TOKEN>`                      |

### Suggested Grok system prompt addition

> You have access to Roblox Studio through MCP tools. Always call
> `list_roblox_studios` first to get the available Studio instances and
> their `studio_id` values. Pass the correct `studio_id` on every
> subsequent Roblox tool call. Confirm with the user before modifying
> their game.

## Environment variables

| Variable           | Default                                     | Description                                      |
| ------------------ | ------------------------------------------- | ------------------------------------------------ |
| `BRIDGE_TOKEN`     | *(required)*                                | Bearer token for authenticating requests         |
| `PORT`             | `8787`                                      | Port uvicorn listens on                          |
| `RBX_MCP_COMMAND`  | `cmd.exe`                                   | Command to launch the Studio MCP server          |
| `RBX_MCP_ARGS`     | `/c %LOCALAPPDATA%\Roblox\mcp.bat`          | Arguments for the command                        |
| `RBX_MCP_VERBOSE`  | *(empty)*                                   | Set to `1` to pass `--verbose` to StudioMCP.exe  |
| `NGROK_DOMAIN`     | *(empty)*                                   | Your ngrok static domain (for reference in .env) |

## How it works

1. **FastAPI** starts and loads the `fastmcp` proxy, which spawns
   `cmd.exe /c mcp.bat` as a child process (WSL interop runs it as a real
   Windows process).
2. `mcp.bat` finds and runs `StudioMCP.exe`, Roblox's MCP proxy. It
   connects to any open Studio windows via a local WebSocket on
   `127.0.0.1`. Authentication between Studio and StudioMCP.exe is
   handled automatically through a token file.
3. The fastmcp proxy re-exposes all of Studio's MCP tools over Streamable
   HTTP at `/mcp`.
4. Bearer-token middleware protects `/mcp` — only requests with the
   correct `Authorization: Bearer <token>` header pass through.
5. **ngrok** publishes `localhost:8787` at a static HTTPS domain that Grok
   can reach.

## Troubleshooting

- **"No Roblox Studio instances are connected"** — Make sure Studio is
  open with a place loaded and MCP is enabled in Assistant settings.
- **Tools list is empty** — Studio sends tools after it connects. Restart
  uvicorn after opening Studio, or wait a moment and retry.
- **`cmd.exe` UNC path warning** — The bridge sets `cwd="/mnt/c"` to
  avoid this. If you still see it, check your `RBX_MCP_COMMAND` setting.
- **Token errors** — Ensure `BRIDGE_TOKEN` in `.env` matches what you
  configured in Grok.
- **Debug logging** — Set `RBX_MCP_VERBOSE=1` in `.env` to see
  StudioMCP.exe's verbose output in the uvicorn logs.
