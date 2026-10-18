#!/usr/bin/env bash
# start-bridge.sh - the grok-studio bridge for macOS and Linux/WSL: exposes Roblox Studio (plus a
# small file drop, and optionally Blender) to the cloud bot team over one HTTPS URL.
#
#   cloud bots --HTTPS--> tunnel --> 127.0.0.1:$PORT (supergateway, API key required)
#                                      |-- /roblox-studio/mcp --stdio--> StudioMCP (one per session)
#                                      |-- /files/mcp         --stdio--> files-server.mjs (file drop)
#                                      '-- /blender/mcp       --stdio--> mcp-for-blender (opt-in: --blender)
#   Roblox Studio (this Mac) --> 127.0.0.1:$((PORT+1))/<token>/...  (read-only view of the drop folder)
#
# Usage: ./start-bridge.sh <command> [options]
#   run                 supervisor in the foreground (default); Ctrl+C stops
#   install-service     install the service (macOS: launchd LaunchAgent; Linux: systemd --user unit),
#                       started at login and restarted if it crashes; then start it
#   uninstall-service   stop and remove the LaunchAgent (--purge also deletes key/config/logs)
#   status              cheap JSON health check (--deep also asks the public URL)
#   start | stop | restart
#   session             print the session: STATUS=, KEY=, STUDIO_URL=, FILES_URL=, ... one per line
# Options: --port N  --tunnel-provider ngrok|cloudflare|none  --ngrok-domain NAME.ngrok-free.dev
#          --blender  --no-studio  --no-files  --drop-dir DIR  --task-name LABEL  --rotate-key
#          --studio-mcp-path PATH  --json-output  --deep  --purge  --unsafe-blender
#   --json-output  print the session (or result) as ONE compact JSON line; nothing else on stdout
#
# Linux: Roblox Studio doesn't run on Linux. Under WSL, point the bridge at the Windows Studio MCP
# launcher (WSL interop runs it through cmd.exe): --studio-mcp-path /mnt/c/Users/<you>/AppData/Local/Roblox/mcp.bat
# (or set ROBLOX_STUDIO_MCP_PATH). The service needs systemd (WSL: [boot] systemd=true in
# /etc/wsl.conf). 'loginctl enable-linger ${USER:-$(id -un)}' keeps it running while logged out (optional).
#
# Kept next to this script: bridge.key (the API key, created once, chmod 600; --rotate-key
# replaces it), config.json (port, tunnel, static ngrok domain; not secret), session.json
# (URLs + key, chmod 600), node_modules/ (supergateway pinned by package-lock.json), logs/ run/ bin/.
#
# Tunnels: ngrok (default; with a static domain the URL never changes; the authtoken is applied
# once from $NGROK_AUTHTOKEN if ngrok isn't configured), cloudflare (fallback, no account; the URL
# changes on every tunnel start), none (localhost only).
#
# SECURITY: anyone with the URL + key can run Luau in your open Studio places and drop files on
# this Mac (and run Python in Blender, if exposed). Stop it when you don't need it.

set -uo pipefail

CMD="run"
case "${1:-}" in
  run|install-service|uninstall-service|status|start|stop|restart|session|unit) CMD="$1"; shift ;;
  -h|--help|help) sed -n '2,32p' "$0"; exit 0 ;;
esac

OPT_PORT=""; OPT_TUNNEL=""; OPT_DOMAIN=""; OPT_BLENDER=""; OPT_STUDIO=""; OPT_FILES=""; OPT_DROP=""
OPT_LABEL=""; OPT_SMCP=""; ROTATE=0; DEEP=0; PURGE=0; FROM_TASK=0; UNSAFE_BLENDER=0; JSON=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) OPT_PORT="$2"; shift 2 ;;
    --tunnel-provider) OPT_TUNNEL="$2"; shift 2 ;;
    --ngrok-domain|--ngrok-url) OPT_DOMAIN="$2"; shift 2 ;;
    --blender) OPT_BLENDER=true; shift ;;
    --no-studio) OPT_STUDIO=false; shift ;;
    --no-files) OPT_FILES=false; shift ;;
    --drop-dir) OPT_DROP="$2"; shift 2 ;;
    --task-name) OPT_LABEL="$2"; shift 2 ;;
    --rotate-key) ROTATE=1; shift ;;
    --deep) DEEP=1; shift ;;
    --purge) PURGE=1; shift ;;
    --from-task) FROM_TASK=1; shift ;;
    --unsafe-blender) UNSAFE_BLENDER=1; shift ;;
    --studio-mcp-path) OPT_SMCP="$2"; shift 2 ;;
    --json-output) JSON=1; shift ;;
    --tunnel|--no-blender|--yes|-y) shift ;;   # accepted from older callers; no effect
    *) printf 'STATUS=error\nERROR=unknown option %s (see --help)\n' "$1"; exit 2 ;;
  esac
done

BRIDGE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG="$BRIDGE_DIR/config.json"; KEYFILE="$BRIDGE_DIR/bridge.key"; SESSION="$BRIDGE_DIR/session.json"
RUN_DIR="$BRIDGE_DIR/run"; LOG_DIR="$BRIDGE_DIR/logs"; BIN_DIR="$BRIDGE_DIR/bin"
STOP_FILE="$RUN_DIR/stop"; PID_FILE="$RUN_DIR/supervisor.pid"
GATEWAY_JS="$BRIDGE_DIR/node_modules/supergateway/dist/index.js"; FILES_SERVER="$BRIDGE_DIR/files-server.mjs"
mkdir -p "$RUN_DIR" "$LOG_DIR"

