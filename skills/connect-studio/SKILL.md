---
name: connect-studio
description: >-
  Connect Roblox Studio (and optionally Blender) running on the user's local PC
  to this remote GrokBot agent. Runs entirely through ExternalShell: checks
  prerequisites, starts the bridge + ngrok tunnel, parses the connection details,
  and registers the MCP connectors automatically. Use when the user says
  "connect Studio", "reconnect Studio", "connect Roblox", or when the orchestrator's
  preflight detects that Studio is unreachable.
user-invocable: true
argument-hint: "[--no-blender]"
---

# Connect Studio (bridge)

> Called by `/setup-bridge` (Step 2) or by the Lead to reconnect. Pass `--no-blender`:
> Blender runs headless on the cloud computer. After Step 4, also write the parsed JSON to
> `/workspace/grok-studio/.bridge.json` (`chmod 600`) so the team can use the file drop.
> Register ONE `roblox-studio` connector (shared by all Bots), and on reconnect update its
> URL and key instead of adding another.

Connect Roblox Studio (and optionally Blender) on the user's local PC to this
GrokBot agent. After this skill finishes, Studio and Blender tools are available
as custom MCP connectors — no manual copy-paste needed.

**This skill uses ExternalShell (local execution).** The user must have "Execution
on Local Computer" enabled (the default "Ask every time" is fine — they will see
approval prompts).

## Step 0 — Determine the user's OS

Run via ExternalShell:

```
echo %OS%
```

- If the output contains `Windows_NT`, this is **Windows**. Use PowerShell commands
  and `start-bridge.ps1`.
- If the command fails or returns nothing, try `uname -s`. If the output is `Darwin`,
  this is **macOS**. Use bash commands and `start-bridge.sh`.
- If the result is `Linux`, stop: Roblox Studio does not run on Linux. Tell the
  user they need to run this from their Windows or macOS machine.

## Step 1 — Locate the plugin files on the user's PC

The bridge scripts ship with this plugin. When the plugin is installed locally by
GrokBot, its files are in the plugin directory. Check if the bridge script exists
via ExternalShell.

**Windows:**
```
if exist "%USERPROFILE%\.cursor\plugins\*grok-studio*\bridge\start-bridge.ps1" (echo FOUND) else (echo MISSING)
```

**macOS:**
```
ls ~/Library/Application\ Support/Cursor/plugins/*grok-studio*/bridge/start-bridge.sh 2>/dev/null && echo FOUND || echo MISSING
```

If MISSING, the plugin may not be installed locally, or GrokBot's local execution
does not have access to the plugin directory. Fall back: ask the user to clone the
repo manually:

```
git clone https://github.com/brain-xiang/grok-studio.git ~/grok-studio
```

Then use `~/grok-studio/bridge/` as the bridge path.

Record the bridge directory path as `$BRIDGE_DIR` for the steps below.

## Step 2 — Check prerequisites

Run each check via ExternalShell. For any failure, tell the user what to install
and **wait for them to confirm** before re-checking. Do not proceed with missing
prerequisites.

### 2a. Node.js / npx

**Windows:** `where npx`
**macOS:** `which npx`

If missing: "Install Node.js LTS from https://nodejs.org, then reopen your terminal."

### 2b. ngrok

**Windows:** `where ngrok`
**macOS:** `which ngrok`

If missing: "Install ngrok from https://ngrok.com/download and run
`ngrok config add-authtoken <your-token>` once."

If present, check that it has an authtoken:
**Both:** `ngrok config check`
Look for "Valid configuration file" in the output. If it says the config is missing
or invalid, tell the user to run `ngrok config add-authtoken <token>`.

### 2c. Roblox Studio MCP enabled

**Windows:** `if exist "%LOCALAPPDATA%\Roblox\mcp.bat" (echo OK) else (echo MISSING)`
**macOS:** `test -x /Applications/RobloxStudio.app/Contents/MacOS/StudioMCP && echo OK || echo MISSING`

If MISSING: "Open Roblox Studio, go to Assistant settings, and turn on 'Enable
Studio as MCP server'. Then check again."

