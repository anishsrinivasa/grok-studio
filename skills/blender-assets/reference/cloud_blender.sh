#!/usr/bin/env bash
# cloud_blender.sh - headless Blender for the grok-studio bots' cloud computer (Linux x64).
#
#   cloud_blender.sh install [version]   download the pinned official build, verify sha256, unpack
#   cloud_blender.sh probe               find a render engine that works headless (writes engine file)
#   cloud_blender.sh run <script.py> [-- args...]
#                                        blender -b --factory-startup, this folder on sys.path,
#                                        exit code 1 if the script raises
#   cloud_blender.sh version             print the installed version and binary path
#   cloud_blender.sh path                print the blender binary path (nothing else)
#
# Installs to $GS_ROOT/.tools/blender/<version>/ (GS_ROOT defaults to /workspace/grok-studio,
# which is durable and shared by every Bot). Safe to run from several Bots at once: the install
# takes a mkdir lock and is idempotent.
#
# Local use (any OS with bash, e.g. Git Bash on Windows): set BLENDER_BIN to an existing Blender
# binary and use `probe` / `run` / `version` only.
#
# Versions: 5.2.2 (default; the version the reference scripts were tested with) and 5.0.1
# (verified on the Grok Bot cloud computer). Checksums are the official ones published at
# https://download.blender.org/release/Blender<major.minor>/blender-<version>.sha256

set -euo pipefail

GS_ROOT="${GS_ROOT:-/workspace/grok-studio}"
TOOLS="$GS_ROOT/.tools/blender"
DEFAULT_VERSION="5.2.2"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

die()  { printf '[cloud_blender] ERROR: %s\n' "$*" >&2; exit 1; }
info() { printf '[cloud_blender] %s\n' "$*" >&2; }

sha_for() {
  case "$1" in
    5.2.2) echo "84098912789dc450e95697c4184fb8a90acbe5111c2ba4aede3fecb57806a168" ;;
    5.0.1) echo "8019580ee1b7262e505f4196a00237ccf743c88d205b38d34201510676e60b09" ;;
    *) return 1 ;;
  esac
}

version_wanted() { echo "${BLENDER_VERSION:-$DEFAULT_VERSION}"; }

# Paths handed to Blender's Python must be native (Git Bash on Windows: C:/...).
native_path() { if command -v cygpath >/dev/null 2>&1; then cygpath -m "$1"; else printf '%s' "$1"; fi; }

# The binary to use: BLENDER_BIN (local override) or the newest-pinned install.
blender_bin() {
  if [[ -n "${BLENDER_BIN:-}" ]]; then
    [[ -x "$BLENDER_BIN" || -f "$BLENDER_BIN" ]] || die "BLENDER_BIN does not exist: $BLENDER_BIN"
    echo "$BLENDER_BIN"; return
  fi
  local v; v="$(version_wanted)"
  local bin="$TOOLS/$v/blender"
  [[ -x "$bin" ]] || die "Blender $v is not installed. Run: $0 install"
  echo "$bin"
}

# Where `probe` records the engine. Next to the cloud install; for a local BLENDER_BIN
# (often a read-only Program Files folder) in the temp dir instead.
engine_file() {
  if [[ -n "${BLENDER_BIN:-}" ]]; then
    echo "${TMPDIR:-/tmp}/gs-render-engine-$(printf '%s' "$BLENDER_BIN" | cksum | cut -d' ' -f1)"
  else
    echo "$(dirname "$(blender_bin)")/.render_engine"
  fi
}

sha256_of() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d' ' -f1
  elif command -v shasum >/dev/null 2>&1; then shasum -a 256 "$1" | cut -d' ' -f1
  else die "need sha256sum or shasum to verify the download"; fi
}

download() {  # url dest
  if command -v curl >/dev/null 2>&1; then
    curl -fsSL --retry 3 --retry-delay 2 -o "$2" "$1"
  elif command -v wget >/dev/null 2>&1; then
    wget -q -O "$2" "$1"
  else die "need curl or wget"; fi
}