CLOUDFLARED_VERSION="2026.9.3"
CF_SHA_darwin_arm64="587c2cfb1c230fe36c7fa7727da78be459dae028cabe8c001291999350f07095"
CF_SHA_darwin_amd64="d1155d0837487f261183b15c1eab6c4ebcad9dc49b94675f1524c3564cea3977"
CF_SHA_linux_amd64="77e26d8d900e0b8469f416239d14b5f296525fdf79fee6f511ef55609e3fbac2"
CF_SHA_linux_arm64="aaeb2d7d0da3614634c7e03ab13487a1522c2e79165ed2929cfe23d5e95b326d"

have() { command -v "$1" >/dev/null 2>&1; }
log() { local l; l="[$(date '+%Y-%m-%d %H:%M:%S')] $*"; echo "$l" >> "$LOG_DIR/supervisor.log"; [[ $FROM_TASK -eq 1 ]] || echo "[bridge] $*" >&2; }
json_str() { local v="$1"; v="${v//\\/\\\\}"; v="${v//\"/\\\"}"; v="${v//$'\n'/ }"; v="${v//$'\r'/}"; printf '"%s"' "$v"; }
# A short result (stopped, uninstalled, error, ...): STATUS=/ERROR= lines, or one JSON line.
out_result() {
  if [[ $JSON -eq 1 ]]; then if [[ -n "${2:-}" ]]; then printf '{"status":"%s","error":%s}\n' "$1" "$(json_str "$2")"; else printf '{"status":"%s"}\n' "$1"; fi
  else echo "STATUS=$1"; [[ -n "${2:-}" ]] && echo "ERROR=$2"; fi
  return 0
}
fail() { log "ERROR: $*"; out_result error "$*"; exit 1; }
rand_token() { if have openssl; then openssl rand -base64 "$1" | tr '+/' '-_' | tr -d '=\r\n'; else LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c $(( $1 * 4 / 3 )); fi; }
sha256_of() { if have shasum; then shasum -a 256 "$1" | cut -d' ' -f1; else sha256sum "$1" | cut -d' ' -f1; fi; }
http_code() { curl -s -o /dev/null -w '%{http_code}' --max-time "${2:-3}" -H 'ngrok-skip-browser-warning: 1' "$1" 2>/dev/null || true; }
tcp_up() { (exec 9<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }
alive() { [[ -n "${1:-}" ]] && kill -0 "$1" 2>/dev/null; }
proc_cmd() { if [[ -r "/proc/$1/cmdline" ]]; then tr '\0' ' ' < "/proc/$1/cmdline"; else ps -p "$1" -o command= 2>/dev/null; fi; }

NODE_BIN="$(command -v node || true)"
[[ -n "$NODE_BIN" ]] || { out_result error "Node.js not found. Install it (macOS: brew install node; Linux: your package manager or https://nodejs.org)."; exit 1; }

# One node call reads config + session into shell variables (node is a prerequisite anyway).
load_state() {
  eval "$("$NODE_BIN" -e '
    const fs = require("fs");
    const read = (f) => { try { return JSON.parse(fs.readFileSync(f, "utf8")); } catch { return {}; } };
    const c = read(process.argv[1]), s = read(process.argv[2]);
    const q = (v) => "'"'"'" + String(v ?? "").replace(/'"'"'/g, "'"'"'\\'"'"''"'"'") + "'"'"'";
    const out = { C_PORT: c.port ?? 8765, C_TUNNEL: c.tunnel ?? "", C_DOMAIN: c.ngrok_domain ?? "",
      C_STUDIO: c.studio ?? true, C_FILES: c.files ?? true, C_BLENDER: c.blender ?? false,
      C_DROP: c.drop_dir ?? "", C_TOKEN: c.files_token ?? "", C_LABEL: c.task_name ?? "",
      C_NGROK: c.ngrok_path ?? "", C_SMCP: c.studio_mcp_path ?? "",
      S_STATE: s.state ?? "", S_PUBLIC: s.public_url ?? "", S_TUNNEL: s.tunnel ?? "", S_SUP: s.supervisor_pid ?? "",
      S_GW: s.gateway_pid ?? "", S_FILES: s.files_pid ?? "", S_TUN: s.tunnel_pid ?? "", S_UPDATED: s.updated_at ?? "",
      S_STABLE: s.tunnel_stable ?? false, S_ERR: s.tunnel_error ?? "" };
    for (const [k, v] of Object.entries(out)) console.log(k + "=" + q(v));
  ' "$CONFIG" "$SESSION")"
}
load_state
PORT="${OPT_PORT:-$C_PORT}"; TUNNEL="${OPT_TUNNEL:-$C_TUNNEL}"; DOMAIN="${OPT_DOMAIN:-$C_DOMAIN}"
DOMAIN="${DOMAIN#https://}"; DOMAIN="${DOMAIN#http://}"; DOMAIN="${DOMAIN%/}"
STUDIO="${OPT_STUDIO:-$C_STUDIO}"; FILES="${OPT_FILES:-$C_FILES}"; BLENDER="${OPT_BLENDER:-$C_BLENDER}"
DROP_DIR="${OPT_DROP:-$C_DROP}"; DROP_DIR="${DROP_DIR:-$HOME/grok-studio/drop}"
TOKEN="${C_TOKEN:-$(rand_token 16)}"; LABEL="${OPT_LABEL:-$C_LABEL}"
SMCP="${OPT_SMCP:-${ROBLOX_STUDIO_MCP_PATH:-$C_SMCP}}"
NGROK_BIN="${C_NGROK:-$(command -v ngrok || true)}"; [[ -x "$NGROK_BIN" ]] || NGROK_BIN="$(command -v ngrok || true)"
[[ "$TUNNEL" == auto ]] && TUNNEL=""
FILES_PORT=$((PORT + 1)); METRICS_PORT=$((PORT + 2))
case "$(uname -s)" in Darwin) PC_OS=macos ;; Linux) PC_OS=linux ;; *) PC_OS="$(uname -s | tr '[:upper:]' '[:lower:]')" ;; esac
IS_WSL=0; [[ $PC_OS == linux ]] && grep -qi microsoft /proc/version 2>/dev/null && IS_WSL=1
if [[ -z "$LABEL" ]]; then if [[ $PC_OS == macos ]]; then LABEL=com.grokstudio.bridge; else LABEL=grok-studio-bridge; fi; fi
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"; UNIT="$UNIT_DIR/$LABEL.service"
# Git Bash/MSYS (testing only): native programs need Windows paths and PIDs.
WIN=0; have cygpath && WIN=1
winpath() { if [[ $WIN -eq 1 && -n "$1" ]]; then cygpath -w "$1"; else printf '%s' "$1"; fi; }
SELF_PID=$$; [[ -r /proc/$$/winpid ]] && SELF_PID="$(cat /proc/$$/winpid)"

