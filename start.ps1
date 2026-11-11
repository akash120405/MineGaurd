$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$localPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
$bundledPython = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe'
$taskDeps = Join-Path $PSScriptRoot '../../work/deps'
if (Test-Path $localPython) {
  & $localPython run.py
} elseif ((Test-Path $bundledPython) -and (Test-Path $taskDeps)) {
  $env:PYTHONPATH = (Resolve-Path $taskDeps).Path
  & $bundledPython run.py
} else {
  Write-Host 'Create a Python 3.12 virtual environment and install requirements.txt first. See README.md.'
  exit 1
}