cmd_install() {
  local v="${1:-$(version_wanted)}"
  local sha; sha="$(sha_for "$v")" || die "no pinned checksum for Blender $v (pinned: 5.2.2, 5.0.1)"
  local dest="$TOOLS/$v"

  if [[ -x "$dest/blender" ]] && "$dest/blender" --version >/dev/null 2>&1; then
    info "Blender $v already installed at $dest"; echo "$dest/blender"; return
  fi

  [[ "$(uname -s)" == "Linux" ]] || die "install is for the Linux cloud computer. Locally, set BLENDER_BIN to your Blender instead."
  case "$(uname -m)" in
    x86_64|amd64) ;;
    *) die "this computer is $(uname -m); Blender publishes official Linux builds for x86_64 only." ;;
  esac

  mkdir -p "$TOOLS"
  # ~383 MB download + ~1.2 GB unpacked; ask for 2 GB to be safe.
  local free_kb; free_kb="$(df -Pk "$TOOLS" | awk 'NR==2 {print $4}')"
  if [[ -n "$free_kb" && "$free_kb" -lt 2097152 ]]; then
    die "not enough disk space in $TOOLS ($((free_kb / 1024)) MB free, need ~2048 MB)"
  fi

  # One installer at a time (several Bots may call install at once).
  local lock="$TOOLS/.install.lock"
  local waited=0
  until mkdir "$lock" 2>/dev/null; do
    if (( waited >= 900 )); then die "another install has held $lock for 15 min; remove it if it is stale"; fi
    info "another install is running; waiting..."; sleep 10; waited=$((waited + 10))
  done
  trap 'rm -rf "$lock" "$TOOLS/.dl-$v" "$TOOLS/.unpack-$v"' EXIT

  if [[ -x "$dest/blender" ]] && "$dest/blender" --version >/dev/null 2>&1; then
    info "Blender $v was installed by another Bot meanwhile"; echo "$dest/blender"; return
  fi

  local mm="${v%.*}"
  local name="blender-$v-linux-x64"
  local url="https://download.blender.org/release/Blender$mm/$name.tar.xz"
  mkdir -p "$TOOLS/.dl-$v"
  local tarball="$TOOLS/.dl-$v/$name.tar.xz"
  info "downloading $url (~380 MB)"
  download "$url" "$tarball"

  local got; got="$(sha256_of "$tarball")"
  [[ "$got" == "$sha" ]] || die "sha256 mismatch for $name.tar.xz (expected $sha, got $got). Not installing."
  info "sha256 OK"

  rm -rf "$TOOLS/.unpack-$v"; mkdir -p "$TOOLS/.unpack-$v"
  tar -xJf "$tarball" -C "$TOOLS/.unpack-$v"
  rm -rf "$dest"
  mv "$TOOLS/.unpack-$v/$name" "$dest"

  if ! "$dest/blender" --version >/dev/null 2>&1; then
    info "Blender is unpacked but does not start. Missing system libraries:"
    ldd "$dest/blender" 2>/dev/null | grep 'not found' >&2 || true
    die "install the missing libraries (Debian/Ubuntu: apt-get install -y libx11-6 libxext6 libxi6 libxxf86vm1 libxfixes3 libxrender1 libxkbcommon0 libsm6 libice6 libgl1 libegl1 - libgl1/libegl1 also give Workbench a software renderer), then re-run install"
  fi
  info "installed Blender $v at $dest"
  echo "$dest/blender"
}

# Render a tiny scene with each engine in its own process (a GPU-context failure can crash
# Blender outright, so never probe inside the job itself). First engine that writes a PNG wins.
cmd_probe() {
  local bin; bin="$(blender_bin)"
  local tmp; tmp="$(mktemp -d "${TMPDIR:-/tmp}/gs-probe.XXXXXX")"
  local out_file; out_file="$(engine_file)"
  local engine
  for engine in BLENDER_WORKBENCH BLENDER_EEVEE BLENDER_EEVEE_NEXT CYCLES; do
    local png; png="$(native_path "$tmp/$engine.png")"
    local expr="import bpy
s = bpy.context.scene
try:
    s.render.engine = '$engine'
except TypeError:
    raise SystemExit(3)
if s.render.engine == 'CYCLES':
    s.cycles.device = 'CPU'; s.cycles.samples = 1
s.render.resolution_x = s.render.resolution_y = 64
s.render.filepath = r'$png'
bpy.ops.render.render(write_still=True)"
    if timeout 300 "$bin" -b --factory-startup --python-exit-code 1 --python-expr "$expr" >"$tmp/$engine.log" 2>&1 && [[ -s "$png" ]]; then
      echo "$engine" > "$out_file"
      info "headless render engine: $engine"
      rm -rf "$tmp"
      echo "$engine"; return
    fi
    info "$engine: no image (see $tmp/$engine.log)"
  done
  die "no render engine could render headless; logs in $tmp"
}

cmd_run() {
  [[ $# -ge 1 ]] || die "usage: $0 run <script.py> [-- args...]"
  local script="$1"; shift
  [[ -f "$script" ]] || die "script not found: $script"
  if [[ "${1:-}" == "--" ]]; then shift; fi
  local bin; bin="$(blender_bin)"
  local ef; ef="$(engine_file)"
  if [[ -z "${GS_RENDER_ENGINE:-}" && -s "$ef" ]]; then
    GS_RENDER_ENGINE="$(cat "$ef")"; export GS_RENDER_ENGINE
  fi
  # Blender ignores PYTHONPATH by default, so put this folder (asset_harness, roblox_export)
  # on sys.path explicitly before the job runs. Paths go in through the environment.
  GS_REFERENCE_DIR="$(native_path "$HERE")"; export GS_REFERENCE_DIR
  exec "$bin" -b --factory-startup --python-exit-code 1 \
    --python-expr "import os, sys; sys.path.insert(0, os.environ['GS_REFERENCE_DIR'])" \
    --python "$script" -- "$@"
}

cmd_version() {
  local bin; bin="$(blender_bin)"
  "$bin" --version 2>/dev/null | head -n 1
  echo "$bin"
  local ef; ef="$(engine_file)"
  [[ -s "$ef" ]] && echo "render engine: $(cat "$ef")" || echo "render engine: not probed (run: $0 probe)"
}

case "${1:-}" in
  install) shift; cmd_install "$@" ;;
  probe)   shift; cmd_probe ;;
  run)     shift; cmd_run "$@" ;;
  version) shift; cmd_version ;;
  path)    shift; blender_bin ;;
  *) sed -n '2,13p' "$0"; exit 2 ;;
esac