ngrok_configured() {
  [[ -n "$NGROK_BIN" ]] || return 1
  local cfg; cfg="$("$NGROK_BIN" config check 2>&1 | sed -n 's/.*Valid configuration file at \(.*\)$/\1/p' | head -n1)"
  [[ -n "$cfg" && -f "$cfg" ]] && grep -Eq '^[[:space:]]*authtoken:[[:space:]]*[^[:space:]]+' "$cfg"
}
resolve_tunnel() {
  [[ -n "$TUNNEL" ]] && return
  if [[ -n "$NGROK_BIN" ]] && { [[ -n "$DOMAIN" ]] || [[ -n "${NGROK_AUTHTOKEN:-}" ]] || ngrok_configured; }; then TUNNEL=ngrok; else TUNNEL=cloudflare; fi
}

save_config() {
  GS_PORT="$PORT" GS_TUNNEL="$TUNNEL" GS_DOMAIN="$DOMAIN" GS_STUDIO="$STUDIO" GS_FILES="$FILES" GS_BLENDER="$BLENDER" \
  GS_DROP="$DROP_DIR" GS_TOKEN="$TOKEN" GS_LABEL="$LABEL" GS_NODE="$NODE_BIN" GS_NGROK="$NGROK_BIN" GS_SMCP="$SMCP" \
  "$NODE_BIN" -e '
    const e = process.env, b = (v) => v === "true";
    const c = { port: Number(e.GS_PORT), tunnel: e.GS_TUNNEL, ngrok_domain: e.GS_DOMAIN, studio: b(e.GS_STUDIO),
      files: b(e.GS_FILES), blender: b(e.GS_BLENDER), drop_dir: e.GS_DROP, files_token: e.GS_TOKEN,
      task_name: e.GS_LABEL, node_path: e.GS_NODE, ngrok_path: e.GS_NGROK, studio_mcp_path: e.GS_SMCP };
    require("fs").writeFileSync(process.argv[1], JSON.stringify(c, null, 2) + "\n");
  ' "$CONFIG"
}

get_key() {
  if [[ $ROTATE -eq 1 || ! -s "$KEYFILE" ]]; then
    ( umask 077; rand_token 32 > "$KEYFILE.tmp"; echo >> "$KEYFILE.tmp" ); chmod 600 "$KEYFILE.tmp"; mv -f "$KEYFILE.tmp" "$KEYFILE"
    if [[ $ROTATE -eq 1 ]]; then log "API key rotated."; else log "API key created."; fi
    ROTATE=0
  fi
  head -n1 "$KEYFILE" | tr -d '\r\n'
}

install_runtime() {
  [[ -f "$GATEWAY_JS" ]] && return
  log "Installing supergateway (pinned, one time)..."
  local verb=install; [[ -f "$BRIDGE_DIR/package-lock.json" ]] && verb=ci
  ( cd "$BRIDGE_DIR" && npm "$verb" --omit=dev --no-audit --no-fund --loglevel=error ) >> "$LOG_DIR/supervisor.log" 2>&1
  [[ -f "$GATEWAY_JS" ]] || fail "npm $verb did not install supergateway (see logs/supervisor.log)."
}

get_cloudflared() {
  if have cloudflared; then command -v cloudflared; return; fi
  local os arch asset sha exe tmp
  case "$(uname -s)" in Darwin) os=darwin ;; Linux) os=linux ;; *) fail "No pinned cloudflared for $(uname -s); install cloudflared." ;; esac
  case "$(uname -m)" in arm64|aarch64) arch=arm64 ;; x86_64|amd64) arch=amd64 ;; *) fail "No pinned cloudflared for $(uname -m)." ;; esac
  local var="CF_SHA_${os}_${arch}"; sha="${!var}"; exe="$BIN_DIR/cloudflared-$CLOUDFLARED_VERSION"
  if [[ -x "$exe" ]]; then echo "$exe"; return; fi
  mkdir -p "$BIN_DIR"
  if [[ $os == darwin ]]; then asset="cloudflared-$os-$arch.tgz"; else asset="cloudflared-$os-$arch"; fi
  log "Downloading cloudflared $CLOUDFLARED_VERSION ($asset, one time)..."
  tmp="$(mktemp "${TMPDIR:-/tmp}/cloudflared.XXXXXX")"
  curl -fsSL "https://github.com/cloudflare/cloudflared/releases/download/$CLOUDFLARED_VERSION/$asset" -o "$tmp" || { rm -f "$tmp"; fail "cloudflared download failed."; }
  [[ "$(sha256_of "$tmp")" == "$sha" ]] || { rm -f "$tmp"; fail "cloudflared failed its SHA-256 check; not running it."; }
  if [[ $os == darwin ]]; then local x; x="$(mktemp -d)"; tar -xzf "$tmp" -C "$x" && mv "$x/cloudflared" "$exe"; rm -rf "$x" "$tmp"; else mv "$tmp" "$exe"; fi
  chmod 755 "$exe"; echo "$exe"
}

public_base() { if [[ "$TUNNEL" == ngrok && -n "$DOMAIN" ]]; then echo "https://$DOMAIN"; fi; }

