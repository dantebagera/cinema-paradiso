@echo off
setlocal
set "ZIP="
set "DEST="

:parse
if "%~1"=="" goto run
if "%~1"=="-d" (
  set "DEST=%~2"
  shift
  shift
  goto parse
)
if "%~1"=="-qo" (
  shift
  goto parse
)
if "%~1"=="-q" (
  shift
  goto parse
)
if "%~1"=="-o" (
  shift
  goto parse
)
if "%ZIP%"=="" set "ZIP=%~1"
shift
goto parse

:run
if "%DEST%"=="" set "DEST=."
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -LiteralPath '%ZIP%' -DestinationPath '%DEST%' -Force"
