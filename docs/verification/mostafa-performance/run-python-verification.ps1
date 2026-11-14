$ErrorActionPreference = 'Stop'
$root = 'C:\Users\dante\.codex\worktrees\mostafa-ui-ux\cinema paradiso'
$evidence = Join-Path $root 'docs\verification\mostafa-performance'
$testRoot = Join-Path ([IO.Path]::GetTempPath()) ('cp-performance-python-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $testRoot | Out-Null
$env:CP_TEST_MODE = '1'
$env:CP_TEST_ROOT = $testRoot
$env:CP_TEST_QBT_MODE = 'embedded'
$env:CP_TEST_DIST_DIR = Join-Path $testRoot 'dist'
$env:CP_PORT = '5136'
$python = Join-Path $root '.venv\Scripts\python.exe'
Write-Output "Isolated root: $testRoot"
& npm.cmd run build -- --outDir $env:CP_TEST_DIST_DIR *> (Join-Path $evidence 'python-build.log')
if ($LASTEXITCODE -ne 0) { Get-Content -LiteralPath (Join-Path $evidence 'python-build.log') -Tail 20; exit $LASTEXITCODE }
& $python -m unittest tests.test_unified_movie_card_ui tests.test_full_row_card_grids_ui tests.test_workspace_layout_ui tests.test_library_action_ux tests.test_tv_list_filters tests.test_tv_credit_portraits tests.test_ui_preview_launcher *> (Join-Path $evidence 'python-focused.log')
$focusedExit = $LASTEXITCODE
Get-Content -LiteralPath (Join-Path $evidence 'python-focused.log') -Tail 12
& $python -m unittest discover -s tests -p 'test_*.py' *> (Join-Path $evidence 'python-full.log')
$fullExit = $LASTEXITCODE
Get-Content -LiteralPath (Join-Path $evidence 'python-full.log') -Tail 35
@{ isolatedRoot = $testRoot; focusedExit = $focusedExit; fullExit = $fullExit; dist = $env:CP_TEST_DIST_DIR } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $evidence 'python-result.json')
exit $fullExit