# Writes session.json (chmod 600). Args: state public_url tunnel_error
write_session() {
  local key; key="$(head -n1 "$KEYFILE" | tr -d '\r\n')"
  GS_KEY="$key" GS_STATE="$1" GS_PUBLIC="${2:-http://127.0.0.1:$PORT}" GS_ERR="${3:-}" GS_TUNNEL="$TUNNEL" GS_DOMAIN="$DOMAIN" \
  GS_STUDIO="$STUDIO" GS_FILES="$FILES" GS_BLENDER="$BLENDER" GS_PORT="$PORT" GS_FPORT="$FILES_PORT" GS_DROP="${GROK_STUDIO_DROP_DIR_DISPLAY:-$(winpath "$DROP_DIR")}" \
  GS_TOKEN="$TOKEN" GS_OS="$([[ $IS_WSL -eq 1 ]] && echo wsl || echo "$PC_OS")" GS_SUP="$SELF_PID" GS_GW="${GW_PID:-}" GS_FP="${FILES_PID:-}" GS_TP="${TUN_PID:-}" \
  GS_DIR="$BRIDGE_DIR" GS_STOP="$STOP_FILE" GS_LABEL="$LABEL" GS_STARTED="${STARTED_AT:-}" \
  "$NODE_BIN" -e '
    const e = process.env, n = (v) => (v ? Number(v) : null), b = (v) => v === "true";
    const base = e.GS_PUBLIC, o = { state: e.GS_STATE, api_key: e.GS_KEY, public_url: base };
    if (b(e.GS_STUDIO)) o.studio_url = base + "/roblox-studio/mcp";
    if (b(e.GS_FILES)) { o.files_url = base + "/files/mcp"; o.pc_drop_dir = e.GS_DROP; o.pc_http_base = `http://127.0.0.1:${e.GS_FPORT}/${e.GS_TOKEN}`; }
    if (b(e.GS_BLENDER)) o.blender_url = base + "/blender/mcp";
    Object.assign(o, { tunnel: e.GS_TUNNEL, tunnel_stable: e.GS_TUNNEL === "none" || (e.GS_TUNNEL === "ngrok" && !!e.GS_DOMAIN),
      tunnel_error: e.GS_ERR || null, port: n(e.GS_PORT), files_port: n(e.GS_FPORT), pc_os: e.GS_OS,
      supervisor_pid: n(e.GS_SUP), gateway_pid: n(e.GS_GW), files_pid: n(e.GS_FP), tunnel_pid: n(e.GS_TP),
      bridge_dir: e.GS_DIR, stop_file: e.GS_STOP, task_name: e.GS_LABEL, started_at: e.GS_STARTED || null,
      updated_at: new Date().toISOString().replace(/\.\d+Z$/, "Z") });
    const fs = require("fs"), f = process.argv[1];
    fs.writeFileSync(f + ".tmp", JSON.stringify(o, null, 2) + "\n", { mode: 0o600 }); fs.chmodSync(f + ".tmp", 0o600); fs.renameSync(f + ".tmp", f);
  ' "$SESSION"
}

print_session() {
  "$NODE_BIN" -e '
    let s; try { s = JSON.parse(require("fs").readFileSync(process.argv[1], "utf8")); } catch { console.log("STATUS=none"); console.log("ERROR=no session yet: run start or install-service"); process.exit(3); }
    const st = process.argv[2] || s.state;
    if (process.argv[3] === "json") {
      const o = { status: st };
      for (const k of ["api_key", "studio_url", "files_url", "blender_url", "pc_drop_dir", "pc_http_base", "public_url", "tunnel", "tunnel_stable", "tunnel_error", "port", "pc_os"])
        if (s[k] !== undefined && s[k] !== null && s[k] !== "") o[k] = s[k];
      o.session_file = process.argv[1];
      console.log(JSON.stringify(o));
      process.exit(0);
    }
    const out = [["STATUS", st], ["KEY", s.api_key], ["STUDIO_URL", s.studio_url], ["FILES_URL", s.files_url],
      ["BLENDER_URL", s.blender_url], ["PC_DROP_DIR", s.pc_drop_dir], ["PC_HTTP_BASE", s.pc_http_base], ["TUNNEL", s.tunnel],
      ["TUNNEL_STABLE", s.tunnel_stable ? "yes" : "no"], ["TUNNEL_ERROR", s.tunnel_error], ["PC_OS", s.pc_os], ["PORT", s.port],
      ["SESSION_FILE", process.argv[1]]];
    for (const [k, v] of out) if (v !== undefined && v !== null && v !== "") console.log(k + "=" + v);
  ' "$SESSION" "${1:-}" "$([[ $JSON -eq 1 ]] && echo json)"
}

sup_local() { cat "$PID_FILE" 2>/dev/null; }
supervisor_alive() { local p; p="$(sup_local)"; alive "$p" && [[ $WIN -eq 1 || "$(proc_cmd "$p")" == *start-bridge.sh* ]]; }

