param([string]$Label='qml')
$ErrorActionPreference='Stop'
$taskRoot=Join-Path $env:TEMP 'cp-player-menu-usability-20261024'
$qtRoot=Join-Path $taskRoot 'qt/6.10.3/msvc2022_64'
$buildRoot=Join-Path $taskRoot 'ui-build'
$mpvRoot=Join-Path $env:TEMP 'cp-player-unicode-20261022/mpv'
$vsRoot='C:\Program Files\Microsoft Visual Studio\2022\Community'
$dev=Join-Path $vsRoot 'Common7/Tools/VsDevCmd.bat'
$cmake=Join-Path $vsRoot 'Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe'
$ninja=Join-Path $vsRoot 'Common7/IDE/CommonExtensions/Microsoft/CMake/Ninja/ninja.exe'
$ctest=Join-Path (Split-Path $cmake) 'ctest.exe'
$source=Join-Path (Get-Location) 'native/player'
$command='call "'+$dev+'" -arch=x64 -host_arch=x64 && "'+$cmake+'" -S "'+$source+'" -B "'+$buildRoot+'" -G Ninja -DCMAKE_BUILD_TYPE=Release -DCP_PLAYER_BUILD_TESTS=ON "-DCMAKE_PREFIX_PATH='+$qtRoot+'" "-DCMAKE_MAKE_PROGRAM='+$ninja+'" "-DMPV_ROOT='+$mpvRoot+'" && "'+$cmake+'" --build "'+$buildRoot+'" --target cp-player-ui-tests --parallel 4'
& cmd.exe /d /s /c $command *> "docs/verification/native-player-menu-usability/$Label-build.log"
if($LASTEXITCODE -ne 0){Get-Content "docs/verification/native-player-menu-usability/$Label-build.log" -Tail 25; exit 1}
$env:PATH="$qtRoot/bin;"+$env:PATH
$env:QT_SCALE_FACTOR='1'
$env:QT_PLUGIN_PATH="$qtRoot/plugins"
$env:QML_IMPORT_PATH="$qtRoot/qml"
$env:APPDATA="$taskRoot/ui-roaming"; $env:LOCALAPPDATA="$taskRoot/ui-local"
$env:CP_TEST_MODE='1'; $env:CP_TEST_ROOT="$taskRoot/ui-data"
& $ctest --test-dir $buildRoot --output-on-failure -R player-ui *> "docs/verification/native-player-menu-usability/$Label.log"
Copy-Item -LiteralPath "$buildRoot/player-ui.txt" -Destination "docs/verification/native-player-menu-usability/$Label-details.log" -Force
Get-Content "docs/verification/native-player-menu-usability/$Label-details.log" -Tail 65
exit $LASTEXITCODE
