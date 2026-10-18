<#
.SYNOPSIS
  The grok-studio bridge: exposes Roblox Studio on this PC (plus a small file drop, and
  optionally Blender) to the cloud bot team over one authenticated HTTPS URL.

.DESCRIPTION
    cloud bots --HTTPS--> tunnel --> 127.0.0.1:<Port> (supergateway, API key required)
                                       |-- /roblox-studio/mcp --stdio--> Studio MCP (one per session)
                                       |-- /files/mcp         --stdio--> files-server.mjs (file drop)
                                       '-- /blender/mcp       --stdio--> mcp-for-blender (opt-in: -Blender)
    Roblox Studio (this PC) --> 127.0.0.1:<Port+1>/<token>/...  (read-only view of the drop folder)

  It runs as a supervisor: it starts supergateway, the drop folder's HTTP view and the
  tunnel, and restarts any of them that dies. Installed as a service (a per-user
  Scheduled Task at logon, hidden), it survives reboots.

  Everything it keeps lives next to this script:
    bridge.key      the API key, created once (user-only ACL). -RotateKey replaces it.
    config.json     port, tunnel provider, static ngrok domain, what to expose (not secret)
    session.json    the live session: URLs, key, PIDs (user-only ACL)
    node_modules\   supergateway, pinned by package.json / package-lock.json (npm ci once)
    logs\  run\  bin\

  Tunnels (config "tunnel"):
    ngrok       default. With a static domain (a free account gets one, e.g.
                name.ngrok-free.dev; -NgrokDomain) the URL never changes, so connectors
                are registered once. The authtoken is applied once from $env:NGROK_AUTHTOKEN
                if ngrok isn't configured yet.
    cloudflare  fallback, no account: a quick tunnel. Its URL CHANGES on every tunnel
                start, so connectors must be updated each time (TUNNEL_STABLE=no).
    none        no tunnel: localhost only (local agents, tests).

  SECURITY: anyone with the URL + key can run Luau in your open Studio places and drop
  files on this PC (and run Python in Blender, if exposed). Stop it when you don't need it.

.EXAMPLE
  .\start-bridge.ps1 install-service -NgrokDomain my-name.ngrok-free.dev
.EXAMPLE
  .\start-bridge.ps1 status
.EXAMPLE
  .\start-bridge.ps1 session        # prints KEY=..., STUDIO_URL=..., one per line
.EXAMPLE
  .\start-bridge.ps1 run -TunnelProvider none     # foreground, Ctrl+C stops
#>
[CmdletBinding()]
param(
  [Parameter(Position = 0)]
  [ValidateSet('run', 'install-service', 'uninstall-service', 'status', 'start', 'stop', 'restart', 'session', 'help')]
  [string]$Command = 'run',
  [int]$Port = 0,
  [ValidateSet('', 'auto', 'ngrok', 'cloudflare', 'none')]
  [string]$TunnelProvider = '',
  [string]$NgrokDomain = '',
  [switch]$Blender,
  [switch]$NoStudio,
  [switch]$NoFiles,
  [string]$DropDir = '',
  [string]$TaskName = '',
  [switch]$RotateKey,
  [switch]$Deep,
  [switch]$Purge,
  [switch]$FromTask,
  [switch]$UnsafeBlender,
  # One compact JSON line on stdout instead of KEY=... lines (nothing else goes to stdout).
  [switch]$JsonOutput,
  # Accepted for compatibility with older callers; they change nothing.
  [switch]$Tunnel, [switch]$NoBlender, [switch]$Yes, [string]$NgrokUrl = '', [string]$ApiKey = ''
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$BridgeDir   = $PSScriptRoot
$ConfigPath  = Join-Path $BridgeDir 'config.json'
$KeyPath     = Join-Path $BridgeDir 'bridge.key'
$SessionPath = Join-Path $BridgeDir 'session.json'
$RunDir      = Join-Path $BridgeDir 'run'
$LogDir      = Join-Path $BridgeDir 'logs'
$BinDir      = Join-Path $BridgeDir 'bin'
$StopFile    = Join-Path $RunDir 'stop'
$StoppedFlag = Join-Path $RunDir 'stopped'
$GatewayJs   = Join-Path $BridgeDir 'node_modules\supergateway\dist\index.js'
$FilesServer = Join-Path $BridgeDir 'files-server.mjs'
$TaskPath    = '\GrokStudio\'
$Interactive = -not $FromTask

# Pinned cloudflared for the fallback tunnel (GitHub release asset digest, 2026.9.3).
$CloudflaredVersion = '2026.9.3'
$CloudflaredUrl = "https://github.com/cloudflare/cloudflared/releases/download/$CloudflaredVersion/cloudflared-windows-amd64.exe"
$CloudflaredSha256 = 'f096265ec2fcbe9bb6e2d64268db167ced3fcbb83d894bdb9e2fcdb26f2ea7e2'

if ($Command -eq 'help') { Get-Help $PSCommandPath -Detailed; exit 0 }
foreach ($d in $RunDir, $LogDir) { New-Item -ItemType Directory -Force -Path $d | Out-Null }
if ($Interactive) { try { $host.UI.RawUI.WindowTitle = 'Grok Studio bridge' } catch { } }

# ---------------------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------------------
function Log($msg) {
  $line = "[{0}] {1}" -f (Get-Date).ToString('yyyy-MM-dd HH:mm:ss'), $msg
  try { [System.IO.File]::AppendAllText((Join-Path $LogDir 'supervisor.log'), "$line`r`n", (New-Object System.Text.UTF8Encoding($false))) } catch { }
  if ($Interactive) { [Console]::Error.WriteLine("[bridge] $msg") }
}
function Out-Line($text) { [Console]::Out.WriteLine($text) }
# A short result (stopped, uninstalled, error, ...): STATUS=/ERROR= lines, or one JSON line.
function Out-Result([string]$status, [string]$err = '') {
  if ($JsonOutput) {
    $o = [ordered]@{ status = $status }; if ($err) { $o.error = $err }
    Out-Line ($o | ConvertTo-Json -Compress)
  } else { Out-Line "STATUS=$status"; if ($err) { Out-Line "ERROR=$err" } }
}
function Fail($msg) { Log "ERROR: $msg"; Out-Result 'error' $msg; exit 1 }
# Windows PowerShell 5.1 turns a native program's stderr into a terminating error while
# $ErrorActionPreference is Stop; run native programs through this.
function Invoke-Quiet([scriptblock]$sb) { $ErrorActionPreference = 'Continue'; & $sb }
function Quote([string]$s) { if ($s -match '[\s"]') { '"' + $s.Replace('"', '\"') + '"' } else { $s } }
function Write-Utf8([string]$path, [string]$text) { [System.IO.File]::WriteAllText($path, $text, (New-Object System.Text.UTF8Encoding($false))) }

function New-RandomToken([int]$bytes) {
  $buf = New-Object byte[] $bytes
  [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($buf)
  [Convert]::ToBase64String($buf).TrimEnd('=').Replace('+', '-').Replace('/', '_')
}

# Only the current user may read the file (no inherited ACEs).
function Protect-File([string]$path) {
  $acl = New-Object System.Security.AccessControl.FileSecurity
  $acl.SetAccessRuleProtection($true, $false)
  $sid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
  $acl.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule($sid, 'FullControl', 'Allow')))
  Set-Acl -LiteralPath $path -AclObject $acl
}
function Write-Secret([string]$path, [string]$text) {
  $tmp = "$path.tmp"
  Write-Utf8 $tmp ''
  Protect-File $tmp
  Write-Utf8 $tmp $text
  for ($i = 0; $i -lt 5; $i++) {
    try { Move-Item -Force -LiteralPath $tmp -Destination $path; return } catch { Start-Sleep -Milliseconds 100 }
  }
  Move-Item -Force -LiteralPath $tmp -Destination $path
}

