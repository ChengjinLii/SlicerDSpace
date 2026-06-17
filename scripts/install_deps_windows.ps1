$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $env:PYTHON_BIN -and $env:SLICER_EXECUTABLE) {
  $slicerDir = Split-Path -Parent $env:SLICER_EXECUTABLE
  $pythonSlicerExe = Join-Path $slicerDir "PythonSlicer.exe"
  $pythonSlicer = Join-Path $slicerDir "PythonSlicer"
  if (Test-Path $pythonSlicerExe) {
    $env:PYTHON_BIN = $pythonSlicerExe
  }
  elseif (Test-Path $pythonSlicer) {
    $env:PYTHON_BIN = $pythonSlicer
  }
}
if (-not $env:PYTHON_BIN) {
  $env:PYTHON_BIN = "python"
}

& $env:PYTHON_BIN "$ScriptDir/install_dependencies.py" --all @args
