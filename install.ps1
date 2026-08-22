# Bootstrap Dmitri dev environment (hardware-agent + backend + frontend + local Supabase
# when available).
# Usage: .\install.ps1 [-AgentOnly] [-SkipVerify] [-Hooks]
param(
    [switch]$AgentOnly,
    [switch]$SkipVerify,
    [switch]$Hooks
)

$ErrorActionPreference = 'Stop'

$RepoRoot = $PSScriptRoot
$InfraOk = $false
$FrontendOk = $false

# Read the project id and port from config.toml rather than hardcoding them, so this
# keeps working if either is changed there. Same values database.sh parses.
$SupabaseConfig = Join-Path $RepoRoot 'supabase\config.toml'
$SupabaseProject = 'dmitri'
$SupabaseDbPort = '54322'
if (Test-Path $SupabaseConfig) {
    $configText = Get-Content $SupabaseConfig -Raw
    $projectMatch = [regex]::Match($configText, '(?m)^project_id\s*=\s*"([^"]+)"')
    if ($projectMatch.Success) { $SupabaseProject = $projectMatch.Groups[1].Value }
    $portMatch = [regex]::Match($configText, '(?ms)^\[db\].*?^port\s*=\s*(\d+)')
    if ($portMatch.Success) { $SupabaseDbPort = $portMatch.Groups[1].Value }
}
$SupabaseDbContainer = "supabase_db_$SupabaseProject"
$LocalDbUrl = "postgresql+psycopg://postgres:postgres@127.0.0.1:$SupabaseDbPort/postgres"
$TestDbUrl = "postgresql+psycopg://postgres:postgres@127.0.0.1:$SupabaseDbPort/dmitri_test"

function Write-Info([string]$Message) {
    Write-Host "==> $Message"
}

function Write-Warn([string]$Message) {
    Write-Warning $Message
}

function Write-Note([string]$Message) {
    Write-Host "note: $Message"
}

function Ensure-Uv {
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        Write-Info "uv already installed ($(uv --version))"
        return
    }

    Write-Info 'Installing uv...'
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression

    $uvBin = Join-Path $env:USERPROFILE '.local\bin'
    if (Test-Path $uvBin) {
        $env:Path = "$uvBin;$env:Path"
    }

    if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
        throw 'uv install finished but uv is not on PATH. Restart PowerShell and re-run .\install.ps1'
    }
    Write-Info "uv installed ($(uv --version))"
}

$UserBinDir = Join-Path $env:USERPROFILE '.local\bin'

function Ensure-UserBinOnPath {
    New-Item -ItemType Directory -Force -Path $UserBinDir | Out-Null
    if ($env:Path -notlike "*$UserBinDir*") {
        $env:Path = "$UserBinDir;$env:Path"
    }

    $userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
    if ($userPath -like "*$UserBinDir*") {
        return
    }

    if ([string]::IsNullOrWhiteSpace($userPath)) {
        $newPath = $UserBinDir
    } else {
        $newPath = "$UserBinDir;$userPath"
    }
    [Environment]::SetEnvironmentVariable('Path', $newPath, 'User')
    Write-Info "Added $UserBinDir to user PATH"
    Write-Note 'Restart PowerShell for PATH changes in other windows'
}

function Install-DmitriCli {
    $agentDir = Join-Path $RepoRoot 'hardware-agent'
    $wrapper = Join-Path $UserBinDir 'dmitri.cmd'

    Ensure-UserBinOnPath

    @"
@echo off
uv run --directory "$agentDir" dmitri %*
"@ | Set-Content -Encoding ASCII -Path $wrapper

    Write-Info "Installed dmitri launcher at $wrapper"
}

function Ensure-Nmap {
    if (Get-Command nmap -ErrorAction SilentlyContinue) {
        Write-Info "nmap already installed ($((nmap --version | Select-Object -First 1)))"
        return
    }

    Write-Info 'Installing nmap...'
    $installed = $false

    if (Get-Command winget -ErrorAction SilentlyContinue) {
        try {
            winget install -e --id Insecure.Nmap --accept-package-agreements --accept-source-agreements
            $installed = $true
        } catch {
            Write-Warn "winget nmap install failed: $_"
        }
    }

    if (-not $installed -and (Get-Command choco -ErrorAction SilentlyContinue)) {
        try {
            choco install nmap -y
            $installed = $true
        } catch {
            Write-Warn "choco nmap install failed: $_"
        }
    }

    if (Get-Command nmap -ErrorAction SilentlyContinue) {
        Write-Info "nmap installed ($((nmap --version | Select-Object -First 1)))"
        return
    }

    Write-Warn 'Could not auto-install nmap.'
    Write-Note 'Install from https://nmap.org/download.html or run: winget install -e --id Insecure.Nmap'
}