function Test-Tcp([int]$p, [int]$ms = 300) {
  $c = New-Object System.Net.Sockets.TcpClient
  try {
    $ar = $c.BeginConnect('127.0.0.1', $p, $null, $null)
    if (-not $ar.AsyncWaitHandle.WaitOne($ms)) { return $false }
    $c.EndConnect($ar); return $true
  } catch { return $false } finally { $c.Close() }
}

$CurlExe = (Get-Command 'curl.exe' -ErrorAction SilentlyContinue)
# HTTP status of a GET (0 = no answer). curl.exe avoids Invoke-WebRequest's slow start.
function Get-HttpCode([string]$url, [int]$sec = 3) {
  if ($CurlExe) {
    $code = Invoke-Quiet { & $CurlExe.Source -s -o NUL -w '%{http_code}' --max-time $sec -H 'ngrok-skip-browser-warning: 1' $url 2>$null }
    $n = 0; [void][int]::TryParse("$code", [ref]$n); return $n
  }
  try {
    $req = [System.Net.HttpWebRequest]::Create($url); $req.Timeout = $sec * 1000
    if ($url -like 'http://127.0.0.1*') { $req.Proxy = $null }
    $resp = $req.GetResponse(); $n = [int]$resp.StatusCode; $resp.Close(); return $n
  } catch [System.Net.WebException] {
    if ($_.Exception.Response) { return [int]$_.Exception.Response.StatusCode } return 0
  } catch { return 0 }
}

function Read-Json([string]$path) {
  if (-not (Test-Path -LiteralPath $path)) { return $null }
  try { return (Get-Content -Raw -LiteralPath $path | ConvertFrom-Json) } catch { return $null }
}
function Get-Prop($obj, [string]$name, $default = $null) {
  if ($null -eq $obj) { return $default }
  if ($obj -is [System.Collections.IDictionary]) { if ($obj.Contains($name)) { return $obj[$name] } return $default }
  if ($obj.PSObject.Properties[$name]) { return $obj.$name }
  return $default
}

# ngrok has an authtoken in its own config file.
function Test-NgrokConfigured([string]$ngrok) {
  if (-not $ngrok) { return $false }
  try {
    $out = (Invoke-Quiet { & $ngrok config check 2>&1 } | Out-String)
    $m = [regex]::Match($out, 'Valid configuration file at (.+?)\s*$', 'Multiline')
    if (-not $m.Success) { return $false }
    $cfg = $m.Groups[1].Value.Trim()
    return ((Test-Path -LiteralPath $cfg) -and [bool](Select-String -LiteralPath $cfg -Pattern '^\s*authtoken:\s*\S+' -Quiet))
  } catch { return $false }
}
function Test-NgrokAuth([string]$ngrok) { return [bool]($ngrok -and ($env:NGROK_AUTHTOKEN -or (Test-NgrokConfigured $ngrok))) }

