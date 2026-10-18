---
name: connect-studio
description: >-
  Connects Roblox Studio on the user's PC to the bot team, keeps it connected, and
  disconnects it. Checks the bridge from the cloud first (no PC command), and only if
  that fails runs commands on the user's PC (local execution, the user approves):
  status, then start or restart, or a first-time install of the bridge as a background
  service (Windows Scheduled Task / macOS LaunchAgent) with a stable key and a static
  ngrok domain. Then it saves the session to /workspace/grok-studio/.bridge.json,
  registers or updates the one shared roblox-studio connector in place, and verifies
  with list_roblox_studios. Use when Studio tools fail, when the user says "connect
  Studio", "reconnect", "disconnect Studio" or "stop the bridge", and from /setup-bridge.
user-invocable: true
argument-hint: "[disconnect | remove | status] [--cloudflare] [--blender]"
---

# Connect Studio

Roblox Studio only runs on Windows and macOS, so it stays on the user's PC. The **bridge**
(`bridge/start-bridge.ps1` on Windows, `bridge/start-bridge.sh` on macOS) runs there as a
background service. It exposes Studio over one HTTPS URL (a static ngrok domain) with one
API key, plus a file drop for `scripts/send-to-pc.py`. It restarts its own parts when they
die and starts again after a reboot. The key and URL don't change, so the connector is
registered once.

**Who runs this:** whichever Bot is running `/setup-bridge` (in the user's chat, where the
user approves each PC command), the **Lead** to repair or reconnect, or any Bot when the
user says "disconnect Studio". Specialists only run the cloud check (Step 0). If it fails,
they tell the Lead instead of touching the PC. Never show the API key to the user and
never put it in a message to another Bot.

**PC commands** go through local execution: commands run on the user's PC once the user
approves them (Grok Bot: Settings > General > Bot > Execution on Local Computer, "Ask every
time" is fine). If local execution is off, use **Manual fallback**.

Paths:
- `<plugin>` = `/workspace/grok-studio/plugin` on the cloud computer (`/setup-bridge` puts
  the plugin there).
- `<home>` = the bridge's home on the PC: `%USERPROFILE%\grok-studio` (Windows) or
  `~/grok-studio` (macOS).
- `<bridge>` = `<home>\bridge`.
- `BR` = the bridge command:
  - Windows: `powershell -NoProfile -ExecutionPolicy Bypass -File "%USERPROFILE%\grok-studio\bridge\start-bridge.ps1"`
  - macOS: `bash ~/grok-studio/bridge/start-bridge.sh`

Arguments: `disconnect` -> **Disconnect**. `remove` -> **Remove**. `status` -> Step 0 and
Step 1 only (report, change nothing). `--cloudflare` -> use the no-account fallback tunnel.
`--blender` -> also expose a Blender running on the PC (see **Blender on the PC**).

## Step 0 - Cloud check (no PC command; every Bot, every task)

```bash
python3 <plugin>/scripts/bridge-check.py --studio
```

It prints one JSON line, and transient failures are already retried with backoff.

- `"bridge": "up", "studio": "ok"`: connected. Use `places` to confirm the right place is
  open, and stop here.
- `"studio": "no-places"`: the bridge works but no place is open. Ask the user to open it
  in Studio; don't touch the bridge.
- `"bridge": "down"` or `"unknown"`, or `"studio": "error"`: go to Step 1. Specialists
  stop here and message the Lead with the `error` and `fix` fields.

## Heal (any Bot, when Step 0 fails)

Any Bot may run this one repair. Everything else on the PC stays with the Lead.

1. Re-run Step 0 once: `python3 <plugin>/scripts/bridge-check.py --studio`.
2. Still `down`: restart the bridge on the PC. This is local execution, so the user approves
   it like any PC command.
   - Windows:
     `powershell -NoProfile -ExecutionPolicy Bypass -File "%USERPROFILE%\grok-studio\bridge\start-bridge.ps1" restart -JsonOutput`
   - macOS / Linux (WSL):
     `bash ~/grok-studio/bridge/start-bridge.sh restart --json-output`
   - It prints ONE JSON line: the session, with the same fields as `.bridge.json`. With
     `"status": "error"` it has an `error` field instead.
3. If that line's `api_key` or `studio_url` differs from `/workspace/grok-studio/.bridge.json`
   (key rotated, or a Cloudflare URL), write the line to `.bridge.json` (mode 600) and update
   the `roblox-studio` connector in place (Step 3). With ngrok's static domain, normally
   nothing changes.
4. Re-check: `python3 <plugin>/scripts/bridge-check.py --studio --wait 30`.
5. Still failing: stop. Message the Lead with bridge-check's `error` and `fix`, plus the
   `error` from step 2. Don't retry in a loop.

## Step 1 - Status on the PC

Find the OS once: run `echo %OS%` (`Windows_NT` = Windows), else `uname -s` (`Darwin` =
macOS). `Linux` means WSL on a Windows PC: either use the Windows side (preferred), or run
`start-bridge.sh` inside WSL. There, the bridge reaches Studio through WSL interop: add
`--studio-mcp-path /mnt/c/Users/<you>/AppData/Local/Roblox/mcp.bat`, and the service is a
`systemd --user` unit (needs `[boot] systemd=true` in `/etc/wsl.conf`; `loginctl
enable-linger` is optional). Studio can't run on plain Linux. Then run `BR status`.
`-JsonOutput` (macOS/Linux `--json-output`) on any command prints one compact JSON line
instead. It's cheap (about a second) and prints JSON:
`running, gateway_up, files_up, tunnel_up, url, tunnel, tunnel_stable, tunnel_error,
state, key_present`. Exit code 0 = healthy, 1 = degraded, 3 = not running.

| Result | Do |
|---|---|
| the command fails: file not found | the bridge isn't installed: **Install** |
| `running: false` | `BR start`, then Step 2 |
| running, but `gateway_up` or `tunnel_up` is false, or `state: degraded` | read `tunnel_error` (see **Fixes**), then `BR restart`, then Step 2 |
| everything true, but Step 0 failed | the URL/key in `.bridge.json` are stale: `BR session`, then Step 2 |

`start` and `restart` take about 10 seconds and print the session (Step 2).

## Step 2 - Save the session (cloud)

`BR session` (and `install-service`, `start`, `restart`) print one field per line:
```
STATUS=ready
KEY=<43 chars>
STUDIO_URL=https://<domain>/roblox-studio/mcp
FILES_URL=https://<domain>/files/mcp
PC_DROP_DIR=...
PC_HTTP_BASE=http://127.0.0.1:8766/<token>
TUNNEL=ngrok
TUNNEL_STABLE=yes
PC_OS=windows
PORT=8765
SESSION_FILE=...\bridge\session.json      <- always the last line
```
Wait for the `SESSION_FILE=` line. Strip whitespace from each value, because a terminal
may wrap long lines. `STATUS=error` comes with an `ERROR=` line that says what's wrong (see
**Fixes**).

