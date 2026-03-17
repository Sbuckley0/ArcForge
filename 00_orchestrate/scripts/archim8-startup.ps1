# Archim8 Startup -- guarded container start
#
# Before running `docker compose up`, checks whether archim8-neo4j already
# exists so the user gets clear feedback instead of Docker's raw output.
# Bind-mount data at 02_store/neo4j/docker/data/ is always preserved.
#
# Usage:    make docker-up

param()
$ErrorActionPreference = 'Continue'

$ScriptDir    = Split-Path -Parent $MyInvocation.MyCommand.Path
$Archim8Root = Split-Path -Parent (Split-Path -Parent $ScriptDir)
$ComposeFile  = Join-Path $Archim8Root "02_store\neo4j\docker\docker-compose.yml"
$LocalEnv     = Join-Path $Archim8Root "00_orchestrate\config\archim8.local.env"
$DataDir      = Join-Path $Archim8Root "02_store\neo4j\docker\data"

# Load archim8.local.env into current process environment
if (Test-Path $LocalEnv) {
    foreach ($line in (Get-Content $LocalEnv)) {
        if ($line -match '^([A-Z_][A-Z0-9_]*)=(.*)$') {
            [System.Environment]::SetEnvironmentVariable($Matches[1].Trim(), $Matches[2].Trim())
        }
    }
}

# ---------------------------------------------------------------------------
# Pre-flight: is Docker daemon reachable at all?
# ---------------------------------------------------------------------------
$dockerCheck = docker version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[X]  Docker daemon is not running -- start Docker Desktop and try again." -ForegroundColor Red
    exit 1
}

# ---------------------------------------------------------------------------
# Pre-flight: check current container state
# ---------------------------------------------------------------------------
$existingState = docker inspect archim8-neo4j --format '{{.State.Status}}' 2>&1
$containerKnown = $LASTEXITCODE -eq 0

if ($containerKnown) {
    switch ($existingState.Trim()) {
        "running" {
            $health = docker inspect archim8-neo4j --format '{{.State.Health.Status}}' 2>&1
            Write-Host "[OK] archim8-neo4j is already running ($health) -- nothing to do." -ForegroundColor Green
            Write-Host "    Data:  $DataDir" -ForegroundColor DarkGray
            Write-Host "    Bolt:  bolt://localhost:7687  |  Browser: http://localhost:7474" -ForegroundColor DarkGray
            exit 0
        }
        { $_ -in @("exited", "stopped", "paused", "created") } {
            Write-Host "[->] archim8-neo4j exists but is '$existingState' -- restarting." -ForegroundColor Cyan
            Write-Host "    Existing data at $DataDir will be reused." -ForegroundColor DarkGray
        }
        default {
            Write-Host "[->] archim8-neo4j found in state '$existingState' -- attempting up." -ForegroundColor Yellow
        }
    }
} else {
    Write-Host "[->] archim8-neo4j not found -- creating container." -ForegroundColor Cyan
    if (Test-Path $DataDir) {
        $sizeMB = [math]::Round((Get-ChildItem $DataDir -Recurse -ErrorAction SilentlyContinue |
                   Measure-Object -Property Length -Sum).Sum / 1MB, 0)
        Write-Host "    Existing data directory found ($sizeMB MB) -- will be mounted." -ForegroundColor DarkGray
    } else {
        Write-Host "    Data directory will be created fresh at $DataDir" -ForegroundColor DarkGray
    }
}

# ---------------------------------------------------------------------------
# Start the stack
# ---------------------------------------------------------------------------
docker compose -f $ComposeFile up -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "" 
    Write-Host "[X]  docker compose up failed (exit $LASTEXITCODE)." -ForegroundColor Red
    Write-Host "    Check logs: make docker-logs" -ForegroundColor DarkGray
    exit $LASTEXITCODE
}

Write-Host ""
Write-Host "[OK] archim8-neo4j starting. Poll for readiness: make neo4j-wait" -ForegroundColor Green
Write-Host "    Bolt:  bolt://localhost:7687  |  Browser: http://localhost:7474" -ForegroundColor DarkGray
Write-Host ""
