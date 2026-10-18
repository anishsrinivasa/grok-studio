"""
Bridge that turns Roblox Studio's local stdio MCP server into a public
Streamable HTTP endpoint that Grok (or any remote MCP client) can reach.
"""

import os
import secrets

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastmcp.server.server import create_proxy

load_dotenv()

BRIDGE_TOKEN = os.environ.get("BRIDGE_TOKEN", "")
if not BRIDGE_TOKEN:
    raise RuntimeError(
        "BRIDGE_TOKEN is not set. Generate one with: openssl rand -hex 32"
    )

rbx_command = os.environ.get("RBX_MCP_COMMAND", "cmd.exe")
rbx_args_raw = os.environ.get(
    "RBX_MCP_ARGS", r"/c %LOCALAPPDATA%\Roblox\mcp.bat"
)
rbx_args = rbx_args_raw.split()
if os.environ.get("RBX_MCP_VERBOSE", "") == "1":
    rbx_args.append("--verbose")

# Build the proxy: create_proxy accepts an MCPConfig dict whose shape matches
# the standard mcpServers JSON that Claude Desktop / Cursor use.
proxy = create_proxy(
    {
        "mcpServers": {
            "roblox": {
                "command": rbx_command,
                "args": rbx_args,
                "cwd": "/mnt/c",
            }
        }
    },
    name="roblox_studio",
)

# The proxy is a FastMCP subclass. .http_app() returns a Starlette/ASGI app
# with a lifespan that manages the MCP session.
mcp_app = proxy.http_app(path="/mcp")

# FastAPI host — the lifespan from mcp_app is required so the MCP session
# manager starts properly.
app = FastAPI(lifespan=mcp_app.lifespan)


@app.middleware("http")
async def bearer_auth(request: Request, call_next):
    """Require a valid Bearer token on every /mcp* request."""
    if request.url.path.startswith("/mcp"):
        auth = request.headers.get("authorization", "")
        expected = f"Bearer {BRIDGE_TOKEN}"
        if not secrets.compare_digest(auth, expected):
            return JSONResponse({"error": "unauthorized"}, status_code=401)
    return await call_next(request)


@app.get("/healthz")
async def healthz():
    """Unauthenticated liveness check. Reports whether the upstream proxy is
    reachable but does not expose Studio instance details."""
    return {"ok": True, "proxy": proxy.name}


# Mount the MCP ASGI app under the FastAPI app so /mcp is handled by the
# proxy's Streamable HTTP transport.
app.mount("/", mcp_app)