function Get-Cloudflared {
  $onPath = Get-Command 'cloudflared' -ErrorAction SilentlyContinue
  if ($onPath) { return $onPath.Source }
  $exe = Join-Path $BinDir "cloudflared-$CloudflaredVersion.exe"
  if ((Test-Path $exe) -and (Get-FileHash -Algorithm SHA256 $exe).Hash.ToLower() -eq $CloudflaredSha256) { return $exe }
  New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
  Log "Downloading cloudflared $CloudflaredVersion (about 55 MB, one time)..."
  $tmp = "$exe.download"
  if ($CurlExe) { Invoke-Quiet { & $CurlExe.Source -fsSL -o $tmp $CloudflaredUrl 2>&1 | Out-Null } } else {
    $old = $ProgressPreference; $ProgressPreference = 'SilentlyContinue'
    try { Invoke-WebRequest -UseBasicParsing -Uri $CloudflaredUrl -OutFile $tmp } finally { $ProgressPreference = $old } }
  if (-not (Test-Path $tmp) -or (Get-FileHash -Algorithm SHA256 $tmp).Hash.ToLower() -ne $CloudflaredSha256) {
    Remove-Item -Force $tmp -ErrorAction SilentlyContinue
    throw 'cloudflared download failed or failed its SHA-256 check'
  }
  Move-Item -Force $tmp $exe
  return $exe
}

# Kill processes and their children with one taskkill call.
function Stop-Tree {
  $alive = @($args | ForEach-Object { $_ } | Where-Object { $_ -and (Get-Process -Id $_ -ErrorAction SilentlyContinue) })
  if ($alive.Count -eq 0) { return }
  $argv = @('/T', '/F'); foreach ($id in $alive) { $argv += @('/PID', "$id") }
  Invoke-Quiet { & taskkill.exe @argv 2>&1 | Out-Null }
}

# ---------------------------------------------------------------------------------------
# Settings: config.json, overridden by parameters
# ---------------------------------------------------------------------------------------
$cfg = Read-Json $ConfigPath
$NodeExe = Get-Prop $cfg 'node_path' ''
if (-not $NodeExe -or -not (Test-Path -LiteralPath $NodeExe)) {
  $n = Get-Command 'node' -ErrorAction SilentlyContinue; $NodeExe = $(if ($n) { $n.Source } else { '' })
}
$NgrokExe = Get-Prop $cfg 'ngrok_path' ''
if (-not $NgrokExe -or -not (Test-Path -LiteralPath $NgrokExe)) {
  $n = Get-Command 'ngrok' -ErrorAction SilentlyContinue; $NgrokExe = $(if ($n) { $n.Source } else { '' })
}

$Conf = [ordered]@{
  port         = [int](Get-Prop $cfg 'port' 8765)
  tunnel       = [string](Get-Prop $cfg 'tunnel' '')
  ngrok_domain = [string](Get-Prop $cfg 'ngrok_domain' '')
  studio       = [bool](Get-Prop $cfg 'studio' $true)
  files        = [bool](Get-Prop $cfg 'files' $true)
  blender      = [bool](Get-Prop $cfg 'blender' $false)
  drop_dir     = [string](Get-Prop $cfg 'drop_dir' '')
  files_token  = [string](Get-Prop $cfg 'files_token' '')
  task_name    = [string](Get-Prop $cfg 'task_name' 'GrokStudioBridge')
  node_path    = $NodeExe
  ngrok_path   = $NgrokExe
}
if ($Port -gt 0) { $Conf.port = $Port }
if ($NgrokUrl -and -not $NgrokDomain) { $NgrokDomain = $NgrokUrl }
if ($NgrokDomain) { $Conf.ngrok_domain = ($NgrokDomain -replace '^https?://', '').TrimEnd('/') }
if ($TunnelProvider -and $TunnelProvider -ne 'auto') { $Conf.tunnel = $TunnelProvider } elseif ($TunnelProvider -eq 'auto') { $Conf.tunnel = '' }
if ($NoStudio) { $Conf.studio = $false }
if ($NoFiles) { $Conf.files = $false }
if ($Blender) { $Conf.blender = $true }
if ($DropDir) { $Conf.drop_dir = $DropDir }
if ($TaskName) { $Conf.task_name = $TaskName }
if (-not $Conf.drop_dir) { $Conf.drop_dir = Join-Path $env:USERPROFILE 'grok-studio\drop' }
$Conf.drop_dir = [System.IO.Path]::GetFullPath($Conf.drop_dir)
if (-not $Conf.files_token) { $Conf.files_token = New-RandomToken 16 }
# auto (no tunnel configured): ngrok when it is set up (or can be, from NGROK_AUTHTOKEN), else
# the Cloudflare fallback. Only the commands that start the bridge pay for this check.
function Resolve-Tunnel {
  if ($Conf.tunnel) { return }
  if ($Conf.ngrok_path -and ($Conf.ngrok_domain -or (Test-NgrokAuth $Conf.ngrok_path))) { $Conf.tunnel = 'ngrok' } else { $Conf.tunnel = 'cloudflare' }
}
$FilesPort = $Conf.port + 1
$MetricsPort = $Conf.port + 2   # cloudflared's local metrics (/ready)
$MutexName = "Local\GrokStudioBridge-$($Conf.port)"

function Save-Config { Write-Utf8 $ConfigPath (($Conf | ConvertTo-Json) + "`n") }

function Get-Key {
  if ($ApiKey) { return $ApiKey }
  if ($RotateKey -or -not (Test-Path -LiteralPath $KeyPath)) {
    Write-Secret $KeyPath ((New-RandomToken 32) + "`n")
    Log $(if ($RotateKey) { 'API key rotated.' } else { 'API key created.' })
    $script:RotateKey = $false
  }
  return (Get-Content -LiteralPath $KeyPath -TotalCount 1).Trim()
}

