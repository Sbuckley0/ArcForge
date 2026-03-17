<#
.SYNOPSIS
    Runs jQAssistant scan via the archim8-jqa Docker container.
.DESCRIPTION
    Runs 'docker compose run --rm jqa scan' against the target repository,
    writing structural nodes (:Maven:*, :Java:*) into the running Neo4j instance.
    Idempotent via .jqa-scan-ok marker in 05_deliver/input/01_ingest/.

    Prerequisites:
      - make jqa-install          (archim8-jqa Docker image must be built)
      - make docker-up            (Neo4j must be running)
      - Target repo must be built (mvn clean install -DskipTests)

    Called by: make jqa-scan
    Log:       05_deliver/input/01_ingest/jqa-scan.log
    Marker:    05_deliver/input/01_ingest/.jqa-scan-ok

.PARAMETER ScanPath
    Path to the Maven project root (reactor POM directory) to scan.
    Defaults to $env:ARCHIM8_TARGET_REPO.

.PARAMETER Force
    Re-run even if .jqa-scan-ok marker exists (forces a fresh scan).
#>

[CmdletBinding()]
param(
    [string]$ScanPath = $env:ARCHIM8_TARGET_REPO,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

# Paths: $PSScriptRoot = .../01_ingest/jqassistant/scripts
$jqaDir      = Split-Path $PSScriptRoot -Parent          # .../01_ingest/jqassistant
$ingestDir   = Split-Path $jqaDir -Parent                # .../01_ingest
$arcRoot     = Split-Path $ingestDir -Parent             # archim8 root
$composeFile = Join-Path $arcRoot '02_store\neo4j\docker\docker-compose.yml'
$logDir      = Join-Path $arcRoot '05_deliver\input\01_ingest'
$logFile     = Join-Path $logDir 'jqa-scan.log'
$markerFile  = Join-Path $logDir '.jqa-scan-ok'

# Load Archim8 env (sets ARCHIM8_TARGET_REPO, etc.) — must come before $ScanPath fallback
$loadEnvScript = Join-Path $arcRoot '00_orchestrate\scripts\load-env.ps1'
if (Test-Path $loadEnvScript) {
    . $loadEnvScript
}

# Re-apply default after env load if ScanPath not explicitly passed
if (-not $ScanPath) {
    $ScanPath = $env:ARCHIM8_TARGET_REPO
}

# ---- Preflight checks -------------------------------------------------------

# Verify archim8-jqa image exists
$ErrorActionPreference = 'Continue'
$imageCheck = docker image inspect archim8-jqa:2.9.1 2>&1
$imageExists = ($LASTEXITCODE -eq 0)
$ErrorActionPreference = 'Stop'
if (-not $imageExists) {
    Write-Error "Docker image archim8-jqa:2.9.1 not found. Run 'make jqa-install' first."
    exit 1
}

if (-not $ScanPath) {
    Write-Error ("No scan path provided. Set ARCHIM8_TARGET_REPO in archim8.local.env " +
                 "or pass -ScanPath <path>.")
    exit 1
}

if (-not (Test-Path $ScanPath)) {
    Write-Error "Scan path does not exist: $ScanPath"
    exit 1
}

# Expose to docker compose for volume substitution
$env:ARCHIM8_TARGET_REPO = $ScanPath

# ---- Idempotency guard ------------------------------------------------------

if ((Test-Path $markerFile) -and -not $Force) {
    $ts = (Get-Content $markerFile -Raw -ErrorAction SilentlyContinue).Trim()
    Write-Host ''
    Write-Host "jQA scan already completed at: $ts"
    Write-Host "  Marker: $markerFile"
    Write-Host "  Use -Force to re-scan."
    exit 0
}

# ---- Concurrency lock -------------------------------------------------------
# Prevents two simultaneous scans from writing to Neo4j at the same time.

$lockFile = Join-Path $logDir '.jqa-scan-lock'
if (Test-Path $lockFile) {
    $lockPid = (Get-Content $lockFile -Raw -ErrorAction SilentlyContinue).Trim()
    Write-Host ''
    Write-Host "ERROR: jQA scan already in progress (lock: $lockFile, PID $lockPid)."
    Write-Host "  Wait for it to finish, or delete the lock file if the previous run crashed."
    exit 1
}
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$PID | Set-Content $lockFile -NoNewline

# ---- Run scan ---------------------------------------------------------------

Remove-Item $markerFile -Force -ErrorAction SilentlyContinue

Write-Host ''
Write-Host 'jQAssistant Scanner -- Archim8 (Docker)'
Write-Host "  Image:   archim8-jqa:2.9.1"
Write-Host "  Target:  $ScanPath  (mounted as /scan)"
Write-Host "  Compose: $composeFile"
Write-Host "  Log:     $logFile"
Write-Host ''

# Run via docker compose so the jqa container shares the compose network with neo4j.
# neo4j is reachable at bolt://neo4j:7687 from inside the container.
# Output is piped to log file via Tee-Object.
#
# NOTE: docker writes status lines to stderr. Lower $ErrorActionPreference so
# informational stderr output doesn't trigger NativeCommandError.

$ErrorActionPreference = 'Continue'

docker compose -f $composeFile run --rm `
    jqa `
    scan -f /scan -configurationLocations /jqassistant/config/jqassistant.yml `
    2>&1 | Tee-Object -FilePath $logFile

$scanExit = $LASTEXITCODE
$ErrorActionPreference = 'Stop'

# Always release the lock
Remove-Item $lockFile -Force -ErrorAction SilentlyContinue

if ($scanExit -ne 0) {
    Write-Error "jQA scan failed (exit $scanExit). See: $logFile"
    exit 1
}

# Write success marker
Set-Content -Path $markerFile -Value (Get-Date -Format 'o')

Write-Host ''
Write-Host 'Scan complete.'
Write-Host "  Marker: $markerFile"
Write-Host "  Log:    $logFile"
Write-Host "  Run 'make jqa-verify' to confirm graph node counts."