function Sync-PythonDeps {
    Write-Info 'Syncing hardware-agent dependencies (with dev extras)...'
    Push-Location (Join-Path $RepoRoot 'hardware-agent')
    try {
        uv sync --extra dev
    } finally {
        Pop-Location
    }

    if (-not $AgentOnly) {
        Write-Info 'Syncing backend dependencies (with dev extras)...'
        Push-Location (Join-Path $RepoRoot 'backend')
        try {
            uv sync --extra dev
        } finally {
            Pop-Location
        }
    }
}

function Seed-BackendEnv {
    if ($AgentOnly) { return }

    $envFile = Join-Path $RepoRoot 'backend\.env'
    $example = Join-Path $RepoRoot 'backend\.env.example'

    if (Test-Path $envFile) {
        Write-Note 'backend\.env already exists — not overwriting'
        return
    }
    if (-not (Test-Path $example)) {
        Write-Warn 'backend\.env.example missing — skipping .env seed'
        return
    }

    Copy-Item $example $envFile
    Write-Info 'Created backend\.env from backend\.env.example'
}

function Ensure-Node {
    if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
        Write-Warn 'Node.js not found — skipping frontend setup.'
        @'

Install Node 22.x, then re-run .\install.ps1:
  winget install -e --id OpenJS.NodeJS.LTS
  https://nodejs.org/en/download

'@ | Write-Host
        return $false
    }

    # frontend\package.json pins engines.node to 22.x. npm does not enforce it by
    # default, so a mismatch is a warning here rather than a hard stop.
    #
    # Parsed here rather than with `node -p`: PowerShell strips the inner double quotes
    # out of a native command's argument, so the script node actually received was
    # `process.versions.node.split(.)[0]` — a SyntaxError on every run.
    $nodeVersion = node --version
    $major = ($nodeVersion -replace '^v', '').Split('.')[0]
    if ($major -ne '22') {
        Write-Warn "Node $nodeVersion found; frontend\package.json pins engines.node to 22.x."
        Write-Note 'Continuing anyway — switch with: nvm use 22'
    } else {
        Write-Info "node $nodeVersion"
    }
    return $true
}

function Setup-Frontend {
    if ($AgentOnly) { return }
    if (-not (Ensure-Node)) { return }

    Write-Info 'Installing frontend dependencies...'
    Push-Location (Join-Path $RepoRoot 'frontend')
    try {
        npm install
    } finally {
        Pop-Location
    }

    $envFile = Join-Path $RepoRoot 'frontend\.env'
    $example = Join-Path $RepoRoot 'frontend\.env.example'
    if (Test-Path $envFile) {
        Write-Note 'frontend\.env already exists — not overwriting'
    } elseif (-not (Test-Path $example)) {
        Write-Warn 'frontend\.env.example missing — skipping .env seed'
    } else {
        Copy-Item $example $envFile
        Write-Info 'Created frontend\.env from frontend\.env.example'
    }

    $script:FrontendOk = $true
}

# Docker being installed but idle is the normal state on a dev machine, so start it
# rather than treating it as missing.
function Start-DockerDaemon {
    try {
        docker info *> $null
        if ($LASTEXITCODE -eq 0) { return $true }
    } catch { }

    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        return $false
    }

    $desktop = Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'
    if (-not (Test-Path $desktop)) {
        Write-Warn 'docker CLI found but Docker Desktop is not installed where expected — start Docker yourself and re-run.'
        return $false
    }

    Write-Info 'Docker is installed but not running — starting Docker Desktop...'
    Start-Process $desktop | Out-Null

    foreach ($_ in 1..90) {
        try {
            docker info *> $null
            if ($LASTEXITCODE -eq 0) {
                Write-Info 'Docker is up.'
                return $true
            }
        } catch { }
        Start-Sleep -Seconds 2
    }

    Write-Warn 'Docker did not come up within 180s.'
    return $false
}