function Install-Runtime {
  if (-not $Conf.node_path) { Fail 'Node.js not found. Install Node.js LTS (winget install OpenJS.NodeJS.LTS) and open a new shell.' }
  if (Test-Path -LiteralPath $GatewayJs) { return }
  $npm = Join-Path (Split-Path $Conf.node_path) 'npm.cmd'
  if (-not (Test-Path $npm)) { $npm = 'npm.cmd' }
  Log 'Installing supergateway (pinned, one time)...'
  $verb = $(if (Test-Path (Join-Path $BridgeDir 'package-lock.json')) { 'ci' } else { 'install' })
  Push-Location $BridgeDir
  try { Invoke-Quiet { & $npm $verb --omit=dev --no-audit --no-fund --loglevel=error 2>&1 } | Where-Object { "$_".Trim() } | ForEach-Object { Log "npm: $_" } } finally { Pop-Location }
  if (-not (Test-Path -LiteralPath $GatewayJs)) { Fail "npm $verb did not install supergateway (see logs\supervisor.log)." }
}

function Get-PublicBase {
  if ($Conf.tunnel -eq 'ngrok' -and $Conf.ngrok_domain) { return "https://$($Conf.ngrok_domain)" }
  return $null
}

function Build-Session($key, $public, $state, $pids, $tunnelError) {
  $base = $(if ($public) { $public } else { "http://127.0.0.1:$($Conf.port)" })
  $o = [ordered]@{ state = $state; api_key = $key; public_url = $base }
  if ($Conf.studio)  { $o.studio_url  = "$base/roblox-studio/mcp" }
  if ($Conf.files)   { $o.files_url   = "$base/files/mcp"; $o.pc_drop_dir = $Conf.drop_dir; $o.pc_http_base = "http://127.0.0.1:$FilesPort/$($Conf.files_token)" }
  if ($Conf.blender) { $o.blender_url = "$base/blender/mcp" }
  $o.tunnel = $Conf.tunnel
  $o.tunnel_stable = ($Conf.tunnel -eq 'none') -or ($Conf.tunnel -eq 'ngrok' -and [bool]$Conf.ngrok_domain)
  $o.tunnel_error = $tunnelError
  $o.port = $Conf.port; $o.files_port = $FilesPort; $o.pc_os = 'windows'
  $o.supervisor_pid = $pids.supervisor; $o.gateway_pid = $pids.gateway; $o.files_pid = $pids.files; $o.tunnel_pid = $pids.tunnel
  $o.bridge_dir = $BridgeDir; $o.stop_file = $StopFile; $o.task_name = $Conf.task_name
  $o.started_at = $pids.started_at; $o.updated_at = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
  return $o
}

function Write-SessionLines($s) {
  if ($JsonOutput) {
    # The same fields as /workspace/grok-studio/.bridge.json, on ONE line.
    $o = [ordered]@{ status = (Get-Prop $s 'state' $null) }
    foreach ($k in 'api_key', 'studio_url', 'files_url', 'blender_url', 'pc_drop_dir', 'pc_http_base', 'public_url', 'tunnel', 'tunnel_stable', 'tunnel_error', 'port') {
      $v = Get-Prop $s $k $null
      if ($null -ne $v -and "$v" -ne '') { $o[$k] = $v }
    }
    $o.pc_os = 'windows'; $o.session_file = $SessionPath
    Out-Line ($o | ConvertTo-Json -Compress)
    return
  }
  Out-Line "STATUS=$($s.state)"
  Out-Line "KEY=$($s.api_key)"
  foreach ($pair in @(@('STUDIO_URL', 'studio_url'), @('FILES_URL', 'files_url'), @('BLENDER_URL', 'blender_url'),
                      @('PC_DROP_DIR', 'pc_drop_dir'), @('PC_HTTP_BASE', 'pc_http_base'), @('TUNNEL', 'tunnel'))) {
    $v = Get-Prop $s $pair[1] $null
    if ($v) { Out-Line "$($pair[0])=$v" }
  }
  Out-Line ('TUNNEL_STABLE=' + $(if ((Get-Prop $s 'tunnel_stable' $false)) { 'yes' } else { 'no' }))
  $err = Get-Prop $s 'tunnel_error' $null
  if ($err) { Out-Line "TUNNEL_ERROR=$err" }
  Out-Line "PC_OS=windows"
  Out-Line "PORT=$($s.port)"
  Out-Line "SESSION_FILE=$SessionPath"
}

function Test-Task {
  Invoke-Quiet { & schtasks.exe /Query /TN "$TaskPath$($Conf.task_name)" 2>&1 | Out-Null }
  return ($LASTEXITCODE -eq 0)
}

