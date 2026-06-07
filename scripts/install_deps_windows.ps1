$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $env:PYTHON_BIN) {
  $env:PYTHON_BIN = "python"
}

& $env:PYTHON_BIN "$ScriptDir/install_dependencies.py" --all @args
