Run:
  powershell -ExecutionPolicy Bypass -File .\run-trial.ps1

Stop:
  powershell -ExecutionPolicy Bypass -File .\run-trial.ps1 -Stop

The trial copies the installed qBittorrent runtime into this folder and uses
an isolated profile. It does not modify Cinema Paradiso or the installed
qBittorrent profile.