function Get-Status([bool]$deep) {
  $s = Read-Json $SessionPath
  $supPid = Get-Prop $s 'supervisor_pid' $null
  $sup = $false
  if ($supPid) { $p = Get-Process -Id $supPid -ErrorAction SilentlyContinue; $sup = [bool]($p -and $p.ProcessName -match 'powershell|pwsh') }
  $gw = $sup -and (Test-Tcp $Conf.port)
  $files = (-not $Conf.files) -or ($sup -and (Test-Tcp $FilesPort))
  $tunnel = Get-Prop $s 'tunnel' $Conf.tunnel   # what the running session uses
  $tpid = Get-Prop $s 'tunnel_pid' $null
  $tun = ($tunnel -eq 'none') -or ($sup -and $tpid -and [bool](Get-Process -Id $tpid -ErrorAction SilentlyContinue))
  $o = [ordered]@{
    running = $sup; gateway_up = $gw; files_up = $files; tunnel_up = $tun
    url = (Get-Prop $s 'public_url' (Get-PublicBase)); tunnel = $tunnel
    tunnel_stable = [bool](Get-Prop $s 'tunnel_stable' $false); tunnel_error = (Get-Prop $s 'tunnel_error' $null)
    supervisor_pid = $(if ($sup) { $supPid } else { $null }); port = $Conf.port
    state = $(if (-not $sup) { 'stopped' } else { Get-Prop $s 'state' 'unknown' })
    key_present = (Test-Path -LiteralPath $KeyPath); updated_at = (Get-Prop $s 'updated_at' $null)
  }
  if ($deep) {
    $o.service_installed = Test-Task
    $o.public_healthz = $(if ($o.url) { Get-HttpCode "$($o.url)/healthz" 5 } else { 0 })
  }
  return $o
}

