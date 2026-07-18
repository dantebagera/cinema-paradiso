param(
    [switch]$Stop
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Runtime = Join-Path $Root "qbittorrent"
$Profile = Join-Path $Root "profile"
$State = Join-Path $Root ".trial-state.json"
$Installed = Join-Path $env:ProgramFiles "qBittorrent"

function Stop-TrialProcess {
    param([int]$ProcessId)
    if ($ProcessId -gt 0) {
        Stop-Process -Id $ProcessId -ErrorAction SilentlyContinue
        Wait-Process -Id $ProcessId -Timeout 10 -ErrorAction SilentlyContinue
    }
}

if ($Stop) {
    if (Test-Path -LiteralPath $State) {
        $running = Get-Content -Raw -LiteralPath $State | ConvertFrom-Json
        Stop-TrialProcess -ProcessId $running.serverPid
        Stop-TrialProcess -ProcessId $running.qbittorrentPid
        Remove-Item -LiteralPath $State -Force
    }
    Write-Host "Portable qBittorrent trial stopped."
    exit 0
}

if (-not (Test-Path -LiteralPath (Join-Path $Installed "qbittorrent.exe"))) {
    throw "Installed qBittorrent was not found at $Installed"
}

if (Test-Path -LiteralPath $State) {
    & $PSCommandPath -Stop
}

New-Item -ItemType Directory -Force -Path $Runtime, $Profile | Out-Null
$QbtExe = Join-Path $Runtime "qbittorrent.exe"

Get-Process "qbittorrent" -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -eq $QbtExe } |
    ForEach-Object { Stop-TrialProcess -ProcessId $_.Id }

$InstalledExe = Join-Path $Installed "qbittorrent.exe"
$RuntimeNeedsCopy = -not (Test-Path -LiteralPath $QbtExe)
if (-not $RuntimeNeedsCopy) {
    $RuntimeNeedsCopy = (Get-Item -LiteralPath $InstalledExe).VersionInfo.ProductVersion -ne
        (Get-Item -LiteralPath $QbtExe).VersionInfo.ProductVersion
}

if ($RuntimeNeedsCopy) {
    Copy-Item -LiteralPath $InstalledExe -Destination $Runtime -Force
    Copy-Item -LiteralPath (Join-Path $Installed "qbittorrent.pdb") -Destination $Runtime -Force
    Copy-Item -LiteralPath (Join-Path $Installed "qt.conf") -Destination $Runtime -Force
    Copy-Item -LiteralPath (Join-Path $Installed "translations") -Destination $Runtime -Recurse -Force
}

$ConfigDir = Join-Path $Profile "qBittorrent\config"
$ConfigFile = Join-Path $ConfigDir "qBittorrent.ini"
New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null

@"
[LegalNotice]
Accepted=true

[Preferences]
General\NoSplashScreen=true
General\StartMinimized=true
WebUI\Address=127.0.0.1
WebUI\CSRFProtection=true
WebUI\ClickjackingProtection=true
WebUI\Enabled=true
WebUI\HostHeaderValidation=true
WebUI\LocalHostAuth=false
WebUI\Password_PBKDF2="@ByteArray(Q2luZW1hUGFyYWRpc29RQg==:bbzhjahozapYNZI7ULs2iXFK1KRjOiriLlpLyLCNQYmgKcMZxpH4DprYX4QkvO8sGLDW0HfT+x0aA3ITri9xhg==)"
WebUI\Port=8080
WebUI\SecureCookie=false
WebUI\ServerDomains=127.0.0.1,localhost
WebUI\UseUPnP=false
WebUI\Username=admin
"@ | Set-Content -LiteralPath $ConfigFile -Encoding UTF8

$qbtArguments = "--profile=`"$Profile`" --webui-port=8080 --no-splash"
$qbt = Start-Process -FilePath $QbtExe -ArgumentList $qbtArguments -PassThru -WindowStyle Minimized

$ready = $false
for ($attempt = 0; $attempt -lt 40; $attempt++) {
    Start-Sleep -Milliseconds 250
    try {
        $response = Invoke-WebRequest -Uri "http://127.0.0.1:8080/api/v2/app/version" -UseBasicParsing -TimeoutSec 1
        if ($response.StatusCode -eq 200) {
            $ready = $true
            break
        }
    } catch {
    }
}

if (-not $ready) {
    Stop-TrialProcess -ProcessId $qbt.Id
    throw "Portable qBittorrent did not expose its WebUI on 127.0.0.1:8080."
}

$server = Start-Process -FilePath "python" -ArgumentList "`"$Root\trial_server.py`"" -WorkingDirectory $Root -PassThru -WindowStyle Hidden

@{
    qbittorrentPid = $qbt.Id
    serverPid = $server.Id
    qbittorrentExe = $QbtExe
    profile = $Profile
} | ConvertTo-Json | Set-Content -LiteralPath $State -Encoding UTF8

Start-Sleep -Milliseconds 500
Start-Process "http://127.0.0.1:8090/shell"
Write-Host "Portable qBittorrent trial started at http://127.0.0.1:8090/shell"
Write-Host "Stop it with: .\run-trial.ps1 -Stop"