function Print-DockerInstructions {
    Write-Warn 'Docker is not running or not installed — skipping Supabase and migrations.'
    @'

Install Docker Desktop, then re-run .\install.ps1 (without -AgentOnly):
  https://docs.docker.com/desktop/setup/install/windows-install/

'@ | Write-Host
}

function Print-SupabaseInstructions {
    Write-Warn 'Supabase CLI not found — skipping local Postgres setup.'
    @'

Install the Supabase CLI, then re-run .\install.ps1:
  scoop install supabase
  https://supabase.com/docs/guides/local-development/cli/getting-started

'@ | Write-Host
}

function Invoke-Psql {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)
    & docker exec $SupabaseDbContainer psql -U postgres @Args
}

# `supabase start` returning does not mean Postgres accepts connections yet — without
# this the first psql call below can lose the race.
function Wait-ForPostgres {
    foreach ($_ in 1..30) {
        docker exec $SupabaseDbContainer pg_isready -U postgres -q *> $null
        if ($LASTEXITCODE -eq 0) { return $true }
        Start-Sleep -Seconds 1
    }
    Write-Warn "Postgres in $SupabaseDbContainer never became ready."
    return $false
}

function Recreate-DmitriTestDb {
    Write-Info 'Recreating database dmitri_test for isolated backend tests...'
    try {
        Invoke-Psql -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'dmitri_test' AND pid <> pg_backend_pid();" | Out-Null
    } catch { }
    Invoke-Psql -c 'DROP DATABASE IF EXISTS dmitri_test;' | Out-Null
    Invoke-Psql -c 'CREATE DATABASE dmitri_test;' | Out-Null
}

function Test-DmitriRuntimeRoleExists {
    $exists = Invoke-Psql -tAc "SELECT 1 FROM pg_roles WHERE rolname = 'dmitri_runtime'" 2>$null
    return $exists -eq '1'
}

function Invoke-AlembicOnPostgres {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)
    Push-Location (Join-Path $RepoRoot 'backend')
    try {
        $env:DATABASE_URL_DIRECT = $LocalDbUrl
        & uv run alembic @Args
    } finally {
        Remove-Item Env:DATABASE_URL_DIRECT -ErrorAction SilentlyContinue
        Pop-Location
    }
}

function Prepare-BackendTestDatabase {
    Recreate-DmitriTestDb
    if (Test-DmitriRuntimeRoleExists) {
        Write-Note 'dmitri_runtime role present — resetting postgres schema before backend tests'
        Invoke-AlembicOnPostgres downgrade base
    }
}

function Finalize-PostgresForApi {
    Write-Info 'Applying Alembic migrations on postgres for local API (DATABASE_URL_DIRECT in shell only)...'
    Invoke-AlembicOnPostgres upgrade head
    Write-Info "Local Postgres ready at 127.0.0.1:$SupabaseDbPort"
}

function Invoke-WithBackendEnvHidden {
    param([scriptblock]$ScriptBlock)
    $envFile = Join-Path $RepoRoot 'backend\.env'
    $envBackup = $null
    if (Test-Path $envFile) {
        $envBackup = Join-Path $env:TEMP ("dmitri-backend-env-{0}" -f [guid]::NewGuid())
        Move-Item $envFile $envBackup
    }
    Push-Location (Join-Path $RepoRoot 'backend')
    try {
        & $ScriptBlock
    } finally {
        Pop-Location
        if ($envBackup) {
            Move-Item $envBackup $envFile
        }
    }
}