# ---------------------------------------------------------------------------------------
# run: the supervisor
# ---------------------------------------------------------------------------------------
function Invoke-Run {
  Log "Supervisor starting (pid $PID$(if ($FromTask) { ', service' }))."
  Resolve-Tunnel
  $mutex = New-Object System.Threading.Mutex($false, $MutexName)
  try { $owned = $mutex.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $owned = $true }
  if (-not $owned) { Log "Another bridge supervisor already runs on port $($Conf.port)."; exit 0 }

  if ($FromTask -and (Test-Path $StoppedFlag)) {
    # 'stop' holds until the next boot; the 5-minute repeat trigger must not revive it.
    $boot = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
    if ((Get-Item $StoppedFlag).LastWriteTime -gt $boot) { exit 0 }
    Remove-Item -Force $StoppedFlag
  }
  Remove-Item -Force $StopFile -ErrorAction SilentlyContinue

  # Leftovers of a supervisor that was killed without cleaning up (e.g. an orphaned tunnel).
  $old = Read-Json $SessionPath
  foreach ($name in 'gateway_pid', 'files_pid', 'tunnel_pid') {
    $op = Get-Prop $old $name $null
    if (-not $op -or -not (Get-Process -Id $op -ErrorAction SilentlyContinue)) { continue }
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$op" -ErrorAction SilentlyContinue
    if ($proc -and $proc.CommandLine -and ($proc.CommandLine -match [regex]::Escape($BridgeDir) -or $proc.CommandLine -match "127\.0\.0\.1:$($Conf.port)$Conf")) {
      Log "Stopping a leftover process from the last run (pid $op)."; Stop-Tree $op
    }
  }

  if (-not $Conf.studio -and -not $Conf.files -and -not $Conf.blender) { Fail 'Nothing to expose.' }
  Install-Runtime
  $key = Get-Key
  $studioBat = $null
  if ($Conf.studio) {
    $studioBat = $(if ($env:ROBLOX_STUDIO_MCP_PATH) { $env:ROBLOX_STUDIO_MCP_PATH } else { Join-Path $env:LOCALAPPDATA 'Roblox\mcp.bat' })
    if (-not (Test-Path -LiteralPath $studioBat)) { Fail "Roblox Studio MCP launcher not found at $studioBat. In Studio: Assistant > ... > Manage MCP Servers > Enable Studio as MCP server." }
  }
  if ($Conf.blender -and -not (Get-Command 'uvx' -ErrorAction SilentlyContinue)) { Fail 'Blender is enabled but uv/uvx is missing (https://docs.astral.sh/uv/).' }
  if ($Conf.files) { New-Item -ItemType Directory -Force -Path $Conf.drop_dir | Out-Null }
  if ($Conf.tunnel -eq 'ngrok') {
    if (-not $Conf.ngrok_path) { Fail 'ngrok not found (winget install ngrok.ngrok), or use -TunnelProvider cloudflare.' }
    if (-not (Test-NgrokAuth $Conf.ngrok_path)) { Fail 'ngrok has no authtoken: set NGROK_AUTHTOKEN and run install-service, or: ngrok config add-authtoken <token>.' }
  }
  $ports = @($Conf.port) + $(if ($Conf.files) { @($FilesPort) } else { @() }) + $(if ($Conf.tunnel -eq 'cloudflare') { @($MetricsPort) } else { @() })
  foreach ($p in $ports) {
    if (Test-Tcp $p 200) { Fail "Port $p is already in use (another bridge?). Run 'status', or pass -Port <other>." }
  }

  # supergateway config (no secrets: the key is read from bridge.key)
  $servers = [ordered]@{}
  if ($Conf.studio)  { $servers['roblox-studio'] = [ordered]@{ command = 'cmd.exe'; args = @('/c', $studioBat) } }
  if ($Conf.files)   { $servers['files'] = [ordered]@{ command = $Conf.node_path; args = @($FilesServer)
                      env = [ordered]@{ GROK_STUDIO_DROP_DIR = $Conf.drop_dir; GROK_STUDIO_HTTP_BASE = "http://127.0.0.1:$FilesPort/$($Conf.files_token)" } } }
  if ($Conf.blender) { $servers['blender'] = [ordered]@{ command = 'uvx'; args = @('mcp-for-blender') } }
  $gwConfig = Join-Path $RunDir 'servers.json'
  Write-Utf8 $gwConfig ([ordered]@{ host = '127.0.0.1'; port = $Conf.port; outputTransport = 'streamableHttp'; stateful = $true
    sessionTimeout = 3600000; healthEndpoint = '/healthz'; mcpServers = $servers } | ConvertTo-Json -Depth 8)
  if (-not $UnsafeBlender) { $env:BLENDER_MCP_SAFE_MODE = '1' }
  $env:GROK_STUDIO_DROP_DIR = $Conf.drop_dir
  $env:GROK_STUDIO_HTTP_BASE = "http://127.0.0.1:$FilesPort/$($Conf.files_token)"
  $env:GROK_STUDIO_HTTP_TOKEN = $Conf.files_token

  $kids = @{ gateway = $null; files = $null; tunnel = $null }
  $meta = @{}
  foreach ($k in 'gateway', 'files', 'tunnel') { $meta[$k] = @{ fails = 0; next = [datetime]::MinValue; started = [datetime]::MinValue } }
  $startedAt = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
  # Shared, mutable run state: nested functions can read the caller's variables but not assign them.
  $st = @{ public = (Get-PublicBase); tunnelError = $null; last = $null }

  function Start-Child([string]$name) {
    $log = Join-Path $LogDir "$name.log"; $err = Join-Path $LogDir "$name.err.log"
    switch ($name) {
      'gateway' { $exe = $Conf.node_path; $argv = @((Quote $GatewayJs), '--config', (Quote $gwConfig), '--apiKeyFile', (Quote $KeyPath), '--exitWithProcess', $PID, '--logLevel', 'info') }
      'files'   { $exe = $Conf.node_path; $argv = @((Quote $FilesServer), '--http', $FilesPort, '--parent-pid', $PID) }
      'tunnel'  {
        if ($Conf.tunnel -eq 'ngrok') {
          $exe = $Conf.ngrok_path; $argv = @('http', "127.0.0.1:$($Conf.port)", '--log', 'stdout', '--log-format', 'json')
          if ($Conf.ngrok_domain) { $argv += @('--url', "https://$($Conf.ngrok_domain)") }
        } else {
          $exe = Get-Cloudflared
          $argv = @('tunnel', '--no-autoupdate', '--metrics', "127.0.0.1:$MetricsPort", '--url', "http://127.0.0.1:$($Conf.port)")
        }
      }
    }
    $p = Start-Process -FilePath $exe -ArgumentList $argv -NoNewWindow -PassThru -RedirectStandardOutput $log -RedirectStandardError $err
    [void]$p.Handle   # keeps the handle so ExitCode is readable after the process exits
    $meta[$name].started = Get-Date
    return $p
  }

  # Public URL of a tunnel that has no fixed domain (read from its log).
  function Find-TunnelUrl {
    $log = Join-Path $LogDir 'tunnel.log'; $err = Join-Path $LogDir 'tunnel.err.log'
    if ($Conf.tunnel -eq 'cloudflare') {
      $m = Select-String -LiteralPath $err -Pattern 'https://[a-z0-9-]+\.trycloudflare\.com' -ErrorAction SilentlyContinue | Select-Object -First 1
      if ($m) { return $m.Matches[0].Value }
    } else {
      $line = Select-String -LiteralPath $log -Pattern 'started tunnel' -ErrorAction SilentlyContinue | Select-Object -First 1
      if ($line) { $m = [regex]::Match($line.Line, '"url":"(https://[^"]+)"'); if ($m.Success) { return $m.Groups[1].Value } }
    }
    return $null
  }
  function Get-TunnelError {
    foreach ($f in (Join-Path $LogDir 'tunnel.log'), (Join-Path $LogDir 'tunnel.err.log')) {
      $m = Select-String -LiteralPath $f -Pattern 'ERR_NGROK_\d+|failed to|error' -ErrorAction SilentlyContinue | Select-Object -Last 1
      if ($m) { $t = $m.Line; if ($t.Length -gt 160) { $t = $t.Substring(0, 160) }; return ($t -replace '"', "'") }
    }
    return $null
  }
  function Save-Session([string]$state) {
    $pids = @{ supervisor = $PID; started_at = $startedAt
      gateway = $(if ($kids.gateway) { $kids.gateway.Id } else { $null })
      files = $(if ($kids.files) { $kids.files.Id } else { $null })
      tunnel = $(if ($kids.tunnel) { $kids.tunnel.Id } else { $null }) }
    $st.last = Build-Session $key $st.public $state $pids $st.tunnelError
    Write-Secret $SessionPath ($st.last | ConvertTo-Json)
  }
  function Test-TunnelUp {
    if ($Conf.tunnel -eq 'cloudflare') { return ((Get-HttpCode "http://127.0.0.1:$MetricsPort/ready" 2) -eq 200) }
    return ($st.public -and (Get-HttpCode "$($st.public)/healthz" 5) -eq 200)
  }
  function Wait-Tunnel([int]$sec) {
    $deadline = (Get-Date).AddSeconds($sec)
    while ((Get-Date) -lt $deadline) {
      if ($kids.tunnel.HasExited) { return $false }
      if (-not $Conf.ngrok_domain -or $Conf.tunnel -eq 'cloudflare') {
        $u = Find-TunnelUrl
        if ($u -and $u -ne $st.public) { $st.public = $u; Log "Tunnel URL: $u" }
      }
      if ($st.public -and (Test-TunnelUp)) { return $true }
      Start-Sleep -Milliseconds 500
    }
    return $false
  }

  $t0 = Get-Date
  try {
    Log "Starting supergateway on 127.0.0.1:$($Conf.port)..."
    $kids.gateway = Start-Child 'gateway'
    $up = $false
    for ($i = 0; $i -lt 100 -and -not $up; $i++) { Start-Sleep -Milliseconds 100; if ($kids.gateway.HasExited) { break }; $up = Test-Tcp $Conf.port 200 }
    if (-not $up) { Fail ('supergateway did not start: ' + ((Get-Content (Join-Path $LogDir 'gateway.err.log') -Tail 5 -ErrorAction SilentlyContinue) -join ' | ')) }
    if ($Conf.files) { $kids.files = Start-Child 'files' }
    if ($Conf.tunnel -ne 'none') {
      Log "Starting the $($Conf.tunnel) tunnel..."
      $kids.tunnel = Start-Child 'tunnel'
      if (-not (Wait-Tunnel 30)) {
        $st.tunnelError = $(Get-TunnelError); if (-not $st.tunnelError) { $st.tunnelError = 'tunnel not answering' }
        Log "The tunnel is not answering yet: $($st.tunnelError)"
      }
    }
    $state = $(if ($Conf.tunnel -eq 'none' -or ($st.public -and -not $st.tunnelError)) { 'ready' } else { 'degraded' })
    Save-Session $state
    Log ("Bridge {0} in {1:N1} s at {2}" -f $state, ((Get-Date) - $t0).TotalSeconds, $st.last.public_url)
    if ($Interactive) { Write-SessionLines $st.last; Log "Ctrl+C (or the 'stop' command) stops it." }

    $tick = 0; $gwMisses = 0; $tunMisses = 0
    while ($true) {
      Start-Sleep -Milliseconds 1000
      $tick++
      if (Test-Path $StopFile) { Log 'Stop requested.'; break }
      $changed = $false
      foreach ($name in 'gateway', 'files', 'tunnel') {
        $p = $kids[$name]
        if ($null -eq $p -or -not $p.HasExited) { continue }
        $m = $meta[$name]
        if ((Get-Date) -lt $m.next) { continue }
        if (((Get-Date) - $m.started).TotalSeconds -gt 120) { $m.fails = 0 }
        $m.fails++
        $delay = @(1, 2, 5, 10, 30)[[Math]::Min($m.fails - 1, 4)]
        $m.next = (Get-Date).AddSeconds($delay)
        Log "$name exited (code $($p.ExitCode)); restarting (attempt $($m.fails))."
        if ($name -eq 'gateway') {
          for ($i = 0; $i -lt 30 -and (Test-Tcp $Conf.port 100); $i++) { Start-Sleep -Milliseconds 200 }
        }
        if ($name -eq 'tunnel' -and ($Conf.tunnel -eq 'cloudflare' -or -not $Conf.ngrok_domain)) {
          $st.public = $null   # a new tunnel without a fixed domain gets a new URL: read it from the new log
        }
        $kids[$name] = Start-Child $name
        if ($name -eq 'tunnel') {
          if (Wait-Tunnel 30) { $st.tunnelError = $null } else {
            $st.tunnelError = $(Get-TunnelError); if (-not $st.tunnelError) { $st.tunnelError = 'tunnel not answering' } }
        }
        $changed = $true
      }
      # Liveness: a gateway that stops accepting connections, a tunnel that stops answering.
      if ($tick % 2 -eq 0) { if (Test-Tcp $Conf.port 500) { $gwMisses = 0 } else { $gwMisses++ } }
      if ($gwMisses -ge 3) { Log 'Gateway not answering; restarting it.'; Stop-Tree $kids.gateway.Id; $gwMisses = 0 }
      if ($Conf.tunnel -ne 'none' -and $tick % 30 -eq 0 -and $kids.tunnel -and -not $kids.tunnel.HasExited) {
        if (Test-TunnelUp) {
          if ($tunMisses -gt 0 -or $st.tunnelError) { $st.tunnelError = $null; $changed = $true }
          $tunMisses = 0
        } else {
          $tunMisses++
          if ($tunMisses -ge 3) { Log 'Tunnel not answering; restarting it.'; Stop-Tree $kids.tunnel.Id; $tunMisses = 0 }
        }
      }
      if ($changed) {
        $state = $(if ($Conf.tunnel -eq 'none' -or ($st.public -and -not $st.tunnelError)) { 'ready' } else { 'degraded' })
        Save-Session $state
      }
    }
  } finally {
    Log 'Shutting down...'
    Stop-Tree @($kids.Values | Where-Object { $_ } | ForEach-Object { $_.Id })
    if (Test-Path -LiteralPath $SessionPath) { try { Save-Session 'stopped' } catch { } }
    Remove-Item -Force $StopFile -ErrorAction SilentlyContinue
    $mutex.ReleaseMutex(); $mutex.Dispose()
    Log 'Stopped.'
  }
}

