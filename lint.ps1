$ErrorActionPreference = 'Continue'

$Root = $PSScriptRoot
Set-Location $Root

$agent = Join-Path $Root 'hardware-agent'

# Formatters are scoped to hardware-agent/, matching .pre-commit-config.yaml. backend/
# has never been formatted by black or ruff format; running either over the repo root
# rewrites ~32 backend files that have nothing to do with the change being linted.
# backend/ is gated by `cd backend; uv run ruff check src tests` instead.
Write-Host '== Black =='
python -m black $agent
$blackFail = $LASTEXITCODE

Write-Host '== Ruff format =='
python -m ruff format $agent
$ruffFormatFail = $LASTEXITCODE

Write-Host '== Ruff check =='
python -m ruff check $agent
$ruffFail = $LASTEXITCODE

if ($blackFail -ne 0 -or $ruffFormatFail -ne 0 -or $ruffFail -ne 0) {
    Write-Host ''
    Write-Host 'Lint failed.'
    exit 1
}

Write-Host 'Lint passed.'
