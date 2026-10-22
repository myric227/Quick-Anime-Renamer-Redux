$ErrorActionPreference = 'Stop'
$projectPath = $PSScriptRoot
$pythonPath = Join-Path $projectPath '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw 'Create .venv and install requirements-build.txt before building.'
}

$previousPath = $env:PATH
Push-Location -LiteralPath $projectPath
try {
    $pythonBase = & $pythonPath -c 'import sys; print(sys.base_prefix)'
    if ($LASTEXITCODE -ne 0) { throw 'Cannot locate the Python installation.' }
    # Avoid collecting incompatible DLLs from unrelated programs on PATH.
    $env:PATH = "$pythonBase;$pythonBase\Scripts;$env:SystemRoot\System32;$env:SystemRoot"
    & $pythonPath -m PyInstaller --clean --noconfirm --onefile --windowed `
        --icon=quick_anime_renamer_redux.ico `
        --add-data 'quick_anime_renamer_redux.ico;.' quick_anime_renamer_redux.py
    if ($LASTEXITCODE -ne 0) { throw 'Executable build failed.' }
}
finally {
    $env:PATH = $previousPath
    Pop-Location
}
