# Dante explicitly authorized shutdown after the performance repair is complete.
# The delay allows the saved report and final chat response to finish writing.
$ErrorActionPreference = 'Stop'
$recordPath = 'C:\Users\dante\.codex\worktrees\mostafa-ui-ux\cinema paradiso\docs\verification\mostafa-performance\shutdown-dispatch.json'
$record = @{ authorizedBy = 'Dante'; repairReport = 'docs/verification/mostafa-performance/RESULT.md'; scheduledAtUtc = [DateTime]::UtcNow.ToString('o'); delaySeconds = 45; command = 'shutdown.exe /s /t 0'; forcedApplicationClosure = $false; status = 'scheduled' }
$record | ConvertTo-Json | Set-Content -LiteralPath $recordPath
Start-Sleep -Seconds 45
$record['requestedAtUtc'] = [DateTime]::UtcNow.ToString('o')
$record['status'] = 'requesting'
$record | ConvertTo-Json | Set-Content -LiteralPath $recordPath
& "$env:SystemRoot\System32\shutdown.exe" /s /t 0
$record['exitCode'] = $LASTEXITCODE
$record['status'] = if ($LASTEXITCODE -eq 0) { 'request_accepted' } else { 'request_failed' }
$record | ConvertTo-Json | Set-Content -LiteralPath $recordPath