# ---------------------------------------------------------------------------------------
# Service commands
# ---------------------------------------------------------------------------------------
function Wait-Ready([int]$sec, [datetime]$since) {
  $deadline = (Get-Date).AddSeconds($sec)
  while ((Get-Date) -lt $deadline) {
    $s = Read-Json $SessionPath
    $upd = Get-Prop $s 'updated_at' $null
    if ($s -and $upd -and ([datetime]::Parse($upd).ToUniversalTime() -ge $since.ToUniversalTime().AddSeconds(-1)) -and (Get-Prop $s 'state' '') -in 'ready', 'degraded') {
      $p = Get-Process -Id (Get-Prop $s 'supervisor_pid' 0) -ErrorAction SilentlyContinue
      if ($p) { return $s }
    }
    Start-Sleep -Milliseconds 300
  }
  return $null
}

function Invoke-Stop([bool]$hold) {
  if ($hold) { Write-Utf8 $StoppedFlag (Get-Date).ToString('o') }
  $s = Read-Json $SessionPath
  $supPid = Get-Prop $s 'supervisor_pid' $null
  if ($supPid -and (Get-Process -Id $supPid -ErrorAction SilentlyContinue)) {
    Write-Utf8 $StopFile 'stop'
    for ($i = 0; $i -lt 40 -and (Get-Process -Id $supPid -ErrorAction SilentlyContinue); $i++) { Start-Sleep -Milliseconds 250 }
    if (Get-Process -Id $supPid -ErrorAction SilentlyContinue) {
      Log "Supervisor $supPid did not stop in 10 s; killing it."
      Stop-Tree $supPid (Get-Prop $s 'gateway_pid' $null) (Get-Prop $s 'files_pid' $null) (Get-Prop $s 'tunnel_pid' $null)
    }
  }
  Remove-Item -Force $StopFile -ErrorAction SilentlyContinue
}