Write the fields to `/workspace/grok-studio/.bridge.json`, mode 600:
```bash
mkdir -p /workspace/grok-studio && umask 077 && cat > /workspace/grok-studio/.bridge.json <<'EOF'
{"api_key": "<KEY>", "studio_url": "<STUDIO_URL>", "files_url": "<FILES_URL>",
 "pc_drop_dir": "<PC_DROP_DIR>", "pc_http_base": "<PC_HTTP_BASE>", "tunnel": "<TUNNEL>",
 "tunnel_stable": <true|false>, "pc_os": "<PC_OS>"}
EOF
```
(`send-to-pc.py` and `bridge-check.py` also accept the raw `KEY=...` lines as the file.)

## Step 3 - The connector (one, shared by every Bot)

Connectors are account-wide: every Bot uses the same `roblox-studio` connector.

- **None yet:** add a custom MCP server named `roblox-studio`, URL = `STUDIO_URL`,
  Streamable HTTP, header `Authorization: Bearer <KEY>`.
- **It exists:** compare its URL and key with the session. Same: leave it alone (the
  normal case with a static domain). Different (key rotated, domain changed, or Cloudflare
  gave a new URL): **update it in place** under the same name. If the platform can't
  update one, remove it and add it again with the same name. Never add a second one.
- `--blender`: the same for a `blender` connector with `BLENDER_URL`.
- The file drop needs no connector.

## Step 4 - Verify

1. Call `list_roblox_studios` through `roblox-studio`. On an error such as "fetch failed",
   a timeout or HTTP 502/503/530, retry after 2 s, 5 s, then 10 s; tunnels blip. Then:
   - places listed: if more than one, ask the user which place to build in. The Lead stores
     its id as `build.studioId`.
   - empty list: "Studio is connected, but no place is open. Open it, then tell me."
   - still failing after the retries: run Step 1 again and use **Fixes**.
2. `python3 <plugin>/scripts/bridge-check.py --studio` should say `up` / `ok`.
3. Tell the user in plain words:
   - which place is connected, and whether the URL is stable;
   - that the bridge now runs in the background, starts with their PC, and lets this
     bot team run code in their open Studio places;
   - how to stop it: say **"disconnect Studio"**.

