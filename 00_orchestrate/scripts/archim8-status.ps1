# Archim8 Status -- per-session health check
#
# Runs a quick tool/config audit (no network calls), then checks service
# health and graph data presence. Intended to be run at the start of each
# session to confirm the stack is ready before running the agent.
#
# Usage:    make status

param()
$ErrorActionPreference = 'Continue'

$ScriptDir    = Split-Path -Parent $MyInvocation.MyCommand.Path
$Archim8Root = Split-Path -Parent (Split-Path -Parent $ScriptDir)

$Warnings = 0
$Errors   = 0
$envVars  = @{}

function Write-Pass($msg)    { Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Warn($msg)    { Write-Host "[!!] $msg" -ForegroundColor Yellow; $script:Warnings++ }
function Write-Fail($msg)    { Write-Host "[X]  $msg" -ForegroundColor Red; $script:Errors++ }
function Write-Info($msg)    { Write-Host "    $msg" -ForegroundColor DarkGray }
function Write-Section($msg) { Write-Host "`n-- $msg" -ForegroundColor Cyan }

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm"
Write-Host "`nArchim8 Status  ($timestamp)" -ForegroundColor White
Write-Host ("-" * 60) -ForegroundColor DarkGray

# Doctor marker advisory
$doctorMarker = Join-Path $Archim8Root ".archim8-doctor-ok"
if (-not (Test-Path $doctorMarker)) {
    Write-Host "[!] First-time setup not verified -- run: make doctor" -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# QUICK TOOL AUDIT  (local checks only -- no network calls)
# ---------------------------------------------------------------------------
Write-Section "Runtime Tools"

# Docker daemon
$dockerVer = docker version --format '{{.Server.Version}}' 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Pass "Docker               v$dockerVer"
} else {
    Write-Fail "Docker               daemon not running -- start Docker Desktop"
}

# Java
$javaCmd = Get-Command java -ErrorAction SilentlyContinue
if ($javaCmd) {
    $javaVer = (java -version 2>&1 | Select-Object -First 1) -replace '.*version "([^"]+)".*', '$1'
    Write-Pass "Java                 $javaVer"
} else {
    Write-Warn "Java                 not found on PATH"
}

# Python
$pyVer = python --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Pass "Python               $pyVer"
} else {
    Write-Warn "Python               not found on PATH"
}

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------
Write-Section "Configuration"

$localEnvPath = Join-Path $Archim8Root "00_orchestrate\config\archim8.local.env"
if (Test-Path $localEnvPath) {
    Write-Pass "archim8.local.env   present"
    foreach ($line in (Get-Content $localEnvPath)) {
        if ($line -match '^([A-Z_][A-Z0-9_]*)=(.*)$') {
            $envVars[$Matches[1]] = $Matches[2]
        }
    }
    $requiredVars = @(
        "ARCHIM8_NEO4J_USER",
        "ARCHIM8_NEO4J_PASSWORD",
        "ARCHIM8_NEO4J_BOLT",
        "ARCHIM8_TARGET_REPO"
    )
    foreach ($var in $requiredVars) {
        $val = $envVars[$var]
        if ($val -and $val -ne '/path/to/your/java/project') {
            Write-Pass "  $var"
        } else {
            Write-Warn "  $var   -- not set"
        }
    }
    $targetRepo = $envVars["ARCHIM8_TARGET_REPO"]
    if ($targetRepo -and $targetRepo -ne '/path/to/your/java/project') {
        if (Test-Path $targetRepo) {
            Write-Pass "  ARCHIM8_TARGET_REPO path  exists  ($targetRepo)"
        } else {
            Write-Warn "  ARCHIM8_TARGET_REPO path  not found: $targetRepo"
        }
    }
} else {
    Write-Fail "archim8.local.env   not found -- run: make doctor"
}

# ---------------------------------------------------------------------------
# SERVICES
# ---------------------------------------------------------------------------
Write-Section "Services"

