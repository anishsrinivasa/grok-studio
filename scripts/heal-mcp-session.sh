#!/usr/bin/env bash
set -euo pipefail

# heal-mcp-session.sh
# Restarts ONLY the calling bot's MCP sessions after a tunnel blip or stale session error.
# Never touches other bots' processes. Kills only mcp-remote children of this bot's
# exec-daemon parent.

echo "[Heal] Restarting MCP sessions for this bot only..."

# Find the exec-daemon parent of the current shell (typically ppid of the task runner)
EXEC_DAEMON_PID=""
CURRENT_PID=$$

# Walk up the process tree to find exec-daemon
while [ "$CURRENT_PID" != "1" ]; do
    PARENT_COMM=$(ps -o comm= -p "$CURRENT_PID" 2>/dev/null || echo "")
    if [[ "$PARENT_COMM" == "exec-daemon" ]]; then
        EXEC_DAEMON_PID="$CURRENT_PID"
        break
    fi
    CURRENT_PID=$(ps -o ppid= -p "$CURRENT_PID" 2>/dev/null | tr -d ' ' || echo "1")
done

if [ -z "$EXEC_DAEMON_PID" ]; then
    # Never fall back to killing every mcp-remote: the computer is shared by all Bots.
    echo "[Heal] Could not find this bot's exec-daemon parent; left every MCP session alone."
    echo "[Heal] Continue with the next Heal step (bridge-check, then restart the bridge)."
    exit 2
fi

echo "[Heal] Found exec-daemon PID: $EXEC_DAEMON_PID"

# Find all mcp-remote children of this exec-daemon
MCP_PIDS=$(pgrep -P "$EXEC_DAEMON_PID" -f mcp-remote || true)

if [ -z "$MCP_PIDS" ]; then
    echo "[Heal] No MCP sessions found for this bot. Nothing to restart."
    exit 0
fi

echo "[Heal] Killing MCP processes: $MCP_PIDS"
echo "$MCP_PIDS" | xargs -r kill -TERM 2>/dev/null || true

# Wait for clean shutdown
sleep 2

# Force-kill any stragglers
REMAINING=$(pgrep -P "$EXEC_DAEMON_PID" -f mcp-remote || true)
if [ -n "$REMAINING" ]; then
    echo "[Heal] Force-killing remaining: $REMAINING"
    echo "$REMAINING" | xargs -r kill -KILL 2>/dev/null || true
fi

echo "[Heal] ✓ MCP sessions restarted. Next tool call will spawn fresh connections."