function Setup-BackendInfra {
    if ($AgentOnly) { return }

    if (-not (Start-DockerDaemon)) {
        Print-DockerInstructions
        return
    }

    if (-not (Get-Command supabase -ErrorAction SilentlyContinue)) {
        Print-SupabaseInstructions
        return
    }

    Write-Info 'Starting local Supabase stack...'
    Push-Location $RepoRoot
    try {
        # `supabase start` refuses to run if the CLI still thinks the stack is up while a
        # container has actually exited. A stop first clears that stale bookkeeping;
        # without --no-backup it leaves the data volume intact.
        $running = docker ps --format '{{.Names}}' | Where-Object { $_ -eq $SupabaseDbContainer }
        if (-not $running) {
            try { supabase stop *> $null } catch { }
        }
        supabase start
    } finally {
        Pop-Location
    }

    $running = docker ps --format '{{.Names}}' | Where-Object { $_ -eq $SupabaseDbContainer }
    if (-not $running) {
        Write-Warn "Expected container $SupabaseDbContainer not running after supabase start."
        return
    }

    if (-not (Wait-ForPostgres)) { return }

    Recreate-DmitriTestDb

    $script:InfraOk = $true
}

function Install-Hooks {
    if (-not $Hooks) { return }

    Write-Info 'Installing pre-commit hooks...'
    uv tool install pre-commit
    Push-Location $RepoRoot
    try {
        pre-commit install --hook-type pre-push
    } finally {
        Pop-Location
    }
}

function Run-Verify {
    if ($SkipVerify) {
        Write-Note 'Skipping verification (-SkipVerify)'
        return
    }

    Write-Info 'Running hardware-agent tests...'
    Push-Location (Join-Path $RepoRoot 'hardware-agent')
    try {
        uv run pytest -q
    } finally {
        Pop-Location
    }

    if ($AgentOnly) { return }

    Write-Info 'Running backend tests...'
    if ($InfraOk) {
        Prepare-BackendTestDatabase
        Write-Note 'Temporarily hiding backend\.env so settings tests match CI (no dotenv file)'
        Invoke-WithBackendEnvHidden {
            $env:DATABASE_URL_TEST = $TestDbUrl
            try {
                uv run pytest -q
            } finally {
                Remove-Item Env:DATABASE_URL_TEST -ErrorAction SilentlyContinue
            }
        }
    } else {
        Write-Note 'Running backend tests without DATABASE_URL_TEST (DB-touching tests will skip)'
        Invoke-WithBackendEnvHidden { uv run pytest -q }
    }

    if ($FrontendOk) {
        Write-Info 'Running frontend tests...'
        Push-Location (Join-Path $RepoRoot 'frontend')
        try {
            npm test
        } finally {
            Pop-Location
        }
    }
}

function Print-NextSteps {
    @'

Install complete.

Next steps:
  TUI:     dmitri
           cd hardware-agent; uv run dmitri
  Tests:   cd hardware-agent; uv run pytest
           cd backend; uv run pytest
'@ | Write-Host

    if (-not $AgentOnly) {
        @'
  API:     cd backend; uv run uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
  Worker:  cd backend; uv run python -m api.worker_main
  Health:  curl http://127.0.0.1:8000/api/v1/health
'@ | Write-Host
    }

    if ($FrontendOk) {
        @'
  Web:     cd frontend; npm run dev   (http://localhost:5173)
  CORS:    set CORS_ALLOWED_ORIGINS=http://localhost:5173 in backend\.env before using Web
  Links:   set APP_BASE_URL=http://localhost:5173 in backend\.env for local auth links
'@ | Write-Host
    } elseif (-not $AgentOnly) {
        @'

Frontend was not set up (Node.js missing).
Install Node 22.x, then: cd frontend; npm install; Copy-Item .env.example .env
'@ | Write-Host
    }

    if (-not $AgentOnly -and -not $InfraOk) {
        @'

Backend infra was not configured (Docker/Supabase missing).
Finish setup manually — see backend/README.md and docs/cloud/supabase/SETUP.md
'@ | Write-Host
    }

    if (-not $Hooks) {
        Write-Note 'Optional: .\install.ps1 -Hooks  (pre-commit pre-push)'
    }

    Write-Note 'Docs: docs/DEV-SETUP.md, backend/README.md'
    Write-Note 'Optional Cursor MCP: copy .env.example to .env and set GITHUB_PAT'
}

Write-Info "Dmitri install (repo: $RepoRoot)"
Ensure-Uv
Ensure-Nmap
Sync-PythonDeps
Install-DmitriCli
Seed-BackendEnv
Setup-Frontend
Setup-BackendInfra
Install-Hooks
Run-Verify
if (-not $AgentOnly -and $InfraOk) {
    Finalize-PostgresForApi
}
Print-NextSteps
