#!/usr/bin/env bash
# start-bridge.sh - expose your LOCAL Roblox Studio MCP and Blender MCP servers to a
# REMOTE agent (e.g. Grok Bot on a cloud Linux box) for one build session. macOS.
#
#   remote agent --HTTPS--> ngrok --> 127.0.0.1:$PORT (supergateway, API key required)
#                                        |-- /roblox-studio/mcp --stdio--> StudioMCP
#                                        '-- /blender/mcp       --stdio--> mcp-for-blender
#
# Usage:
#   ./bridge/start-bridge.sh [--tunnel] [--ngrok-url https://x.ngrok.app] [--port 8765]
#                            [--no-studio] [--no-blender] [--unsafe-blender] [--yes]
#
# SECURITY: anyone with the URL + key can run arbitrary Luau in your open Studio places
# and arbitrary Python in Blender on this machine. Only run during a build session.
# Ctrl+C tears everything down. A fresh key is generated every run.
#
# Why supergateway (https://github.com/supercorp-ai/supergateway) rather than mcp-proxy:
# mcp-proxy (sparfenyuk, v0.13) has no API-key option in server mode; supergateway has
# --apiKey and a multi-server --config, so one authenticated port serves both tools.
#
# Status: lightly tested on Linux with stand-in stdio servers; NOT tested on macOS with
# real Studio/Blender yet. Please report issues.

set -euo pipefail

PORT=8765
TUNNEL=0
NGROK_URL=""
NO_STUDIO=0
NO_BLENDER=0
UNSAFE_BLENDER=0
ASSUME_YES=0
SUPERGATEWAY_PKG="supergateway@4"   # pinned major version

info() { printf '\033[36m[bridge]\033[0m %s\n' "$*"; }
warn() { printf '\033[33m[bridge]\033[0m %s\n' "$*"; }
die()  { printf '\033[31m[bridge] ERROR:\033[0m %s\n' "$*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="$2"; shift 2 ;;
    --tunnel) TUNNEL=1; shift ;;
    --ngrok-url) NGROK_URL="$2"; TUNNEL=1; shift 2 ;;
    --no-studio) NO_STUDIO=1; shift ;;
    --no-blender) NO_BLENDER=1; shift ;;
    --unsafe-blender) UNSAFE_BLENDER=1; shift ;;
    --yes|-y) ASSUME_YES=1; shift ;;
    -h|--help) sed -n '2,22p' "$0"; exit 0 ;;
    *) die "Unknown option: $1 (see --help)" ;;
  esac
done

# --------------------------------------------------------------------------------------
# 0. Security confirmation
# --------------------------------------------------------------------------------------
cat <<'BANNER'

==================================================================
 grok-studio bridge - REMOTE CODE EXECUTION ON THIS MACHINE
==================================================================
 Anyone holding the URL + API key printed below can run code in your
 open Roblox Studio places and in Blender on this computer.
 Run only during a build session. Press Ctrl+C to tear everything down.

BANNER
if [[ $ASSUME_YES -ne 1 ]]; then
  read -r -p "Type 'yes' to continue: " answer
  [[ "$answer" == "yes" ]] || { info "Aborted."; exit 0; }
fi
[[ $NO_STUDIO -eq 1 && $NO_BLENDER -eq 1 ]] && die "Nothing to expose (--no-studio and --no-blender)."

# --------------------------------------------------------------------------------------
# 1. Prerequisites
# --------------------------------------------------------------------------------------
info "Checking prerequisites..."
have npx || die "Node.js (npx) not found. Install Node.js LTS (https://nodejs.org or: brew install node)."

STUDIO_MCP=""
if [[ $NO_STUDIO -ne 1 ]]; then
  STUDIO_MCP="${ROBLOX_STUDIO_MCP_PATH:-/Applications/RobloxStudio.app/Contents/MacOS/StudioMCP}"
  [[ -x "$STUDIO_MCP" ]] || die "Roblox Studio MCP not found/executable at '$STUDIO_MCP'. Update Studio, then enable Assistant > ... > Manage MCP Servers > 'Enable Studio as MCP server'. (Override with ROBLOX_STUDIO_MCP_PATH.)"
fi

if [[ $NO_BLENDER -ne 1 ]]; then
  have uvx || die "uv/uvx not found. Install: curl -LsSf https://astral.sh/uv/install.sh | sh  (or: brew install uv), then run: uvx mcp-for-blender setup"
  warn 'Make sure Blender is open with the "MCP for Blender" add-on enabled (N panel > MCP for Blender > Start MCP Server).'
fi

if [[ $TUNNEL -eq 1 ]]; then
  have ngrok || die "ngrok not found. Install (brew install ngrok) and run once: ngrok config add-authtoken <token>"
fi
have curl || die "curl not found."

if (exec 3<>"/dev/tcp/127.0.0.1/$PORT") 2>/dev/null; then
  die "Port $PORT is already in use. Use --port <other>."
fi

# --------------------------------------------------------------------------------------
# 2. API key (256 bits, URL-safe)
# --------------------------------------------------------------------------------------
if have openssl; then
  KEY="$(openssl rand -base64 32 | tr '+/' '-_' | tr -d '=\n')"
else
  KEY="$(LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 48)"
fi

# --------------------------------------------------------------------------------------
# 3. Private runtime dir + supergateway config (contains no secrets)
# --------------------------------------------------------------------------------------
RUNTIME_DIR="$(mktemp -d "${TMPDIR:-/tmp}/grok-studio-bridge.XXXXXX")"
chmod 700 "$RUNTIME_DIR"
CONFIG="$RUNTIME_DIR/servers.json"

json_escape() { local s="$1"; s="${s//\\/\\\\}"; s="${s//\"/\\\"}"; printf '%s' "$s"; }

