$ErrorActionPreference='Stop'
$timer=[Diagnostics.Stopwatch]::StartNew()
$repo=(Get-Location).Path
$root=[IO.Path]::GetFullPath($env:CP_TEST_ROOT)
$dist=[IO.Path]::GetFullPath($env:CP_TEST_DIST_DIR)
if(-not $dist.StartsWith($root+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'Dist escaped isolated root'}
if(Get-NetTCPConnection -State Listen -LocalPort 5127 -ErrorAction SilentlyContinue){throw 'Port 5127 is already owned'}
$server=$null
try {
  if($env:CP_TV_TESTED_DIST){
    $testedDist=[IO.Path]::GetFullPath($env:CP_TV_TESTED_DIST)
    $evidenceRoot=[IO.Path]::GetFullPath($env:CP_TV_PERF_EVIDENCE)
    if(-not $testedDist.StartsWith($evidenceRoot+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'Prebuilt dist escaped this evidence scope'}
    if(-not (Test-Path -LiteralPath (Join-Path $testedDist 'index.html'))){throw 'Missing tested prebuilt dist'}
    Copy-Item -LiteralPath $testedDist -Destination $dist -Recurse
    Write-Output "Reused unchanged compiled application: $testedDist"
  }else{
    & npm.cmd run build -- --outDir $dist
    if($LASTEXITCODE -ne 0){exit $LASTEXITCODE}
  }
  $env:CP_TV_E2E='1'; $env:CP_PORT='5127'; $env:CP_E2E_PORT='5127'; $env:CP_TEST_QBT_MODE='embedded'
  if($env:CP_TV_E2E_SEED_IPTV -eq '1'){
    & (Join-Path $repo '.venv\Scripts\python.exe') -m tests.seed_iptv_e2e $root
    if($LASTEXITCODE -ne 0){exit $LASTEXITCODE}
  }
  $env:CP_TV_E2E_ARTWORK=Join-Path $repo 'tests\fixtures\tv_artwork.svg'
  $server=Start-Process -FilePath (Join-Path $repo '.venv\Scripts\python.exe') -ArgumentList @('-m','tests.native_tv_server') -WorkingDirectory $repo -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $root 'server.log') -RedirectStandardError (Join-Path $root 'server-error.log')
  $deadline=[DateTime]::UtcNow.AddSeconds(15)
  $ready=$false
  while([DateTime]::UtcNow -lt $deadline){
    if($server.HasExited){throw 'Owned fixture server exited during startup'}
    try {$response=Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:5127/api/tv/capabilities' -TimeoutSec 1; if($response.StatusCode -eq 200){$ready=$true;break}}catch{}
    Start-Sleep -Milliseconds 250
  }
  if(-not $ready){throw 'One bounded fixture readiness check expired'}
  $specDir=Join-Path $root 'e2e'; New-Item -ItemType Directory -Path $specDir|Out-Null
  $moduleUri=([Uri](Join-Path $repo 'node_modules\@playwright\test\index.mjs')).AbsoluteUri
  $guard=@'
test.beforeEach(async ({ context }) => {
  await context.route('**/*', route => {
    const url = new URL(route.request().url());
    if (url.hostname === 'image.tmdb.org' && url.pathname.startsWith('/t/p/') && route.request().resourceType() === 'image') {
      return route.fulfill({ path: process.env.CP_TV_E2E_ARTWORK, contentType: 'image/svg+xml' });
    }
    if (['http:', 'https:'].includes(url.protocol) && !['127.0.0.1', 'localhost'].includes(url.hostname)) return route.abort();
    return route.continue();
  });
});
'@
  $specNames=@('tv-parity','native-tv','tv-expanded-parity','tv-stabilization','continue-watching','tv-first-load','tv-visible-load','card-artwork-performance')
  if($env:CP_TV_E2E_EXTRA_SPECS){$specNames+=($env:CP_TV_E2E_EXTRA_SPECS -split ',')}
  foreach($name in $specNames){
    $source=[IO.File]::ReadAllText((Join-Path $repo "tests\e2e\$name.spec.js"))
    $source=$source.Replace("from '@playwright/test';","from '$moduleUri';`n$guard")
    $source=$source.Replace("'docs/verification/","process.env.CP_TEST_ROOT + '/screenshots/docs/verification/")
    $source=$source.Replace('"docs/verification/','process.env.CP_TEST_ROOT + "/screenshots/docs/verification/')
    $source=$source.Replace('`docs/verification/','process.env.CP_TEST_ROOT + `/screenshots/docs/verification/')
    [IO.File]::WriteAllText((Join-Path $specDir "$name.spec.mjs"),$source,[Text.UTF8Encoding]::new($false))
  }
  $testDirJson=ConvertTo-Json -InputObject $specDir -Compress
  $config="import { defineConfig } from '$moduleUri';`nexport default defineConfig({testDir:$testDirJson,timeout:45000,expect:{timeout:15000},fullyParallel:false,workers:1,retries:0,reporter:[['list']],use:{baseURL:'http://127.0.0.1:5127',browserName:'chromium',headless:true,viewport:{width:1600,height:1000},trace:'retain-on-failure',screenshot:'only-on-failure'}});"
  $configPath=Join-Path $root 'playwright.config.mjs'; [IO.File]::WriteAllText($configPath,$config,[Text.UTF8Encoding]::new($false))
  $budget=Get-Content (Join-Path $env:CP_TV_PERF_EVIDENCE 'budget.json')|ConvertFrom-Json
  $remaining=$budget.limit_seconds-$budget.active_seconds-$timer.Elapsed.TotalSeconds-12
  if($remaining -le 0){throw 'Budget exhausted before desktop tests'}
  $globalLimit=[Math]::Floor($remaining*1000)
  Write-Output "Owned fixture server PID=$($server.Id); root=$root; desktop limit=$globalLimit ms"
  $arguments=@('test',"--config=$configPath",'--workers=1','--retries=0','--max-failures=1',"--output=$root\playwright-results","--global-timeout=$globalLimit")
  if($env:CP_TV_E2E_GREP){$arguments+=@('--grep',$env:CP_TV_E2E_GREP)}
  # Invoke Node directly: cmd wrappers interpret regex metacharacters such as |.
  & node.exe (Join-Path $repo 'node_modules\@playwright\test\cli.js') @arguments
  $code=$LASTEXITCODE
  Write-Output "DESKTOP_EXIT=$code"
  exit $code
} finally {
  if($server){$server.Refresh(); if(-not $server.HasExited){& taskkill.exe /PID $server.Id /T /F}}
}
