#
# Bring up the local Postgres that the backend test suite needs, and tidy Docker.
#
#   .\database.ps1               clean + set up
#   .\database.ps1 -Test         ... then run the backend suite against it
#   .\database.ps1 -NoClean      skip the Docker cleanup
#   .\database.ps1 -DeepClean    also remove unused Supabase images (see below)
#
# Idempotent: safe to re-run. Never deletes Docker volumes, so the local database
# survives. Alembic is the sole schema owner - this script never runs
# `supabase db reset|push|migration`; conftest.py migrates to head itself.
param(
    [switch]$Test,
    [switch]$NoClean,
    [switch]$DeepClean,
    [switch]$Help
)

$ErrorActionPreference = 'Stop'

if ($Help) {
    @'
Bring up the local Postgres that the backend test suite needs, and tidy Docker.

  .\database.ps1               clean + set up
  .\database.ps1 -Test         ... then run the backend suite against it
  .\database.ps1 -NoClean      skip the Docker cleanup
  .\database.ps1 -DeepClean    also remove unused Supabase images

By default the cleanup leaves the Supabase CLI's own images alone. `supabase start`
re-pulls its full image set even for services disabled in config.toml (imgproxy,
pooler), so deleting them just means downloading them again on the next start.
-DeepClean removes them anyway, at the cost of that re-pull.

Idempotent, and never deletes Docker volumes - the local database survives.
'@ | Write-Host
    exit 0
}

$Root = $PSScriptRoot
Set-Location $Root

$Config = Join-Path $Root 'supabase\config.toml'
$DbName = 'dmitri_test'   # conftest.py aborts unless the database is named exactly this

if (-not (Test-Path $Config)) {
    Write-Error "Not found: $Config"
    exit 1
}

# Read these from config.toml rather than hardcoding, so the script keeps working
# if the project id or port is changed there. Same parse as install.ps1.
$configText = Get-Content $Config -Raw
$projectMatch = [regex]::Match($configText, '(?m)^project_id\s*=\s*"([^"]+)"')
$portMatch = [regex]::Match($configText, '(?ms)^\[db\].*?^port\s*=\s*(\d+)')
$Project = $projectMatch.Groups[1].Value
$Port = $portMatch.Groups[1].Value
$DbContainer = "supabase_db_$Project"
$DatabaseUrlTest = "postgresql+psycopg://postgres:postgres@127.0.0.1:$Port/$DbName"

function Test-DockerUp {
    try {
        docker info *> $null
        return ($LASTEXITCODE -eq 0)
    } catch {
        return $false
    }
}

Write-Host '== Docker daemon =='
if (-not (Test-DockerUp)) {
    $desktop = Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'
    if (-not (Test-Path $desktop)) {
        Write-Error 'Docker daemon is not running - start it and re-run.'
        exit 1
    }
    Write-Host 'Starting Docker Desktop...'
    Start-Process $desktop | Out-Null

    foreach ($_ in 1..90) {
        if (Test-DockerUp) { break }
        Start-Sleep -Seconds 2
    }
    if (-not (Test-DockerUp)) {
        Write-Error 'Docker did not come up in 180s.'
        exit 1
    }
}
Write-Host 'Docker is up.'

Write-Host ''
Write-Host '== Supabase stack =='
$running = docker ps --format '{{.Names}}' | Where-Object { $_ -eq $DbContainer }
if ($running) {
    Write-Host 'Already running.'
} else {
    # `supabase start` refuses to run if the CLI still thinks the stack is up while
    # a container has actually exited. A stop first clears that stale bookkeeping;
    # without --no-backup it leaves the data volume intact.
    try { supabase stop *> $null } catch { }
    supabase start
}

Write-Host ''
Write-Host '== Test database =='
foreach ($_ in 1..30) {
    docker exec $DbContainer pg_isready -U postgres -q *> $null
    if ($LASTEXITCODE -eq 0) { break }
    Start-Sleep -Seconds 1
}
docker exec $DbContainer pg_isready -U postgres -q *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Error "Postgres in $DbContainer never became ready."
    exit 1
}

$exists = docker exec $DbContainer psql -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$DbName'"
if (-not [string]::IsNullOrWhiteSpace(($exists -join ''))) {
    Write-Host "Database '$DbName' already exists."
} else {
    docker exec $DbContainer psql -U postgres -c "CREATE DATABASE $DbName"
    Write-Host "Created database '$DbName'."
}

if (-not $NoClean) {
    Write-Host ''
    Write-Host '== Docker cleanup =='
    # Deliberately runs *after* the stack is up, so every image the running stack
    # needs is referenced by a container and therefore protected. Doing this first
    # would delete the whole Supabase image set on a machine whose containers had
    # been removed, forcing a multi-GB re-pull.
    #
    # Only images no container references at all are removed. Volumes are never
    # touched - that would destroy the local database.
    #
    # Supabase's own images are skipped unless -DeepClean: `supabase start` pulls
    # its whole image set even for services disabled in config.toml (imgproxy,
    # pooler), so removing them just triggers a re-download on the next start.
    $removed = 0
    $skipped = 0
    $supabasePrefix = ''
    if (-not $DeepClean) {
        try {
            $image = docker inspect $DbContainer --format '{{.Config.Image}}'
            if ($image) {
                $supabasePrefix = [regex]::Replace($image, '/[^/]*$', '/')
            }
        } catch { }
    }

    foreach ($image in (docker images --format '{{.Repository}}:{{.Tag}}')) {
        if ([string]::IsNullOrWhiteSpace($image) -or $image -like '*<none>*') { continue }
        if (docker ps -aq --filter "ancestor=$image") { continue }
        if ($supabasePrefix -and $image.StartsWith($supabasePrefix)) {
            Write-Host "Keeping (Supabase would re-pull it): $image"
            $skipped++
            continue
        }
        Write-Host "Removing unused image: $image"
        docker rmi $image *> $null
        if ($LASTEXITCODE -eq 0) { $removed++ }
    }

    foreach ($id in (docker images -f dangling=true -q)) {
        if ([string]::IsNullOrWhiteSpace($id)) { continue }
        Write-Host "Removing dangling image: $id"
        docker rmi $id *> $null
        if ($LASTEXITCODE -eq 0) { $removed++ }
    }

    if ($removed -eq 0 -and $skipped -eq 0) {
        Write-Host 'Nothing to remove - every image is in use.'
    } else {
        Write-Host "Removed $removed image(s); kept $skipped Supabase image(s)."
        if ($skipped -gt 0) { Write-Host 'Use -DeepClean to remove those too.' }
    }
}

Write-Host ''
Write-Host '== Ready =='
Write-Host "DATABASE_URL_TEST=$DatabaseUrlTest"

if ($Test) {
    Write-Host ''
    Write-Host '== Backend suite =='
    Push-Location (Join-Path $Root 'backend')
    try {
        $env:DATABASE_URL_TEST = $DatabaseUrlTest
        uv run pytest -q
    } finally {
        Remove-Item Env:DATABASE_URL_TEST -ErrorAction SilentlyContinue
        Pop-Location
    }
} else {
    Write-Host ''
    Write-Host 'Run the suite with:'
    Write-Host "  cd backend; `$env:DATABASE_URL_TEST=`"$DatabaseUrlTest`"; uv run pytest"
    Write-Host 'Or re-run this script with -Test.'
}
