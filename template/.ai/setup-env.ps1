# Lanzador para Windows. La logica real vive en setup_env.py (portable).
$ErrorActionPreference = 'Stop'
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "uv no esta instalado. Instalalo con:" -ForegroundColor Red
    Write-Host "    winget install --id=astral-sh.uv -e"
    exit 1
}
& uv run --script "$PSScriptRoot\setup_env.py" @args
exit $LASTEXITCODE