# archim8-neo4j container
$neo4jRaw = docker inspect archim8-neo4j 2>&1
if ($LASTEXITCODE -eq 0) {
    $neo4jInfo = $neo4jRaw | ConvertFrom-Json
    $status    = $neo4jInfo[0].State.Status
    $health    = $neo4jInfo[0].State.Health.Status
    $ports     = ($neo4jInfo[0].NetworkSettings.Ports.PSObject.Properties |
                  ForEach-Object { $_.Name -replace '/tcp','' }) -join ", "
    if ($status -eq "running" -and $health -eq "healthy") {
        Write-Pass "archim8-neo4j       $status / $health  (ports: $ports)"
    } elseif ($status -eq "running") {
        Write-Warn "archim8-neo4j       $status / $health  (still warming up -- wait 30s)"
    } else {
        Write-Fail "archim8-neo4j       $status -- run: make docker-up"
    }
} else {
    Write-Fail "archim8-neo4j       not found -- run: make docker-up"
}

# archim8-jqa Docker image
$jqaRaw = docker image inspect "archim8-jqa:2.9.1" 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Pass "archim8-jqa image   present  (archim8-jqa:2.9.1)"
} else {
    Write-Warn "archim8-jqa image   not built -- run: make jqa-install"
}

# ---------------------------------------------------------------------------
# GRAPH DATA
# ---------------------------------------------------------------------------
Write-Section "Graph Data"

# Scan marker
$scanMarker = Join-Path $Archim8Root "05_deliver\input\01_ingest\.jqa-scan-ok"
if (Test-Path $scanMarker) {
    $scanDate = (Get-Item $scanMarker).LastWriteTime.ToString("yyyy-MM-dd HH:mm")
    Write-Pass "jqa-scan-ok          last scan: $scanDate"
} else {
    Write-Warn "jqa-scan-ok          not found -- run: make jqa-scan"
}

# Node counts via cypher-shell in the running container
$neo4jUser = if ($envVars["ARCHIM8_NEO4J_USER"]) { $envVars["ARCHIM8_NEO4J_USER"] } else { "neo4j" }
$neo4jPass = if ($envVars["ARCHIM8_NEO4J_PASSWORD"]) { $envVars["ARCHIM8_NEO4J_PASSWORD"] } else { "password" }

$testConn = docker exec archim8-neo4j cypher-shell -u $neo4jUser -p $neo4jPass "RETURN 1" --format plain 2>&1
if ($LASTEXITCODE -eq 0) {
    $jarRaw   = docker exec archim8-neo4j cypher-shell -u $neo4jUser -p $neo4jPass "MATCH (j:Jar) RETURN count(j) AS n" --format plain 2>&1
    $mavenRaw = docker exec archim8-neo4j cypher-shell -u $neo4jUser -p $neo4jPass "MATCH (m:Maven) RETURN count(m) AS n" --format plain 2>&1
    $javaRaw  = docker exec archim8-neo4j cypher-shell -u $neo4jUser -p $neo4jPass "MATCH (t:Java) RETURN count(t) AS n" --format plain 2>&1

    $jarN   = ($jarRaw   | Select-String '^\d+' | Select-Object -First 1).Matches[0].Value
    $mavenN = ($mavenRaw | Select-String '^\d+' | Select-Object -First 1).Matches[0].Value
    $javaN  = ($javaRaw  | Select-String '^\d+' | Select-Object -First 1).Matches[0].Value

    if ([int]$jarN -gt 0) {
        Write-Pass "Graph: :Jar          $("{0:N0}" -f [int]$jarN) nodes"
        Write-Pass "Graph: :Maven        $("{0:N0}" -f [int]$mavenN) nodes"
        Write-Pass "Graph: :Java         $("{0:N0}" -f [int]$javaN) nodes"
    } else {
        Write-Warn "Graph                all counts are 0 -- run: make full-pipeline"
    }
} else {
    Write-Warn "Graph                Neo4j not reachable for queries"
}

# ---------------------------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------------------------
Write-Host "`n$('-' * 60)" -ForegroundColor DarkGray

if ($Errors -eq 0 -and $Warnings -eq 0) {
    Write-Host "All checks passed -- system ready." -ForegroundColor Green
    Write-Host "  Start agent:  python 06_agents/orchestrator.py" -ForegroundColor DarkGray
} elseif ($Errors -eq 0) {
    Write-Host "$Warnings warning(s) -- review above before starting agent." -ForegroundColor Yellow
} else {
    Write-Host "$Errors error(s), $Warnings warning(s) -- resolve errors before continuing." -ForegroundColor Red
}
Write-Host ""
