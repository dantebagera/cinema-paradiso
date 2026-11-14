[CmdletBinding(PositionalBinding=$false)]
param(
    [switch]$AIProviderOffline,
    [string]$AICompiledDist,
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$PlaywrightArguments
)
$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$temporaryRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\')
$isolatedRoot = [IO.Path]::GetFullPath(
    (Join-Path $temporaryRoot ('cinema-paradiso-playwright-' + [guid]::NewGuid().ToString('N')))
)
if (-not $isolatedRoot.StartsWith($temporaryRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to create Playwright data outside the operating-system temporary directory: $isolatedRoot"
}

New-Item -ItemType Directory -Path $isolatedRoot | Out-Null
$stdoutPath = Join-Path $isolatedRoot 'server.stdout.log'
$stderrPath = Join-Path $isolatedRoot 'server.stderr.log'
$isolatedDist = Join-Path $isolatedRoot 'dist'
$server = $null
$testExitCode = 1

$env:CP_PORT = '5117'
$env:CP_TEST_MODE = '1'
$env:CP_TEST_ROOT = $isolatedRoot
$env:CP_TEST_QBT_MODE = if ($AIProviderOffline) { 'embedded' } else { 'system' }
$env:CP_TEST_DIST_DIR = $isolatedDist
Write-Output "CP_TEST_ROOT=$isolatedRoot"

try {
    if (Get-NetTCPConnection -LocalPort 5117 -State Listen -ErrorAction SilentlyContinue) {
        throw 'Port 5117 is already owned by another process.'
    }
    $python = Join-Path $projectRoot '.venv\Scripts\python.exe'
    if (-not $AIProviderOffline) {
    & $python -m tests.seed_iptv_e2e $isolatedRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Could not create isolated IPTV provider fixtures."
    }
    & $python -m tests.seed_movie_awards_e2e $isolatedRoot
    if ($LASTEXITCODE -ne 0) { throw 'Could not create isolated awards fixtures.' }
    }
    if ($AICompiledDist) {
        $compiledSource = [IO.Path]::GetFullPath($AICompiledDist)
        if (-not $AIProviderOffline -or -not $compiledSource.StartsWith($temporaryRoot + '\', [StringComparison]::OrdinalIgnoreCase) -or -not (Test-Path -LiteralPath (Join-Path $compiledSource 'index.html'))) {
            throw 'Compiled reuse requires an existing isolated AI fixture bundle in OS temp.'
        }
        Copy-Item -LiteralPath $compiledSource -Destination $isolatedDist -Recurse
    } else {
        & npm.cmd run build -- --outDir $isolatedDist
        if ($LASTEXITCODE -ne 0) { throw "Could not build the isolated Playwright frontend." }
    }
    $server = Start-Process `
        -FilePath $python `
        -ArgumentList $(if ($AIProviderOffline) { '-m tests.ai_provider_server' } elseif ($env:CP_DISCOVER_PAGING_E2E -eq '1') { '-m tests.discover_paging_server' } elseif ($env:CP_TV_E2E -eq '1') { '-m tests.native_tv_server' } else { 'app.py' }) `
        -WorkingDirectory $projectRoot `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath `
        -PassThru

    $ready = $false
    for ($attempt = 0; $attempt -lt 120; $attempt += 1) {
        if ($server.HasExited) {
            throw "Isolated Playwright server exited before becoming ready."
        }
        try {
            $response = Invoke-WebRequest `
                -Uri 'http://127.0.0.1:5117/api/library/status' `
                -UseBasicParsing `
                -TimeoutSec 2
            if ($response.StatusCode -eq 200) {
                $ready = $true
                break
            }
        } catch {
            Start-Sleep -Milliseconds 250
        }
    }
    if (-not $ready) {
        throw "Isolated Playwright server did not become ready within 30 seconds."
    }

    $playwright = Join-Path $projectRoot 'node_modules\.bin\playwright.cmd'
    & $playwright test @PlaywrightArguments
    $testExitCode = $LASTEXITCODE
} catch {
    Write-Error $_
    $testExitCode = 1
} finally {
    if ($server) {
        $trackedIds = [System.Collections.Generic.List[int]]::new()
        $trackedIds.Add([int]$server.Id)
        for ($index = 0; $index -lt $trackedIds.Count; $index += 1) {
            $parentId = $trackedIds[$index]
            Get-CimInstance Win32_Process -Filter "ParentProcessId=$parentId" -ErrorAction SilentlyContinue |
                ForEach-Object {
                    if (-not $trackedIds.Contains([int]$_.ProcessId)) {
                        $trackedIds.Add([int]$_.ProcessId)
                    }
                }
        }
        for ($index = $trackedIds.Count - 1; $index -ge 0; $index -= 1) {
            $processId = $trackedIds[$index]
            Stop-Process -Id $processId -Force -ErrorAction SilentlyContinue
            Wait-Process -Id $processId -Timeout 10 -ErrorAction SilentlyContinue
        }
    }

    if ($testExitCode -eq 0 -and -not $AIProviderOffline) {
        $resolvedRoot = [IO.Path]::GetFullPath($isolatedRoot)
        if (-not $resolvedRoot.StartsWith($temporaryRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
            throw "Refusing to remove an unverified Playwright directory: $resolvedRoot"
        }
        for ($attempt = 0; $attempt -lt 20; $attempt += 1) {
            try {
                Remove-Item -LiteralPath $resolvedRoot -Recurse -Force
                break
            } catch {
                if ($attempt -eq 19) { throw }
                Start-Sleep -Milliseconds 250
            }
        }
    } else {
        Write-Output "Playwright evidence retained at $isolatedRoot"
        if (Test-Path -LiteralPath $stderrPath) {
            Get-Content -LiteralPath $stderrPath -Tail 40
        }
    }
}

exit $testExitCode