{
  echo '{'
  echo '  "host": "127.0.0.1",'
  echo "  \"port\": $PORT,"
  echo '  "outputTransport": "streamableHttp",'
  echo '  "stateful": true,'
  echo '  "sessionTimeout": 3600000,'
  echo '  "healthEndpoint": "/healthz",'
  echo '  "mcpServers": {'
  sep=""
  if [[ $NO_STUDIO -ne 1 ]]; then
    printf '    "roblox-studio": { "command": "%s", "args": [] }' "$(json_escape "$STUDIO_MCP")"
    sep=","
  fi
  if [[ $NO_BLENDER -ne 1 ]]; then
    printf '%s\n    "blender": { "command": "uvx", "args": ["mcp-for-blender"] }' "$sep"
  fi
  echo
  echo '  }'
  echo '}'
} > "$CONFIG"

GATEWAY_PID=""
NGROK_PID=""

cleanup() {
  trap - EXIT INT TERM
  info "Shutting down bridge..."
  for pid in "$NGROK_PID" "$GATEWAY_PID"; do
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      # Kill children first (npx -> node -> MCP servers), then the process itself.
      pkill -TERM -P "$pid" 2>/dev/null || true
      kill -TERM "$pid" 2>/dev/null || true
    fi
  done
  sleep 1
  for pid in "$NGROK_PID" "$GATEWAY_PID"; do
    [[ -n "$pid" ]] && kill -KILL "$pid" 2>/dev/null || true
  done
  rm -rf "$RUNTIME_DIR"
  info "Stopped. The API key from this session is now useless."
}
trap cleanup EXIT
trap 'exit 130' INT TERM

# Secrets/options go via environment, not argv (keeps them out of `ps`).
export SUPERGATEWAY_API_KEY="$KEY"
if [[ $UNSAFE_BLENDER -ne 1 ]]; then export BLENDER_MCP_SAFE_MODE=1; else warn "Blender safe mode is OFF."; fi

# --------------------------------------------------------------------------------------
# 4. Start supergateway
# --------------------------------------------------------------------------------------
info "Starting supergateway on http://127.0.0.1:$PORT ..."
npx -y "$SUPERGATEWAY_PKG" --config "$CONFIG" --exitWithProcess "$$" --logLevel info \
  >"$RUNTIME_DIR/gateway.log" 2>&1 &
GATEWAY_PID=$!

healthy=0
for _ in $(seq 1 90); do
  sleep 1
  kill -0 "$GATEWAY_PID" 2>/dev/null || break
  if curl -fsS --max-time 2 "http://127.0.0.1:$PORT/healthz" >/dev/null 2>&1; then healthy=1; break; fi
done
if [[ $healthy -ne 1 ]]; then
  warn "Gateway did not become healthy. Last log lines:"
  tail -n 20 "$RUNTIME_DIR/gateway.log" >&2 || true
  exit 1
fi
info "Gateway is up (requests without the API key get HTTP 401)."

# --------------------------------------------------------------------------------------
# 5. Optional ngrok tunnel
# --------------------------------------------------------------------------------------
BASE_URL="http://127.0.0.1:$PORT"
if [[ $TUNNEL -eq 1 ]]; then
  info "Starting ngrok tunnel..."
  ng_args=(http "127.0.0.1:$PORT" --log stdout)
  [[ -n "$NGROK_URL" ]] && ng_args+=(--url "$NGROK_URL")
  ngrok "${ng_args[@]}" >"$RUNTIME_DIR/ngrok.log" 2>&1 &
  NGROK_PID=$!
  public=""
  for _ in $(seq 1 30); do
    sleep 1
    kill -0 "$NGROK_PID" 2>/dev/null || break
    public="$(curl -fsS --max-time 2 http://127.0.0.1:4040/api/tunnels 2>/dev/null \
      | grep -o '"public_url":"https://[^"]*"' | head -n1 | cut -d'"' -f4 || true)"
    [[ -n "$public" ]] && break
  done
  if [[ -z "$public" ]]; then
    warn "Could not read the ngrok URL (is your authtoken configured?). Log:"
    tail -n 20 "$RUNTIME_DIR/ngrok.log" >&2 || true
    exit 1
  fi
  BASE_URL="${public%/}"
fi

# --------------------------------------------------------------------------------------
# 6. Print connection details
# --------------------------------------------------------------------------------------
echo
printf '\033[32m================== ADD THESE AS CUSTOM CONNECTORS ==================\033[0m\n'
[[ $NO_STUDIO -ne 1 ]]  && echo "  Roblox Studio MCP : $BASE_URL/roblox-studio/mcp"
[[ $NO_BLENDER -ne 1 ]] && echo "  Blender MCP       : $BASE_URL/blender/mcp"
echo "  Transport         : Streamable HTTP"
echo "  Auth header       : Authorization: Bearer $KEY"
echo "                      (or X-API-Key: $KEY)"
printf '\033[32m====================================================================\033[0m\n'
[[ $TUNNEL -ne 1 ]] && warn "No tunnel: these URLs only work from this machine. Re-run with --tunnel for a cloud agent."
echo
warn 'Keep Studio (with "Enable Studio as MCP server" on) and Blender open.'
warn "Press Ctrl+C to stop the bridge. Remove the connectors from your bot afterwards."

# --------------------------------------------------------------------------------------
# 7. Stay alive until Ctrl+C or a child dies
# --------------------------------------------------------------------------------------
while true; do
  sleep 2
  kill -0 "$GATEWAY_PID" 2>/dev/null || { warn "supergateway exited."; break; }
  if [[ -n "$NGROK_PID" ]] && ! kill -0 "$NGROK_PID" 2>/dev/null; then warn "ngrok exited."; break; fi
done