### 2d. Roblox Studio running (optional check)

**Windows:** `tasklist /fi "imagename eq RobloxStudioBeta.exe" /nh`
**macOS:** `pgrep -x RobloxStudio`

If not running: "Please open Roblox Studio with a place loaded before continuing."

### 2e. uv/uvx (only if Blender is wanted)

If the user did NOT say `--no-blender`:

**Windows:** `where uvx`
**macOS:** `which uvx`

If missing: "Install uv from https://docs.astral.sh/uv/getting-started/installation/,
then run `uvx mcp-for-blender setup`."

If the user doesn't need Blender, note that we will add `--no-blender` to the
bridge command.

## Step 3 — Start the bridge

All prerequisites passed. Start the bridge in the background via ExternalShell.
The `--json-output` flag makes it emit a single JSON line with the connection
details that we can parse.

**Windows:**
```
powershell -ExecutionPolicy Bypass -File "$BRIDGE_DIR\start-bridge.ps1" -Tunnel -Yes -JsonOutput [-NoBlender]
```

**macOS:**
```
"$BRIDGE_DIR/start-bridge.sh" --tunnel --yes --json-output [--no-blender]
```

**IMPORTANT:** This command runs in the foreground and stays alive (the bridge
process). Use `AwaitExternalShell` to wait for the first line of output (the JSON),
then leave the process running. The user will Ctrl+C it when they are done.

## Step 4 — Parse the JSON output

The bridge prints exactly one JSON line to stdout before blocking:

```json
{"studio_url":"https://abc.ngrok-free.app/roblox-studio/mcp","blender_url":"https://abc.ngrok-free.app/blender/mcp","api_key":"...","port":8765}
```

Parse it. Extract:
- `studio_url` — the public HTTPS URL for Studio MCP (present unless `--no-blender`)
- `blender_url` — the public HTTPS URL for Blender MCP (absent if `--no-blender`)
- `api_key` — the ephemeral bearer token

If parsing fails or the bridge exits early, read the last lines of output for
error messages and report them to the user.

## Step 5 — Register the MCP connectors

Tell yourself (the bot) to add custom MCP connectors using the parsed details.
Use a message like:

> Add a custom MCP server called roblox-studio at <studio_url> with
> Authorization header: Bearer <api_key>

If Blender was included:

> Add a custom MCP server called blender at <blender_url> with
> Authorization header: Bearer <api_key>

Wait for confirmation that the connectors were registered.

## Step 6 — Verify

Call `list_roblox_studios` through the newly registered roblox-studio connector.

- **Success (returns studio instances):** Tell the user which Studio instances are
  connected, and that they are ready to go. Suggest they try the `/grok-studio`
  skill or just ask to build something.
- **Empty list:** "Studio is connected but no places are open. Please open a place
  in Roblox Studio."
- **Failure / timeout:** "The connector was registered but Studio didn't respond.
  Check that Studio is open with MCP enabled, and that the bridge terminal on your
  PC shows 'Gateway is up'."

## Step 7 — Tell the user how to stop

> Your bridge is running in a terminal on your local PC. When you are done with
> this build session:
> 1. Press Ctrl+C in that terminal to stop the bridge and tunnel.
> 2. The API key is now useless — no one can connect with it.
> 3. The connectors in this bot will stop working. You can remove them or leave
>    them (they will just fail until you run /setup-bridge again (it reconnects)).

## Error handling

- If ExternalShell is not available or the user has set "Never allow" for local
  execution, explain that this skill needs local execution permission. Point them
  to Settings > General > Bot > Execution on Local Computer > "Ask every time".
- If any prerequisite install fails after two attempts, stop and give the user
  the manual instructions from `bridge/README.md` as a fallback.
- If the bridge script itself fails, show the error output and suggest the user
  run it manually in their own terminal for easier debugging:
  - Windows: `powershell -ExecutionPolicy Bypass -File .\bridge\start-bridge.ps1 -Tunnel`
  - macOS: `./bridge/start-bridge.sh --tunnel`
  Then they can copy-paste the URLs and key manually.
