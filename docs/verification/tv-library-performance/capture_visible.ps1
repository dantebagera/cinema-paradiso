param(
  [Parameter(Mandatory=$true)][ValidateSet('baseline','candidate')][string]$Version,
  [Parameter(Mandatory=$true)][ValidateSet('library','discover')][string]$Scope,
  [Parameter(Mandatory=$true)][string]$CompiledDist
)
$ErrorActionPreference='Stop'
$repo=(Get-Location).Path
$root=[IO.Path]::GetFullPath($env:CP_TEST_ROOT)
$dist=[IO.Path]::GetFullPath($env:CP_TEST_DIST_DIR)
$sourceDist=[IO.Path]::GetFullPath($CompiledDist)
$evidence=[IO.Path]::GetFullPath($env:CP_TV_PERF_EVIDENCE)
if(-not $dist.StartsWith($root+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'Dist escaped case root'}
if(-not $sourceDist.StartsWith($evidence+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'Source dist escaped evidence root'}
if(Get-NetTCPConnection -State Listen -LocalPort 5135 -ErrorAction SilentlyContinue){throw 'Diagnostic port already owned'}
Copy-Item -LiteralPath $sourceDist -Destination $dist -Recurse
$env:CP_PORT='5135'
if($Version -eq 'baseline'){$env:CP_TV_DIAG_BASELINE_SOURCE=Join-Path $evidence 'baseline'}
else{Remove-Item -LiteralPath 'Env:CP_TV_DIAG_BASELINE_SOURCE' -ErrorAction SilentlyContinue}
$backendSource=if($Version -eq 'baseline'){Join-Path $evidence 'baseline\services\tv_search.py'}else{Join-Path $repo 'services\tv_search.py'}
function FileSha256([string]$file){
  $sha=[Security.Cryptography.SHA256]::Create();$stream=[IO.File]::OpenRead($file)
  try{return [BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-','')}finally{$stream.Dispose();$sha.Dispose()}
}
@{version=$Version;scope=$Scope;backend_sha256=(FileSha256 $backendSource);frontend_index_sha256=(FileSha256 (Join-Path $dist 'index.html'));data_mode='ro/query_only';startup_writers=$false;movie_results='empty fixture';browser='fresh headless Chromium 1365x900; visible lifecycle'}|ConvertTo-Json|Set-Content (Join-Path $root 'capture-manifest.json')
$server=$null
try{
  $server=Start-Process -FilePath (Join-Path $repo '.venv\Scripts\python.exe') -ArgumentList @('docs\verification\tv-library-performance\visible_server.py') -WorkingDirectory $repo -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $root 'server.log') -RedirectStandardError (Join-Path $root 'server-error.log')
  $deadline=[DateTime]::UtcNow.AddSeconds(15)
  $ready=$false
  while([DateTime]::UtcNow -lt $deadline){
    if($server.HasExited){throw 'Owned diagnostic exited during startup'}
    try{$response=Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:5135/__cp_tab_probe.js' -TimeoutSec 1;if($response.StatusCode -eq 200){$ready=$true;break}}catch{}
    Start-Sleep -Milliseconds 200
  }
  if(-not $ready){throw 'Bounded diagnostic readiness expired'}
  & node.exe docs\verification\tv-library-performance\capture_visible.mjs 'http://127.0.0.1:5135' $Scope
  exit $LASTEXITCODE
}finally{
  if($server){$server.Refresh();if(-not $server.HasExited){& taskkill.exe /PID $server.Id /T /F}}
}