function Invoke-Start {
  Log 'start: launching the supervisor.'
  Remove-Item -Force $StoppedFlag, $StopFile -ErrorAction SilentlyContinue
  $since = Get-Date
  if (Test-Task) {
    Invoke-Quiet { & schtasks.exe /Run /TN "$TaskPath$($Conf.task_name)" 2>&1 | Out-Null }
  } else {
    $argv = @('-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-WindowStyle', 'Hidden', '-File', (Quote $PSCommandPath), 'run', '-FromTask')
    Start-Process -FilePath 'powershell.exe' -ArgumentList $argv -WindowStyle Hidden | Out-Null
  }
  $s = Wait-Ready 45 $since
  if (-not $s) {
    Out-Result 'error' ('the bridge did not come up in 45 s. Last log lines: ' + ((Get-Content (Join-Path $LogDir 'supervisor.log') -Tail 4 -ErrorAction SilentlyContinue) -join ' | '))
    exit 1
  }
  Write-SessionLines $s
}

function Invoke-InstallService {
  Resolve-Tunnel
  if ($Conf.tunnel -eq 'ngrok' -and $Conf.ngrok_path -and $env:NGROK_AUTHTOKEN -and -not (Test-NgrokConfigured $Conf.ngrok_path)) {
    # Applied once; ngrok keeps it in its own config. Never echoed.
    Invoke-Quiet { & $Conf.ngrok_path config add-authtoken $env:NGROK_AUTHTOKEN 2>&1 | Out-Null }
    Log 'ngrok authtoken saved to the ngrok config.'
  }
  Save-Config
  Install-Runtime
  [void](Get-Key)
  Invoke-Stop $false
  $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ("-NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$PSCommandPath`" run -FromTask")
  $user = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
  $atLogon = New-ScheduledTaskTrigger -AtLogOn -User $user
  $repeat = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5) -RepetitionDuration (New-TimeSpan -Days 3650)
  $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -Hidden
  $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
  Register-ScheduledTask -TaskPath $TaskPath -TaskName $Conf.task_name -Action $action -Trigger @($atLogon, $repeat) `
    -Settings $settings -Principal $principal -Description 'grok-studio bridge: Roblox Studio for the cloud bot team (start-bridge.ps1).' -Force | Out-Null
  Log "Scheduled Task $TaskPath$($Conf.task_name) installed (at logon + a 5-minute keep-alive)."
  Invoke-Start
}

function Invoke-UninstallService {
  Invoke-Stop $false
  if (Test-Task) {
    Invoke-Quiet { & schtasks.exe /Delete /TN "$TaskPath$($Conf.task_name)" /F 2>&1 | Out-Null }
    Log "Scheduled Task $TaskPath$($Conf.task_name) removed."
  }
  try {
    $svc = New-Object -ComObject 'Schedule.Service'; $svc.Connect()
    $folder = $svc.GetFolder($TaskPath.TrimEnd('\'))
    if ($folder.GetTasks(1).Count -eq 0) { $svc.GetFolder('\').DeleteFolder($TaskPath.Trim('\'), 0) }
  } catch { }
  Remove-Item -Force $SessionPath, $StoppedFlag -ErrorAction SilentlyContinue
  if ($Purge) {
    foreach ($p in $KeyPath, $ConfigPath, $LogDir, $RunDir, $BinDir, (Join-Path $BridgeDir 'node_modules')) {
      Remove-Item -Recurse -Force -LiteralPath $p -ErrorAction SilentlyContinue
    }
  }
  Out-Result 'uninstalled'
}

switch ($Command) {
  'run'               { Invoke-Run }
  'install-service'   { Invoke-InstallService }
  'uninstall-service' { Invoke-UninstallService }
  'start'             { Resolve-Tunnel; Save-Config; if ($RotateKey) { [void](Get-Key) }; Invoke-Start }
  'stop'              { Invoke-Stop $true; Out-Result 'stopped' }
  'restart'           { Resolve-Tunnel; Save-Config; Invoke-Stop $false; if ($RotateKey) { [void](Get-Key) }; Invoke-Start }
  'status'            { $o = Get-Status ([bool]$Deep); Out-Line ($o | ConvertTo-Json -Compress:([bool]$JsonOutput)); if (-not $o.running) { exit 3 } elseif (-not ($o.gateway_up -and $o.tunnel_up -and $o.files_up)) { exit 1 } }
  'session'           {
    $s = Read-Json $SessionPath
    if (-not $s) { Out-Result 'none' 'no session yet: run start or install-service'; exit 3 }
    $st = Get-Status $false
    $s.state = $st.state
    Write-SessionLines $s
  }
}
