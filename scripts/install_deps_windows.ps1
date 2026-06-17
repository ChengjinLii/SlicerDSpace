$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not $env:PYTHON_BIN -and $env:SLICER_EXECUTABLE) {
    $SlicerDir = Split-Path -Parent $env:SLICER_EXECUTABLE
    $PythonSlicerExe = Join-Path $SlicerDir "PythonSlicer.exe"
    $PythonSlicer = Join-Path $SlicerDir "PythonSlicer"
    if (Test-Path $PythonSlicerExe) {
        $env:PYTHON_BIN = $PythonSlicerExe
    } elseif (Test-Path $PythonSlicer) {
        $env:PYTHON_BIN = $PythonSlicer
    }
}

if (-not $env:PYTHON_BIN) {
    $env:PYTHON_BIN = "python"
}

& $env:PYTHON_BIN (Join-Path $ScriptDir "install_dependencies.py") --all @args
