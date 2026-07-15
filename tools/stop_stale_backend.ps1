param(
    [string]$ProjectRoot = ".",
    [int]$Port = 5000
)

$ErrorActionPreference = "Stop"

function Get-PortOwners {
    @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique)
}

function Resolve-ExistingPath([string]$Path) {
    if (-not $Path) {
        return ""
    }
    try {
        return (Resolve-Path -LiteralPath $Path -ErrorAction Stop).Path
    } catch {
        return $Path
    }
}

$projectPath = (Resolve-Path -LiteralPath $ProjectRoot).Path.TrimEnd("\")
$projectVenv = Resolve-ExistingPath (Join-Path $projectPath ".venv\Scripts\python.exe")
$portOwners = @(Get-PortOwners)
$targets = @{}

$pythonAppProcesses = @(Get-CimInstance Win32_Process |
    Where-Object { $_.Name -eq "python.exe" -and $_.CommandLine -like "*app.py*" })

foreach ($process in $pythonAppProcesses) {
    $processPath = Resolve-ExistingPath $process.ExecutablePath
    $isProjectVenv = $processPath -and ($processPath -ieq $projectVenv)
    $ownsAppPort = $portOwners -contains $process.ProcessId

    if ($isProjectVenv -or $ownsAppPort) {
        $targets[[int]$process.ProcessId] = $process
    }
}

foreach ($processId in $targets.Keys) {
    $process = $targets[$processId]
    Write-Host "Stopping old backend PID $processId ($($process.ExecutablePath))"
    Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
}

for ($attempt = 0; $attempt -lt 20; $attempt++) {
    Start-Sleep -Milliseconds 200
    $remainingOwners = @(Get-PortOwners)
    if ($remainingOwners.Count -eq 0) {
        exit 0
    }
}

$remaining = @(Get-PortOwners)
if ($remaining.Count -gt 0) {
    Write-Host "Port $Port is still busy:"
    foreach ($processId in $remaining) {
        $process = Get-CimInstance Win32_Process -Filter "ProcessId = $processId" -ErrorAction SilentlyContinue
        if ($process) {
            Write-Host "PID $processId $($process.ExecutablePath) $($process.CommandLine)"
        } else {
            Write-Host "PID $processId"
        }
    }
    exit 1
}

exit 0
