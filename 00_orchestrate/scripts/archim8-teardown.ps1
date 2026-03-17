# Archim8 Teardown -- controlled stack shutdown
#
# Three modes, each progressively more destructive:
#
#   stop         -- suspend containers (keep registered + data)
#   down         -- remove containers (keep data on disk)     [default]
#   all          -- remove containers + permanently delete graph data
#
# Volume note: all Neo4j mounts are bind mounts to the host filesystem.
# Docker named volumes are not used. 'docker compose down -v' has no extra
# effect here -- actual data lives at 02_store/neo4j/docker/data/ and must
# be removed explicitly (only Mode=all does this, after confirmation).
#
# Usage:
#   make stop           -- powershell ... -Mode stop
#   make docker-down    -- powershell ... -Mode down   (default)
#   make teardown       -- powershell ... -Mode down   (alias with explicit messaging)
#   make teardown-all   -- powershell ... -Mode all    (requires typed confirmation)

param(
    [ValidateSet("stop", "down", "all")]
    [string]$Mode = "down"
)
$ErrorActionPreference = 'Continue'

$ScriptDir    = Split-Path -Parent $MyInvocation.MyCommand.Path
$Archim8Root = Split-Path -Parent (Split-Path -Parent $ScriptDir)
$ComposeFile  = Join-Path $Archim8Root "02_store\neo4j\docker\docker-compose.yml"
$DataDir      = Join-Path $Archim8Root "02_store\neo4j\docker\data"

function Write-Section($msg) { Write-Host "`n-- $msg" -ForegroundColor Cyan }

# ---------------------------------------------------------------------------
# Check what's actually running before touching anything
# ---------------------------------------------------------------------------
$dockerCheck = docker version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Archim8 Teardown  [mode: $Mode]" -ForegroundColor White
    Write-Host ("-" * 50) -ForegroundColor DarkGray
    Write-Host "[X]  Docker daemon is not running -- nothing to tear down." -ForegroundColor Yellow
    if ($Mode -eq "all") {
        # Still allow data deletion even without Docker running
        Write-Host "[!!] Docker is down but Mode=all was requested." -ForegroundColor Yellow
        Write-Host "     To delete graph data without Docker, remove manually:" -ForegroundColor DarkGray
        Write-Host "     $DataDir" -ForegroundColor DarkGray
    }
    exit 0
}

$existingState = docker inspect archim8-neo4j --format '{{.State.Status}}' 2>&1
$containerExists = $LASTEXITCODE -eq 0

Write-Host ""
Write-Host "Archim8 Teardown  [mode: $Mode]" -ForegroundColor White
Write-Host ("-" * 50) -ForegroundColor DarkGray

if (-not $containerExists) {
    Write-Host "[OK] archim8-neo4j is not running -- nothing to tear down." -ForegroundColor Green
    if ($Mode -ne "all") { exit 0 }
}

# ---------------------------------------------------------------------------
# MODE: stop -- suspend containers, keep everything
# ---------------------------------------------------------------------------
if ($Mode -eq "stop") {
    Write-Host "[->] Stopping archim8-neo4j (containers remain registered, data safe)..." -ForegroundColor Cyan
    docker compose -f $ComposeFile stop
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Containers stopped." -ForegroundColor Green
        Write-Host "    Resume any time with: make docker-up" -ForegroundColor DarkGray
    } else {
        Write-Host "[X]  docker compose stop failed." -ForegroundColor Red
    }
    exit $LASTEXITCODE
}

# ---------------------------------------------------------------------------
# MODE: down -- remove containers, keep data
# ---------------------------------------------------------------------------
if ($Mode -eq "down") {
    Write-Host "[->] Removing archim8-neo4j container..." -ForegroundColor Cyan
    Write-Host "    Data at $DataDir will be preserved." -ForegroundColor DarkGray
    docker compose -f $ComposeFile down
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[OK] Container removed. Data intact." -ForegroundColor Green
        Write-Host "    Restart: make docker-up  (data will be reused)" -ForegroundColor DarkGray
    } else {
        Write-Host "[X]  docker compose down failed." -ForegroundColor Red
    }
    exit $LASTEXITCODE
}

# ---------------------------------------------------------------------------
# MODE: all -- nuclear, requires confirmation
# ---------------------------------------------------------------------------
if ($Mode -eq "all") {
    Write-Host ""
    Write-Host "+==================================================+" -ForegroundColor Red
    Write-Host "|  DESTRUCTIVE OPERATION -- CANNOT BE UNDONE        |" -ForegroundColor Red
    Write-Host "+==================================================+" -ForegroundColor Red
    Write-Host "|  This will permanently delete:                   |" -ForegroundColor Red
    Write-Host "|    - archim8-neo4j container                    |" -ForegroundColor Red
    Write-Host "|    - ALL graph data at:                          |" -ForegroundColor Red
    Write-Host "|      02_store/neo4j/docker/data/                 |" -ForegroundColor Red
    Write-Host "|    - jqa-scan-ok and jqa-analyze-ok markers      |" -ForegroundColor Red
    Write-Host "|  The next make full-pipeline will start fresh.   |" -ForegroundColor Red
    Write-Host "+==================================================+" -ForegroundColor Red

    # Show data directory size so user knows what they're deleting
    if (Test-Path $DataDir) {
        $sizeMB = [math]::Round((Get-ChildItem $DataDir -Recurse -ErrorAction SilentlyContinue |
                   Measure-Object -Property Length -Sum).Sum / 1MB, 0)
        Write-Host ""
        Write-Host "    Data directory size: $sizeMB MB" -ForegroundColor Yellow
    }

    Write-Host ""
    $confirm = Read-Host "Type 'delete-all' to confirm, or anything else to cancel"
    if ($confirm -ne "delete-all") {
        Write-Host ""
        Write-Host "[OK] Cancelled. No changes made." -ForegroundColor Green
        exit 0
    }

    Write-Section "Stopping and removing containers"
    docker compose -f $ComposeFile down
    if ($LASTEXITCODE -ne 0) {
        Write-Host "[X]  docker compose down failed -- aborting before data deletion." -ForegroundColor Red
        exit $LASTEXITCODE
    }
    Write-Host "[OK] Containers removed." -ForegroundColor Green

    Write-Section "Deleting graph data"
    if (Test-Path $DataDir) {
        Remove-Item -Path $DataDir -Recurse -Force
        Write-Host "[OK] Deleted: $DataDir" -ForegroundColor Green
        # Recreate the empty directory so Docker bind mount doesn't fail on next up
        New-Item -ItemType Directory -Path $DataDir | Out-Null
        Write-Host "[OK] Recreated empty data directory for next run." -ForegroundColor DarkGray
    } else {
        Write-Host "    Data directory not found -- skipping." -ForegroundColor DarkGray
    }

    Write-Section "Clearing scan markers"
    $markers = @(
        (Join-Path $Archim8Root "05_deliver\input\01_ingest\.jqa-scan-ok"),
        (Join-Path $Archim8Root "05_deliver\input\01_ingest\.jqa-analyze-ok")
    )
    foreach ($marker in $markers) {
        if (Test-Path $marker) {
            Remove-Item $marker -Force
            Write-Host "[OK] Removed: $(Split-Path -Leaf $marker)" -ForegroundColor Green
        }
    }

    Write-Host ""
    Write-Host ("-" * 50) -ForegroundColor DarkGray
    Write-Host "[OK] Teardown complete. All data permanently deleted." -ForegroundColor Green
    Write-Host "    To start fresh: make docker-up && make full-pipeline" -ForegroundColor DarkGray
    Write-Host ""
    exit 0
}
