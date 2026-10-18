<#
.SYNOPSIS
  Expose your LOCAL Roblox Studio MCP and Blender MCP servers to a REMOTE agent
  (for example Grok Bot, which runs on a cloud Linux box) for one build session.

.DESCRIPTION
  Roblox Studio's MCP server and the Blender MCP server are stdio servers: they can
  only be launched by a program running on the same PC as Studio/Blender. A cloud
  agent cannot do that. This script bridges them:

    remote agent --HTTPS--> ngrok tunnel --> 127.0.0.1:<Port> (supergateway, API key)
                                                 |-- /roblox-studio/mcp --stdio--> Studio MCP
                                                 '-- /blender/mcp       --stdio--> mcp-for-blender

  What it does:
    1. Checks prerequisites (Node/npx for supergateway, uv/uvx for Blender MCP,
       Roblox Studio's mcp.bat, and ngrok when -Tunnel is used).
    2. Generates a random API key (or uses -ApiKey).
    3. Starts ONE supergateway process (https://github.com/supercorp-ai/supergateway)
       bound to 127.0.0.1 that serves both stdio servers over Streamable HTTP and
       rejects every request without the key (HTTP 401).
    4. Optionally starts an ngrok tunnel (your own ngrok account) and prints the public
       URLs + key to paste into your bot as custom connectors.
    5. Ctrl+C stops everything and deletes the temporary config.

  Why supergateway and not mcp-proxy: mcp-proxy (sparfenyuk) is a good stdio->HTTP
  bridge, but as of v0.13 it has no option to require an API key in server mode, so
  anything that can reach the port could drive Studio. supergateway has --apiKey and a
  multi-server --config, so one authenticated port serves both tools.

  SECURITY - READ THIS:
    * Anyone with the URL + key can run arbitrary Luau in your open Studio places and
      arbitrary Python in Blender (which can read/write files on this PC).
    * Only run this during an active build session. Ctrl+C tears it all down.
    * A fresh key is generated each run. Never paste it anywhere public.
    * Blender MCP safe mode (BLENDER_MCP_SAFE_MODE=1) is ON by default; it blocks
      scripts that touch arbitrary files, the network, or spawn programs.

  STATUS: UNTESTED ON WINDOWS. Written against the documented CLIs of supergateway 4.x,
  mcp-for-blender 2.x, ngrok v3 and Roblox Studio MCP (Oct 2026). Please report issues.

.PARAMETER Port
  Local port for the gateway (default 8765). Always bound to 127.0.0.1.

.PARAMETER Tunnel
  Start an ngrok tunnel so a cloud agent can reach the gateway. Requires ngrok
  installed and authenticated once with `ngrok config add-authtoken <token>`.

.PARAMETER NgrokUrl
  Optional reserved ngrok domain, e.g. https://my-name.ngrok.app (passed as --url).

.PARAMETER ApiKey
  Use this key instead of generating one (min 24 chars). Not recommended.

.PARAMETER NoStudio
  Do not expose Roblox Studio.

.PARAMETER NoBlender
  Do not expose Blender.

.PARAMETER UnsafeBlender
  Disable Blender MCP safe mode. Not recommended over a tunnel.

.PARAMETER Yes
  Skip the interactive security confirmation.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\bridge\start-bridge.ps1 -Tunnel
#>
[CmdletBinding()]
param(
  [int]$Port = 8765,
  [switch]$Tunnel,
  [string]$NgrokUrl,
  [string]$ApiKey,
  [switch]$NoStudio,
  [switch]$NoBlender,
  [switch]$UnsafeBlender,
  [switch]$Yes,
  [switch]$JsonOutput
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# Pin the supergateway major version so a breaking release cannot change behaviour silently.
$SupergatewayPkg = 'supergateway@4'

function Write-Info($msg) { Write-Host "[bridge] $msg" -ForegroundColor Cyan }
function Write-Warn($msg) { Write-Host "[bridge] $msg" -ForegroundColor Yellow }
function Write-Fail($msg) { Write-Host "[bridge] ERROR: $msg" -ForegroundColor Red; exit 1 }

function Test-Command($name) { return [bool](Get-Command $name -ErrorAction SilentlyContinue) }

# Kill a process and all of its children (npx -> node -> cmd.exe -> StudioMCP ...).
function Stop-Tree([System.Diagnostics.Process]$proc) {
  if ($null -eq $proc) { return }
  try {
    if (-not $proc.HasExited) { & taskkill.exe /PID $proc.Id /T /F 2>$null | Out-Null }
  } catch { }
}

# ---------------------------------------------------------------------------------------
# 0. Security confirmation
# ---------------------------------------------------------------------------------------
Write-Host ''
Write-Host '==================================================================' -ForegroundColor Red
Write-Host ' grok-studio bridge - REMOTE CODE EXECUTION ON THIS PC' -ForegroundColor Red
Write-Host '==================================================================' -ForegroundColor Red
Write-Host ' Anyone holding the URL + API key printed below can run code in your'
Write-Host ' open Roblox Studio places and in Blender on this computer.'
Write-Host ' Run only during a build session. Press Ctrl+C to tear everything down.'
Write-Host ''
if (-not $Yes) {
  $answer = Read-Host "Type 'yes' to continue"
  if ($answer -ne 'yes') { Write-Info 'Aborted.'; exit 0 }
}

if ($NoStudio -and $NoBlender) { Write-Fail 'Nothing to expose: both -NoStudio and -NoBlender were given.' }

# ---------------------------------------------------------------------------------------
# 1. Prerequisites
# ---------------------------------------------------------------------------------------
Write-Info 'Checking prerequisites...'

if (-not (Test-Command 'npx')) {
  Write-Fail 'Node.js (npx) not found. Install Node.js LTS from https://nodejs.org and reopen PowerShell.'
}

$StudioBat = $null
if (-not $NoStudio) {
  if (-not $env:LOCALAPPDATA) { Write-Fail 'LOCALAPPDATA is not set.' }
  $StudioBat = Join-Path $env:LOCALAPPDATA 'Roblox\mcp.bat'
  if ($env:ROBLOX_STUDIO_MCP_PATH) { $StudioBat = $env:ROBLOX_STUDIO_MCP_PATH }
  if (-not (Test-Path $StudioBat)) {
    Write-Fail ("Roblox Studio MCP launcher not found at '$StudioBat'. Update Roblox Studio, then in Studio: " +
      "Assistant > ... > Manage MCP Servers > turn on 'Enable Studio as MCP server'.")
  }
}

if (-not $NoBlender) {
  if (-not (Test-Command 'uvx')) {
    Write-Fail ('uv/uvx not found. Install with: powershell -c "irm https://astral.sh/uv/install.ps1 | iex" ' +
      '(then reopen PowerShell). Then run: uvx mcp-for-blender setup')
  }
  Write-Warn 'Make sure Blender is open with the "MCP for Blender" add-on enabled (N panel > MCP for Blender > Start MCP Server).'
}

if ($Tunnel -and -not (Test-Command 'ngrok')) {
  Write-Fail 'ngrok not found. Install it (https://ngrok.com/download or: winget install ngrok.ngrok), then run: ngrok config add-authtoken <your token>'
}

# Make sure the port is free on loopback.
$inUse = Get-NetTCPConnection -LocalAddress 127.0.0.1 -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($inUse) { Write-Fail "Port $Port is already in use. Pass -Port <other>." }

# ---------------------------------------------------------------------------------------
# 2. API key
# ---------------------------------------------------------------------------------------
if ($ApiKey) {
  if ($ApiKey.Length -lt 24) { Write-Fail '-ApiKey must be at least 24 characters.' }
  $Key = $ApiKey
} else {
  $bytes = New-Object byte[] 32
  [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
  # URL-safe base64 without padding (43 chars, 256 bits of entropy).
  $Key = [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
}

# ---------------------------------------------------------------------------------------
# 3. Write the supergateway config to a private temp folder (no secrets in it)
# ---------------------------------------------------------------------------------------
$RuntimeDir = Join-Path ([System.IO.Path]::GetTempPath()) ("grok-studio-bridge-" + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $RuntimeDir | Out-Null
$ConfigPath = Join-Path $RuntimeDir 'servers.json'

$servers = [ordered]@{}
if (-not $NoStudio) {
  # Same command Roblox documents for Windows: cmd.exe /c %LOCALAPPDATA%\Roblox\mcp.bat
  # (the path is expanded here because supergateway runs commands without a shell).
  $servers['roblox-studio'] = [ordered]@{ command = 'cmd.exe'; args = @('/c', $StudioBat) }
}
if (-not $NoBlender) {
  $servers['blender'] = [ordered]@{ command = 'uvx'; args = @('mcp-for-blender') }
}

$config = [ordered]@{
  host            = '127.0.0.1'          # never listen on the LAN; the tunnel connects locally
  port            = $Port
  outputTransport = 'streamableHttp'
  stateful        = $true                # keep one Studio/Blender MCP process per client session
  sessionTimeout  = 3600000              # 1 hour idle timeout for a session
  healthEndpoint  = '/healthz'           # unauthenticated, returns only "ok"
  mcpServers      = $servers
}
# Write UTF-8 *without* BOM (Windows PowerShell 5.1's -Encoding UTF8 adds a BOM).
$json = $config | ConvertTo-Json -Depth 8
[System.IO.File]::WriteAllText($ConfigPath, $json, (New-Object System.Text.UTF8Encoding($false)))

# Secrets and options go to the child through the environment, not the command line,
# so they don't show up in process listings.
$env:SUPERGATEWAY_API_KEY = $Key
if (-not $UnsafeBlender) { $env:BLENDER_MCP_SAFE_MODE = '1' } else { Write-Warn 'Blender safe mode is OFF.' }

$gateway = $null
$ngrok = $null

try {
  # -------------------------------------------------------------------------------------
  # 4. Start supergateway
  # -------------------------------------------------------------------------------------
  Write-Info "Starting supergateway on http://127.0.0.1:$Port ..."
  $gwLog = Join-Path $RuntimeDir 'gateway.log'
  $gwErr = Join-Path $RuntimeDir 'gateway.err.log'
  $gateway = Start-Process -FilePath 'npx.cmd' `
    -ArgumentList @('-y', $SupergatewayPkg, '--config', "`"$ConfigPath`"", '--exitWithProcess', $PID, '--logLevel', 'info') `
    -NoNewWindow -PassThru -RedirectStandardOutput $gwLog -RedirectStandardError $gwErr

  # Wait for the health endpoint (first run downloads the package, so allow a while).
  $healthy = $false
  for ($i = 0; $i -lt 90; $i++) {
    Start-Sleep -Seconds 1
    if ($gateway.HasExited) { break }
    try {
      $r = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$Port/healthz" -TimeoutSec 2
      if ($r.StatusCode -eq 200) { $healthy = $true; break }
    } catch { }
  }
  if (-not $healthy) {
    Write-Warn "Gateway did not become healthy. Last log lines ($gwErr):"
    if (Test-Path $gwErr) { Get-Content $gwErr -Tail 20 | ForEach-Object { Write-Host "  $_" } }
    throw 'supergateway failed to start'
  }
  Write-Info 'Gateway is up (requests without the API key get HTTP 401).'

  # -------------------------------------------------------------------------------------
  # 5. Optional ngrok tunnel
  # -------------------------------------------------------------------------------------
  $BaseUrl = "http://127.0.0.1:$Port"
  if ($Tunnel) {
    Write-Info 'Starting ngrok tunnel...'
    $ngArgs = @('http', "127.0.0.1:$Port", '--log', 'stdout')
    if ($NgrokUrl) { $ngArgs += @('--url', $NgrokUrl) }
    $ngLog = Join-Path $RuntimeDir 'ngrok.log'
    $ngrok = Start-Process -FilePath 'ngrok' -ArgumentList $ngArgs -NoNewWindow -PassThru `
      -RedirectStandardOutput $ngLog -RedirectStandardError (Join-Path $RuntimeDir 'ngrok.err.log')

    # ngrok's local agent API lists the public URL.
    $public = $null
    for ($i = 0; $i -lt 30 -and -not $public; $i++) {
      Start-Sleep -Seconds 1
      if ($ngrok.HasExited) { break }
      try {
        $t = Invoke-RestMethod -Uri 'http://127.0.0.1:4040/api/tunnels' -TimeoutSec 2
        $public = ($t.tunnels | Where-Object { $_.public_url -like 'https://*' } | Select-Object -First 1).public_url
      } catch { }
    }
    if (-not $public) {
      Write-Warn "Could not read the ngrok URL. Check $ngLog (is your authtoken configured?)."
      throw 'ngrok failed to start'
    }
    $BaseUrl = $public.TrimEnd('/')
  }

  # -------------------------------------------------------------------------------------
  # 6. Print connection details
  # -------------------------------------------------------------------------------------
  if ($JsonOutput) {
    # Machine-readable single-line JSON for automated setup (e.g. GrokBot ExternalShell).
    $jsonObj = [ordered]@{}
    if (-not $NoStudio)  { $jsonObj['studio_url']  = "$BaseUrl/roblox-studio/mcp" }
    if (-not $NoBlender) { $jsonObj['blender_url'] = "$BaseUrl/blender/mcp" }
    $jsonObj['api_key'] = $Key
    $jsonObj['port']    = $Port
    $jsonObj | ConvertTo-Json -Compress | Write-Output
  } else {
    Write-Host ''
    Write-Host '================== ADD THESE AS CUSTOM CONNECTORS ==================' -ForegroundColor Green
    if (-not $NoStudio)  { Write-Host "  Roblox Studio MCP : $BaseUrl/roblox-studio/mcp" }
    if (-not $NoBlender) { Write-Host "  Blender MCP       : $BaseUrl/blender/mcp" }
    Write-Host "  Transport         : Streamable HTTP"
    Write-Host "  Auth header       : Authorization: Bearer $Key"
    Write-Host "                      (or X-API-Key: $Key)"
    Write-Host '====================================================================' -ForegroundColor Green
    if (-not $Tunnel) {
      Write-Warn 'No tunnel: these URLs only work from this PC. Re-run with -Tunnel for a cloud agent.'
    }
    Write-Host ''
    Write-Host 'Example client config (for clients that accept mcpServers JSON):'
    $example = [ordered]@{ mcpServers = [ordered]@{} }
    if (-not $NoStudio)  { $example.mcpServers['roblox-studio'] = [ordered]@{ url = "$BaseUrl/roblox-studio/mcp"; headers = @{ Authorization = "Bearer $Key" } } }
    if (-not $NoBlender) { $example.mcpServers['blender'] = [ordered]@{ url = "$BaseUrl/blender/mcp"; headers = @{ Authorization = "Bearer $Key" } } }
    $example | ConvertTo-Json -Depth 6 | Write-Host
    Write-Host ''
    Write-Warn 'Keep Studio (with "Enable Studio as MCP server" on) and Blender open.'
    Write-Warn 'Press Ctrl+C to stop the bridge. Remove the connectors from your bot afterwards.'
  }

  # -------------------------------------------------------------------------------------
  # 7. Stay alive until Ctrl+C or a child dies
  # -------------------------------------------------------------------------------------
  while ($true) {
    Start-Sleep -Seconds 2
    if ($gateway.HasExited) { Write-Warn 'supergateway exited.'; break }
    if ($ngrok -and $ngrok.HasExited) { Write-Warn 'ngrok exited.'; break }
  }
}
finally {
  # Runs on Ctrl+C, on errors, and on normal exit.
  Write-Info 'Shutting down bridge...'
  Stop-Tree $ngrok
  Stop-Tree $gateway
  Remove-Item Env:\SUPERGATEWAY_API_KEY -ErrorAction SilentlyContinue
  Remove-Item -Recurse -Force $RuntimeDir -ErrorAction SilentlyContinue
  Write-Info 'Stopped. The API key from this session is now useless.'
}
