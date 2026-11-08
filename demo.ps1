param(
    [switch]$Setup,
    [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
Push-Location $PSScriptRoot
try {
    $env:UV_CACHE_DIR = Join-Path $PSScriptRoot '.uv-cache'
    $env:MPLCONFIGDIR = Join-Path $PSScriptRoot '.mplconfig'
    $env:PYTHONUTF8 = '1'
    $python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
    $astra = Join-Path $PSScriptRoot '.venv\Scripts\astra.exe'
    if ($Setup -or !(Test-Path -LiteralPath $python)) {
        if (!(Test-Path -LiteralPath $python)) {
            uv venv --python 3.12 .venv
            if ($LASTEXITCODE -ne 0) { throw 'Could not create the Python environment.' }
        }
        uv pip sync --python $python --require-hashes requirements.txt
        if ($LASTEXITCODE -ne 0) { throw 'Could not install the locked dependencies.' }
    }
    & $astra --version
    if ($LASTEXITCODE -ne 0) { throw 'Could not run ASTRA; try -Setup.' }
    & $astra info
    if ($LASTEXITCODE -ne 0) { throw 'ASTRA could not read the analysis.' }
    & $astra viz
    if ($LASTEXITCODE -ne 0) { throw 'ASTRA could not render the decisions.' }
    $runArgs = @('run_demo.py')
    if ($DryRun) { $runArgs += '--dry-run' }
    & $python @runArgs
    if ($LASTEXITCODE -ne 0) { throw 'The demonstration failed.' }
} finally {
    Pop-Location
}