## Install (first time on this PC)

Tell the user what you're about to install, and wait for their go-ahead, before each
install command.

1. **Node.js**: Windows `where node`, macOS `command -v node`. Missing: Windows
   `winget install -e --id OpenJS.NodeJS.LTS --accept-package-agreements --accept-source-agreements`,
   macOS `brew install node` (or https://nodejs.org). Then use a new shell, since PATH
   changed.
2. **Studio MCP**: Windows `if exist "%LOCALAPPDATA%\Roblox\mcp.bat" (echo OK)`, macOS
   `test -x /Applications/RobloxStudio.app/Contents/MacOS/StudioMCP && echo OK`. Missing:
   the user opens Studio > Assistant > ... > Manage MCP Servers > turns on **Enable Studio as
   MCP server**.
3. **Bridge files** go into `<home>`, never into an editor's plugin folder.
   - `<ref>` = the tag `v<version>` (version from `<plugin>/.cursor-plugin/plugin.json`)
     if it exists (`git ls-remote --tags https://github.com/anishsrinivasa/grok-studio.git
     v<version>` prints a line), else the branch `multi-bot-team`, else `main`. If
     `/setup-bridge` was told to use a branch, use that one.
   - If git exists (`git --version`) and `<home>` doesn't:
     `git clone --depth 1 --branch <ref> https://github.com/anishsrinivasa/grok-studio.git "<home>"`.
   - If `<home>` is already a clone (`git -C "<home>" status --porcelain`): with no local
     changes, run `git -C "<home>" fetch --depth 1 origin <ref>` and then
     `git -C "<home>" checkout --detach FETCH_HEAD`. With local changes, leave it alone
     and tell the user.
   - No git, Windows: download
     `https://codeload.github.com/anishsrinivasa/grok-studio/zip/refs/tags/<ref>` (a branch:
     `refs/heads/<ref>`) with `curl.exe -fsSL -o "%TEMP%\gs.zip" <url>`. Run
     `Expand-Archive -Force "%TEMP%\gs.zip" "%TEMP%\gs"`, then copy the extracted folder's
     contents into `<home>`.
   - No git, macOS: `curl -fsSL <same url, tar.gz instead of zip> | tar -xz -C /tmp`, then
     copy into `<home>`.
4. **Verify the files before running anything.** Hash with line endings normalized (`.ps1`
   files check out with CRLF, the plugin may have LF).
   - On the PC, Windows:
     ```powershell
     foreach ($f in 'start-bridge.ps1','start-bridge.sh','files-server.mjs','package.json','package-lock.json') {
       $t = [IO.File]::ReadAllText("$env:USERPROFILE\grok-studio\bridge\$f").Replace("`r`n", "`n")
       $h = [Security.Cryptography.SHA256]::Create().ComputeHash([Text.Encoding]::UTF8.GetBytes($t))
       (($h | ForEach-Object { $_.ToString('x2') }) -join '') + "  $f" }
     ```
   - On the PC, macOS:
     `cd ~/grok-studio/bridge && for f in start-bridge.ps1 start-bridge.sh files-server.mjs package.json package-lock.json; do echo "$(tr -d '\r' < $f | shasum -a 256 | cut -c1-64)  $f"; done`
   - On the cloud computer, the same files from `<plugin>/bridge`:
     `for f in ...; do echo "$(tr -d '\r' < <plugin>/bridge/$f | sha256sum | cut -c1-64)  $f"; done`
   - Every hash must match. If any differs, don't run anything: tell the user.
5. **The tunnel** (default: ngrok with the user's static domain, so the URL never changes):
   - ngrok installed? Windows `where ngrok`, macOS `command -v ngrok`. If not:
     `winget install -e --id ngrok.ngrok` / `brew install ngrok`.
   - **Static domain:** ask the user to paste it. A free ngrok account includes one, shown
     at dashboard.ngrok.com > Domains, e.g. `name.ngrok-free.dev`. It isn't secret.
   - **Authtoken:** the Grok Bot secret `NGROK_AUTHTOKEN`. Ask the user to add it if it's
     missing (dashboard.ngrok.com > Your Authtoken). Pass it only in the install command's
     environment. The bridge saves it to ngrok's own config once, and only if ngrok has no
     token yet. Never echo it.
   - **No ngrok account and the user doesn't want one:** use `-TunnelProvider cloudflare`
     (macOS `--tunnel-provider cloudflare`). It needs no account, but the URL changes
     every time the tunnel restarts, so Step 3 updates the connector each time. Say so.
6. **Install the service** (starts at logon, restarts its parts, keeps the key):
   - Windows:
     `set NGROK_AUTHTOKEN=<secret>&& BR install-service -NgrokDomain <domain>`
     (in PowerShell: `$env:NGROK_AUTHTOKEN='<secret>'; ...`). This creates the per-user
     Scheduled Task `\GrokStudio\GrokStudioBridge` and needs no admin rights.
   - macOS:
     `NGROK_AUTHTOKEN=<secret> BR install-service --ngrok-domain <domain>`. This creates the
     LaunchAgent `com.grokstudio.bridge`.
   - The first run installs supergateway once with npm (about 15 s). Later starts take
     about 10 s. Then continue at **Step 2**.

## Disconnect (stop for now)

`BR stop` prints `STATUS=stopped`. The bridge stays stopped until `BR start` or the next
reboot/login. The key, URL, connector and `.bridge.json` stay valid for the next start.
If you are the Lead, tell the team `[GS] STUDIO OFFLINE` (no Studio writes until
`[GS] STUDIO ONLINE`).

## Remove (uninstall)

`BR uninstall-service` stops the bridge and removes the Scheduled Task / LaunchAgent.
`-Purge` (macOS `--purge`) also deletes the key, config, logs and installed packages. Then
run `rm -f /workspace/grok-studio/.bridge.json` on the cloud computer, and ask the user
whether to remove the `roblox-studio` connector too.

## Fixes

| Seen | Fix |
|---|---|
| `ERROR=Port 8765 is already in use` | another bridge or program holds the port: `BR status`; if it's an old bridge, `BR stop`; otherwise `BR restart -Port 8775` (macOS `--port 8775`) and update the connector |
| `tunnel_error` with `ERR_NGROK_108` | a free ngrok account allows one agent at a time: close the other ngrok (another PC or terminal), then `BR restart` |
| `ERR_NGROK_4018` or "authtoken" | ngrok has no valid token: add or fix the `NGROK_AUTHTOKEN` secret, re-run Install step 6 |
| other `ERR_NGROK_<n>` (e.g. the domain belongs to another account) | look it up at https://ngrok.com/docs/errors/err_ngrok_<n>; check the domain the user pasted |
| `ERROR=Roblox Studio MCP launcher not found` | Studio > Assistant > ... > Manage MCP Servers > **Enable Studio as MCP server** |
| `ERROR=Node.js not found` right after installing Node | open a new shell (old PATH), then retry |
| `bridge-check`: 401 | the key was rotated: `BR session`, then Step 2 and Step 3 |
| `bridge-check`: "fetch failed" / 530 for more than a minute | the PC is asleep, offline or shut down: ask the user to wake it; the service resumes by itself |
| `list_roblox_studios` is empty | no place open, or Studio's MCP toggle is off |
| Long calls fail with HTTP 524 (Cloudflare tunnel only) | use the `async` mode of `generate_*` tools and short `wait_job_finished` calls, or switch to ngrok |
| Windows: Register-ScheduledTask "Access is denied" | a policy blocks per-user tasks: use `BR start` without the service (runs until logoff) and tell the user |

To rotate the key (e.g. it leaked): `BR restart -RotateKey` (macOS `--rotate-key`), then
Step 2 and Step 3.

## Blender on the PC (opt-in)

By default Blender runs headless on the cloud computer (see `blender-assets`), and the
bridge doesn't expose or install Blender. Only if the user already has Blender with the
MCP for Blender add-on running on this PC and wants it used: add `-Blender` (macOS
`--blender`) to install-service or restart, then register the `blender` connector from
`BLENDER_URL` (Step 3). It needs `uv` (`uvx mcp-for-blender`).

## Manual fallback (no local execution)

The user opens PowerShell (Windows) or Terminal (macOS) and runs:
1. Get the files: `git clone https://github.com/anishsrinivasa/grok-studio.git "%USERPROFILE%\grok-studio"`
   (or download the zip from GitHub and unpack it there).
2. Windows: `powershell -ExecutionPolicy Bypass -File "%USERPROFILE%\grok-studio\bridge\start-bridge.ps1" install-service -NgrokDomain <domain>`.
   macOS: `bash ~/grok-studio/bridge/start-bridge.sh install-service --ngrok-domain <domain>`.
3. The user pastes the printed `KEY=` and `STUDIO_URL=` lines to you, and you continue at
   Step 2.