status_json() {
  local sup=false gw=false files=true tun=false tunnel="${S_TUNNEL:-$TUNNEL}"
  supervisor_alive && sup=true
  if [[ $sup == true ]]; then
    tcp_up "$PORT" && gw=true
    [[ "$FILES" == true ]] && { tcp_up "$FILES_PORT" && files=true || files=false; }
    if [[ "$tunnel" == none ]]; then tun=true; elif alive "$S_TUN"; then tun=true; fi
  else files=false; [[ "$tunnel" == none ]] && tun=true; fi
  local state="$S_STATE"; [[ $sup == true ]] || state=stopped
  local deep=""
  if [[ $DEEP -eq 1 ]]; then
    local inst=false; { [[ $PC_OS == macos && -f "$PLIST" ]] || [[ $PC_OS == linux && -f "$UNIT" ]]; } && inst=true
    deep=",\"service_installed\":$inst,\"public_healthz\":$(http_code "${S_PUBLIC:-http://127.0.0.1:$PORT}/healthz" 5)"
  fi
  local nl='\n  ' end='\n'; [[ $JSON -eq 1 ]] && { nl=''; end=''; }
  printf "{${nl}\"running\": %s,${nl}\"gateway_up\": %s,${nl}\"files_up\": %s,${nl}\"tunnel_up\": %s,${nl}\"url\": \"%s\",${nl}\"tunnel\": \"%s\",${nl}\"tunnel_stable\": %s,${nl}\"tunnel_error\": \"%s\",${nl}\"supervisor_pid\": \"%s\",${nl}\"port\": %s,${nl}\"state\": \"%s\",${nl}\"key_present\": %s%s${end}}\n" \
    "$sup" "$gw" "$files" "$tun" "$S_PUBLIC" "$tunnel" "$S_STABLE" "$S_ERR" "$([[ $sup == true ]] && echo "$S_SUP")" "$PORT" "$state" \
    "$([[ -s "$KEYFILE" ]] && echo true || echo false)" "$deep"
  [[ $sup == true ]] || return 3
  [[ $gw == true && $files == true && $tun == true ]] || return 1
  return 0
}

# ---------------------------------------------------------------------------------------
# run: the supervisor
# ---------------------------------------------------------------------------------------
do_run() {
  resolve_tunnel
  if supervisor_alive && [[ "$(sup_local)" != "$$" ]]; then
    log "Another bridge supervisor already runs (pid $(sup_local))."; exit 0
  fi
  echo $$ > "$PID_FILE"; rm -f "$STOP_FILE"
  for p in "$S_GW" "$S_FILES" "$S_TUN"; do   # leftovers of a supervisor killed without cleanup
    if alive "$p" && [[ "$(proc_cmd "$p")" == *"$BRIDGE_DIR"* || "$(proc_cmd "$p")" == *"127.0.0.1:$PORT"* ]]; then
      log "Stopping a leftover process from the last run (pid $p)."; kill "$p" 2>/dev/null
    fi
  done
  [[ "$STUDIO" == true || "$FILES" == true || "$BLENDER" == true ]] || fail "Nothing to expose."
  install_runtime
  local key; key="$(get_key)"
  local studio_mcp="" studio_args="[]"
  if [[ "$STUDIO" == true ]]; then
    if [[ $PC_OS == linux ]]; then
      [[ -n "$SMCP" ]] || fail "Roblox Studio doesn't run on Linux. Under WSL use --studio-mcp-path /mnt/c/Users/<you>/AppData/Local/Roblox/mcp.bat (the Windows Studio MCP launcher), or --no-studio."
      if [[ "$(printf '%s' "$SMCP" | tr '[:upper:]' '[:lower:]')" == *.bat || "$(printf '%s' "$SMCP" | tr '[:upper:]' '[:lower:]')" == *.cmd ]]; then
        # A Windows launcher: run it through WSL interop (cmd.exe /c <Windows path>).
        studio_mcp="$(command -v cmd.exe || true)"; [[ -n "$studio_mcp" ]] || studio_mcp=/mnt/c/Windows/System32/cmd.exe
        [[ -x "$studio_mcp" ]] || fail "cmd.exe is not reachable, so WSL interop is off: the Windows Studio MCP launcher can't run from here."
        local win_smcp="$SMCP"; [[ "$SMCP" == /* ]] && { have wslpath || fail "wslpath not found: pass the launcher as a Windows path (C:\\...\\mcp.bat)."; win_smcp="$(wslpath -w "$SMCP")"; }
        studio_args="$(GS_P="$win_smcp" "$NODE_BIN" -e 'console.log(JSON.stringify(["/c", process.env.GS_P]))')"
      else
        studio_mcp="$SMCP"; [[ -x "$studio_mcp" ]] || fail "Roblox Studio MCP launcher not executable: $studio_mcp"
      fi
    else
      studio_mcp="${SMCP:-/Applications/RobloxStudio.app/Contents/MacOS/StudioMCP}"
      [[ -x "$studio_mcp" ]] || fail "Roblox Studio MCP not found at $studio_mcp. In Studio: Assistant > ... > Manage MCP Servers > Enable Studio as MCP server."
    fi
  fi
  [[ "$BLENDER" != true ]] || have uvx || fail "Blender is enabled but uv/uvx is missing (https://docs.astral.sh/uv/)."
  [[ "$FILES" != true ]] || mkdir -p "$DROP_DIR"
  if [[ "$TUNNEL" == ngrok ]]; then
    [[ -n "$NGROK_BIN" ]] || fail "ngrok not found (brew install ngrok), or use --tunnel-provider cloudflare."
    [[ -n "${NGROK_AUTHTOKEN:-}" ]] || ngrok_configured || fail "ngrok has no authtoken: set NGROK_AUTHTOKEN and run install-service, or: ngrok config add-authtoken <token>."
  fi
  for p in "$PORT" $([[ "$FILES" == true ]] && echo "$FILES_PORT") $([[ "$TUNNEL" == cloudflare ]] && echo "$METRICS_PORT"); do
    tcp_up "$p" && fail "Port $p is already in use (another bridge?). Run 'status', or pass --port <other>."
  done

  local gw_config="$RUN_DIR/servers.json" esc_node esc_files esc_drop
  GS_STUDIO="$STUDIO" GS_FILES="$FILES" GS_BLENDER="$BLENDER" GS_SMCP="$(winpath "$studio_mcp")" GS_SARGS="$studio_args" GS_NODE="$(winpath "$NODE_BIN")" \
  GS_FS="$(winpath "$FILES_SERVER")" GS_DROP="$(winpath "$DROP_DIR")" GS_BASE="http://127.0.0.1:$FILES_PORT/$TOKEN" GS_PORT="$PORT" \
  "$NODE_BIN" -e '
    const e = process.env, s = {};
    if (e.GS_STUDIO === "true") s["roblox-studio"] = { command: e.GS_SMCP, args: JSON.parse(e.GS_SARGS || "[]") };
    if (e.GS_FILES === "true") s.files = { command: e.GS_NODE, args: [e.GS_FS], env: { GROK_STUDIO_DROP_DIR: e.GS_DROP, GROK_STUDIO_HTTP_BASE: e.GS_BASE } };
    if (e.GS_BLENDER === "true") s.blender = { command: "uvx", args: ["mcp-for-blender"] };
    require("fs").writeFileSync(process.argv[1], JSON.stringify({ host: "127.0.0.1", port: Number(e.GS_PORT), outputTransport: "streamableHttp",
      stateful: true, sessionTimeout: 3600000, healthEndpoint: "/healthz", mcpServers: s }, null, 2));
  ' "$gw_config"
  [[ $UNSAFE_BLENDER -eq 1 ]] || export BLENDER_MCP_SAFE_MODE=1
  export GROK_STUDIO_DROP_DIR="$(winpath "$DROP_DIR")" GROK_STUDIO_HTTP_BASE="http://127.0.0.1:$FILES_PORT/$TOKEN" GROK_STUDIO_HTTP_TOKEN="$TOKEN"
  if [[ $IS_WSL -eq 1 ]] && have wslpath; then export GROK_STUDIO_DROP_DIR_DISPLAY="$(wslpath -w "$DROP_DIR")"; fi

  GW_PID=""; FILES_PID=""; TUN_PID=""; PUBLIC="$(public_base)"; TERR=""
  STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  start_child() {
    case "$1" in
      gateway) "$NODE_BIN" "$(winpath "$GATEWAY_JS")" --config "$(winpath "$gw_config")" --apiKeyFile "$(winpath "$KEYFILE")" \
                 --exitWithProcess "$SELF_PID" --logLevel info >"$LOG_DIR/gateway.log" 2>"$LOG_DIR/gateway.err.log" </dev/null &
               GW_PID=$! ;;
      files)   "$NODE_BIN" "$(winpath "$FILES_SERVER")" --http "$FILES_PORT" --parent-pid "$SELF_PID" \
                 >"$LOG_DIR/files.log" 2>"$LOG_DIR/files.err.log" </dev/null &
               FILES_PID=$! ;;
      tunnel)  if [[ "$TUNNEL" == ngrok ]]; then
                 local a=(http "127.0.0.1:$PORT" --log stdout --log-format json); [[ -n "$DOMAIN" ]] && a+=(--url "https://$DOMAIN")
                 "$NGROK_BIN" "${a[@]}" >"$LOG_DIR/tunnel.log" 2>"$LOG_DIR/tunnel.err.log" </dev/null &
               else
                 local cf; cf="$(get_cloudflared)"
                 "$cf" tunnel --no-autoupdate --metrics "127.0.0.1:$METRICS_PORT" --url "http://127.0.0.1:$PORT" >"$LOG_DIR/tunnel.log" 2>"$LOG_DIR/tunnel.err.log" </dev/null &
               fi
               TUN_PID=$! ;;
    esac
  }
  find_tunnel_url() {
    if [[ "$TUNNEL" == cloudflare ]]; then grep -Eo 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOG_DIR/tunnel.err.log" 2>/dev/null | head -n1
    else grep 'started tunnel' "$LOG_DIR/tunnel.log" 2>/dev/null | grep -o '"url":"https://[^"]*"' | head -n1 | cut -d'"' -f4; fi
  }
  tunnel_up() {
    if [[ "$TUNNEL" == cloudflare ]]; then [[ "$(http_code "http://127.0.0.1:$METRICS_PORT/ready" 2)" == 200 ]]   # never resolve a fresh quick-tunnel name from here
    else [[ -n "$PUBLIC" && "$(http_code "$PUBLIC/healthz" 5)" == 200 ]]; fi
  }
  wait_tunnel() {
    local end=$(( $(date +%s) + $1 )) u
    while [[ $(date +%s) -lt $end ]]; do
      alive "$TUN_PID" || return 1
      if [[ "$TUNNEL" == cloudflare || -z "$DOMAIN" ]]; then u="$(find_tunnel_url)"; [[ -n "$u" && "$u" != "$PUBLIC" ]] && { PUBLIC="$u"; log "Tunnel URL: $u"; }; fi
      [[ -n "$PUBLIC" ]] && tunnel_up && return 0
      sleep 0.5
    done
    return 1
  }
  tunnel_error() { grep -Eho 'ERR_NGROK_[0-9]+[^"]*|failed to[^"]*' "$LOG_DIR/tunnel.log" "$LOG_DIR/tunnel.err.log" 2>/dev/null | tail -n1 | cut -c1-160 | tr '"' "'"; }
  state_now() { if [[ "$TUNNEL" == none || ( -n "$PUBLIC" && -z "$TERR" ) ]]; then echo ready; else echo degraded; fi; }
  kill_children() { for p in "$TUN_PID" "$FILES_PID" "$GW_PID"; do [[ -n "$p" ]] && { pkill -TERM -P "$p" 2>/dev/null; kill -TERM "$p" 2>/dev/null; }; done; }
  cleanup() {
    trap - EXIT INT TERM
    log "Shutting down..."
    kill_children; sleep 0.5
    [[ -f "$SESSION" ]] && write_session stopped "$PUBLIC" ""
    rm -f "$STOP_FILE" "$PID_FILE"
    log "Stopped."
  }
  trap cleanup EXIT; trap 'exit 0' INT TERM

  local t0; t0=$(date +%s)
  log "Starting supergateway on 127.0.0.1:$PORT..."
  start_child gateway
  local i up=0; for i in $(seq 1 100); do sleep 0.1; alive "$GW_PID" || break; tcp_up "$PORT" && { up=1; break; }; done
  [[ $up -eq 1 ]] || fail "supergateway did not start: $(tail -n 5 "$LOG_DIR/gateway.err.log" 2>/dev/null | tr '\n' ' ')"
  [[ "$FILES" == true ]] && start_child files
  if [[ "$TUNNEL" != none ]]; then
    log "Starting the $TUNNEL tunnel..."
    start_child tunnel
    wait_tunnel 30 || { TERR="$(tunnel_error)"; TERR="${TERR:-tunnel not answering}"; log "The tunnel is not answering yet: $TERR"; }
  fi
  write_session "$(state_now)" "$PUBLIC" "$TERR"
  log "Bridge $(state_now) in $(( $(date +%s) - t0 )) s at ${PUBLIC:-http://127.0.0.1:$PORT}"
  [[ $FROM_TASK -eq 1 ]] || { print_session; log "Ctrl+C (or the 'stop' command) stops it."; }
  [[ $FROM_TASK -eq 1 && $PC_OS == linux ]] && have systemd-notify && systemd-notify --ready 2>/dev/null

  local tick=0 gw_miss=0 tun_miss=0 changed v
  fails_gateway=0; fails_files=0; fails_tunnel=0; next_gateway=0; next_files=0; next_tunnel=0
  started_gateway=$(date +%s); started_files=$started_gateway; started_tunnel=$started_gateway
  while true; do
    sleep 1; tick=$((tick + 1)); changed=0
    [[ -e "$STOP_FILE" ]] && { log "Stop requested."; break; }
    for name in gateway files tunnel; do
      local pid=""; case $name in gateway) pid="$GW_PID" ;; files) pid="$FILES_PID" ;; tunnel) pid="$TUN_PID" ;; esac
      [[ -z "$pid" ]] && continue; alive "$pid" && continue
      local now; now=$(date +%s)
      v="next_$name"; [[ $now -lt ${!v} ]] && continue
      v="started_$name"; [[ $(( now - ${!v} )) -gt 120 ]] && printf -v "fails_$name" '%s' 0
      v="fails_$name"; printf -v "fails_$name" '%s' $(( ${!v} + 1 ))
      local delays=(1 2 5 10 30); local idx=$(( ${!v} - 1 )); [[ $idx -gt 4 ]] && idx=4
      printf -v "next_$name" '%s' $(( now + ${delays[$idx]} )); printf -v "started_$name" '%s' "$now"
      log "$name exited; restarting (attempt ${!v})."
      if [[ $name == tunnel && ( "$TUNNEL" == cloudflare || -z "$DOMAIN" ) ]]; then PUBLIC=""; fi
      start_child "$name"
      if [[ $name == tunnel ]]; then if wait_tunnel 30; then TERR=""; else TERR="$(tunnel_error)"; TERR="${TERR:-tunnel not answering}"; fi; fi
      changed=1
    done
    if (( tick % 2 == 0 )); then if tcp_up "$PORT"; then gw_miss=0; else gw_miss=$((gw_miss + 1)); fi; fi
    [[ $gw_miss -ge 3 ]] && { log "Gateway not answering; restarting it."; kill "$GW_PID" 2>/dev/null; gw_miss=0; }
    if [[ "$TUNNEL" != none ]] && (( tick % 30 == 0 )) && alive "$TUN_PID"; then
      if tunnel_up; then [[ $tun_miss -gt 0 || -n "$TERR" ]] && { TERR=""; changed=1; }; tun_miss=0
      else tun_miss=$((tun_miss + 1)); [[ $tun_miss -ge 3 ]] && { log "Tunnel not answering; restarting it."; kill "$TUN_PID" 2>/dev/null; tun_miss=0; }; fi
    fi
    [[ $changed -eq 1 ]] && write_session "$(state_now)" "$PUBLIC" "$TERR"
  done
}

# ---------------------------------------------------------------------------------------
# Service commands
# ---------------------------------------------------------------------------------------
wait_ready() {  # $1 seconds, $2 = epoch seconds the start began
  local end=$(( $(date +%s) + $1 ))
  while [[ $(date +%s) -lt $end ]]; do
    load_state
    if [[ ( "$S_STATE" == ready || "$S_STATE" == degraded ) && -n "$S_UPDATED" ]] && supervisor_alive; then
      local upd; upd="$("$NODE_BIN" -e 'console.log(Math.floor(Date.parse(process.argv[1]) / 1000))' "$S_UPDATED")"
      [[ $upd -ge $(( $2 - 1 )) ]] && return 0
    fi
    sleep 0.3
  done
  return 1
}

do_stop() {
  load_state
  local sp; sp="$(sup_local)"
  if supervisor_alive; then
    touch "$STOP_FILE"
    local i; for i in $(seq 1 40); do alive "$sp" || break; sleep 0.25; done
    if alive "$sp"; then
      log "Supervisor $sp did not stop in 10 s; killing it."
      kill "$sp" 2>/dev/null; sleep 1; kill -9 "$sp" "$S_GW" "$S_FILES" "$S_TUN" 2>/dev/null
    fi
  fi
  rm -f "$STOP_FILE"
}

do_start() {
  rm -f "$STOP_FILE"
  local since; since=$(date +%s)
  if [[ "$PC_OS" == macos && -f "$PLIST" ]]; then
    launchctl kickstart "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || launchctl bootstrap "gui/$(id -u)" "$PLIST" >/dev/null 2>&1
  elif [[ "$PC_OS" == linux && -f "$UNIT" ]]; then
    systemctl --user start "$LABEL.service" >/dev/null 2>&1 || fail "systemctl --user start $LABEL.service failed (journalctl --user -u $LABEL)."
  else
    nohup /bin/bash "$BRIDGE_DIR/start-bridge.sh" run --from-task >/dev/null 2>&1 </dev/null &
  fi
  if ! wait_ready 45 "$since"; then
    out_result error "the bridge did not come up in 45 s. Last log lines: $(tail -n 4 "$LOG_DIR/supervisor.log" 2>/dev/null | tr '\n' '|')"
    exit 1
  fi
  print_session
}

do_install_service() {
  [[ "$PC_OS" == macos || "$PC_OS" == linux ]] || fail "install-service supports macOS (launchd) and Linux (systemd --user). On Windows use start-bridge.ps1."
  if [[ "$PC_OS" == linux ]] && ! systemctl --user show-environment >/dev/null 2>&1; then
    fail "No systemd user manager here (WSL: add '[boot] systemd=true' to /etc/wsl.conf, then 'wsl --shutdown'). Without a service, use: start-bridge.sh start (runs until you log out)."
  fi
  resolve_tunnel
  if [[ "$TUNNEL" == ngrok && -n "$NGROK_BIN" && -n "${NGROK_AUTHTOKEN:-}" ]] && ! ngrok_configured; then
    "$NGROK_BIN" config add-authtoken "$NGROK_AUTHTOKEN" >/dev/null 2>&1 && log "ngrok authtoken saved to the ngrok config."   # never echoed
  fi
  save_config; install_runtime; get_key >/dev/null; do_stop
  local path_dirs; path_dirs="$(dirname "$NODE_BIN")"; [[ -n "$NGROK_BIN" ]] && path_dirs="$path_dirs:$(dirname "$NGROK_BIN")"
  if [[ "$PC_OS" == linux ]]; then install_systemd_unit "$path_dirs"; return; fi
  mkdir -p "$HOME/Library/LaunchAgents"
  cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>$LABEL</string>
  <key>ProgramArguments</key>
  <array><string>/bin/bash</string><string>$BRIDGE_DIR/start-bridge.sh</string><string>run</string><string>--from-task</string></array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>
  <key>ThrottleInterval</key><integer>30</integer>
  <key>EnvironmentVariables</key>
  <dict><key>PATH</key><string>$path_dirs:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string></dict>
  <key>StandardOutPath</key><string>$LOG_DIR/launchd.log</string>
  <key>StandardErrorPath</key><string>$LOG_DIR/launchd.log</string>
</dict>
</plist>
PLIST
  launchctl bootout "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true
  local since; since=$(date +%s)
  launchctl bootstrap "gui/$(id -u)" "$PLIST" || fail "launchctl bootstrap failed for $PLIST"
  log "LaunchAgent $LABEL installed (starts at login; restarted if it crashes)."
  wait_ready 45 "$since" || fail "the bridge did not come up in 45 s (see logs/supervisor.log)."
  print_session
}

# The systemd --user unit (Linux, incl. WSL with systemd). Restart=on-failure: a clean 'stop'
# (exit 0) stays stopped; a crash is restarted.
unit_text() {
  cat <<UNIT
[Unit]
Description=grok-studio bridge (Roblox Studio for the cloud bot team)
After=network-online.target

[Service]
Type=simple
ExecStart=/bin/bash $BRIDGE_DIR/start-bridge.sh run --from-task
Restart=on-failure
RestartSec=10
Environment=PATH=$1:/usr/local/bin:/usr/bin:/bin

[Install]
WantedBy=default.target
UNIT
}
install_systemd_unit() {
  mkdir -p "$UNIT_DIR"
  unit_text "$1" > "$UNIT"
  local since; since=$(date +%s)
  systemctl --user daemon-reload && systemctl --user enable --now "$LABEL.service" >/dev/null 2>&1 || fail "systemctl --user enable --now $LABEL.service failed (journalctl --user -u $LABEL)."
  log "systemd user unit $LABEL.service installed (starts with your user session; restarted if it crashes)."
  if have loginctl && [[ "$(loginctl show-user "${USER:-$(id -un)}" -p Linger --value 2>/dev/null)" != yes ]]; then
    log "Optional: 'loginctl enable-linger ${USER:-$(id -un)}' keeps the bridge running while you're logged out and starts it at boot."
  fi
  wait_ready 45 "$since" || fail "the bridge did not come up in 45 s (see logs/supervisor.log)."
  print_session
}

do_uninstall_service() {
  do_stop
  if [[ "$PC_OS" == macos ]]; then
    launchctl bootout "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true
    [[ -f "$PLIST" ]] && { rm -f "$PLIST"; log "LaunchAgent $LABEL removed."; }
  elif [[ "$PC_OS" == linux && -f "$UNIT" ]]; then
    systemctl --user disable --now "$LABEL.service" >/dev/null 2>&1 || true
    rm -f "$UNIT"; systemctl --user daemon-reload >/dev/null 2>&1 || true
    log "systemd user unit $LABEL.service removed."
  fi
  rm -f "$SESSION"
  [[ $PURGE -eq 1 ]] && rm -rf "$KEYFILE" "$CONFIG" "$LOG_DIR" "$RUN_DIR" "$BIN_DIR" "$BRIDGE_DIR/node_modules"
  out_result uninstalled
}

case "$CMD" in
  run)               do_run ;;
  install-service)   do_install_service ;;
  uninstall-service) do_uninstall_service ;;
  start)             resolve_tunnel; save_config; [[ $ROTATE -eq 1 ]] && get_key >/dev/null; do_start ;;
  stop)              do_stop; out_result stopped ;;
  restart)           resolve_tunnel; save_config; do_stop; [[ $ROTATE -eq 1 ]] && get_key >/dev/null; do_start ;;
  status)            status_json; exit $? ;;
  session)           st=""; supervisor_alive || st=stopped; print_session "$st" ;;
  unit)              unit_text "$(dirname "$NODE_BIN")" ;;   # print the systemd unit (debugging)
esac
