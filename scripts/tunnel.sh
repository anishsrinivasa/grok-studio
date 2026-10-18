#!/usr/bin/env bash
# Start the ngrok tunnel for grok-studio.
# Uses both the global ngrok config (for authtoken) and the project ngrok.yml.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Detect ngrok's global config path
NGROK_GLOBAL=""
for candidate in \
    "${HOME}/.config/ngrok/ngrok.yml" \
    "${HOME}/snap/ngrok/current/.config/ngrok/ngrok.yml" \
    "$(ngrok config check 2>/dev/null | grep -oP '(?<=at ).*')" \
; do
    if [ -f "$candidate" ]; then
        NGROK_GLOBAL="$candidate"
        break
    fi
done

if [ -z "$NGROK_GLOBAL" ]; then
    echo "ERROR: ngrok global config not found."
    echo "Run:  ngrok config add-authtoken <YOUR_TOKEN>"
    exit 1
fi

echo "Using ngrok config: $NGROK_GLOBAL"
exec ngrok start \
    --config "$NGROK_GLOBAL" \
    --config "$PROJECT_DIR/ngrok.yml" \
    roblox
