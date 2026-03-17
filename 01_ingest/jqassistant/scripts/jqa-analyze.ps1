<#
.SYNOPSIS
    Runs jQAssistant rules engine (analyze) via the archim8-jqa Docker container.
.DESCRIPTION
    Runs 'docker compose run --rm jqa analyze' against the Neo4j store,
    evaluating concept and constraint rules defined under:
      01_ingest/jqassistant/rules/baseline/

    Output:
      - HTML report  → 05_deliver/input/01_ingest/jqa-report/
      - Violation log → 05_deliver/input/01_ingest/jqa-analyze.log

    Prerequisites:
      - make jqa-install          (archim8-jqa Docker image must be built)
      - make docker-up            (Neo4j must be running)
      - make jqa-scan             (graph must be populated before analysis)

    Layer model enforced (low → high):
      1. common-*           (foundation — zero internal deps)
      2. database-*         (JDBC/JPA adapters)
         message-queue-*    (messaging adapters)
      3. system-*           (ORM + repository services)
         transaction-database-*
      4. platform-*         (Pekko/lifecycle framework)
      5. runtime-cobol-*    (workload runtimes)
         runtime-easytrieve-*
      6. control-center-*   (management plane)

    Constraints run with failOn: none — violations are reported as warnings,
    not build failures, until the baseline is established.

    Called by: make jqa-analyze
    Log:       05_deliver/input/01_ingest/jqa-analyze.log
    Report:    05_deliver/input/01_ingest/jqa-report/

.PARAMETER Groups
    Comma-separated list of rule group IDs to run.
    Defaults to the group defined in jqassistant.yml (set by 'make jqa-generate-rules').
    Override example: -Groups 'MyApp:Default'

.PARAMETER Force
    Re-run even if Neo4j already has layer labels (concept was applied).
    NOTE: analyze is always safe to re-run — concepts are SET (idempotent).
#>

[CmdletBinding()]
param(
    [string]$Groups = '',   # empty = auto-detect from jqassistant.yml
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

# Paths: $PSScriptRoot = .../01_ingest/jqassistant/scripts
$jqaDir      = Split-Path $PSScriptRoot -Parent          # .../01_ingest/jqassistant
$ingestDir   = Split-Path $jqaDir -Parent                # .../01_ingest
$arcRoot     = Split-Path $ingestDir -Parent             # archim8 root
$composeFile = Join-Path $arcRoot '02_store\neo4j\docker\docker-compose.yml'
$logDir      = Join-Path $arcRoot '05_deliver\input\01_ingest'
$logFile     = Join-Path $logDir 'jqa-analyze.log'
$reportDir   = Join-Path $logDir 'jqa-report'

# Load Archim8 env (sets ARCHIM8_TARGET_REPO, etc.)
$loadEnvScript = Join-Path $arcRoot '00_orchestrate\scripts\load-env.ps1'
if (Test-Path $loadEnvScript) {
    . $loadEnvScript
}

# ---- Resolve rule group from jqassistant.yml if not passed as parameter ----

$jqaYmlPath = Join-Path $jqaDir 'config\jqassistant.yml'
if ([string]::IsNullOrEmpty($Groups)) {
    if (Test-Path $jqaYmlPath) {
        # Extract first entry under `groups:` list
        $ymlContent = Get-Content $jqaYmlPath -Raw
        $match = [regex]::Match($ymlContent, '(?m)^[ \t]+groups:\s*\n[ \t]+-[ \t]+(.+)')
        if ($match.Success) {
            $Groups = $match.Groups[1].Value.Trim()
        }
    }
    # Final fallback
    if ([string]::IsNullOrEmpty($Groups)) {
        $Groups = 'Default'
        Write-Warning "Could not detect rule group from jqassistant.yml. Defaulting to '$Groups'."
        Write-Warning "Run 'make jqa-generate-rules' to configure the group automatically."
    }
}

# ---- Preflight checks -------------------------------------------------------

$ErrorActionPreference = 'Continue'
$imageCheck = docker image inspect archim8-jqa:2.9.1 2>&1
$imageExists = ($LASTEXITCODE -eq 0)
$ErrorActionPreference = 'Stop'
if (-not $imageExists) {
    Write-Error "Docker image archim8-jqa:2.9.1 not found. Run 'make jqa-install' first."
    exit 1
}

# Verify scan was run first (at least some Maven or Java nodes should exist)
$nodeCheck = docker exec archim8-neo4j cypher-shell `
    -u neo4j -p password `
    "MATCH (n:Maven) RETURN count(n) AS c" 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Error "Neo4j is not accessible. Run 'make docker-up' and 'make jqa-scan' first."
    exit 1
}

$nodeCount = ($nodeCheck | Select-String '\d+' | Select-Object -Last 1).Matches[0].Value
if ([int]$nodeCount -eq 0) {
    Write-Warning "No :Maven nodes found in Neo4j. Did 'make jqa-scan' complete successfully?"
    Write-Warning "Proceeding with analyze - concepts may return 0 results."
}

# ---- Run analyze ------------------------------------------------------------

New-Item -ItemType Directory -Force -Path $logDir   | Out-Null
New-Item -ItemType Directory -Force -Path $reportDir | Out-Null

Write-Host ''
Write-Host 'jQAssistant Rules Engine (analyze) -- Archim8 (Docker)'
Write-Host "  Image:    archim8-jqa:2.9.1"
Write-Host "  Groups:   $Groups"
Write-Host "  Config:   01_ingest/jqassistant/config/jqassistant.yml"
Write-Host "  Rules:    01_ingest/jqassistant/rules/baseline/"
Write-Host "  Report:   $reportDir"
Write-Host "  Log:      $logFile"
Write-Host ''
Write-Host "  Rule group: $Groups"
Write-Host ''

# Lower ErrorActionPreference so docker informational stderr doesn't trigger
# NativeCommandError in PowerShell.
$ErrorActionPreference = 'Continue'

docker compose -f $composeFile run --rm `
    jqa `
    analyze -configurationLocations /jqassistant/config/jqassistant.yml `
    2>&1 | Tee-Object -FilePath $logFile

$analyzeExit = $LASTEXITCODE
$ErrorActionPreference = 'Stop'

# ---- Parse violation summary ------------------------------------------------

$logContent  = Get-Content $logFile -Raw -ErrorAction SilentlyContinue
$violations  = ($logContent | Select-String 'Constraint violation' -AllMatches).Matches.Count
$warnings    = ($logContent | Select-String '(?i)(WARN|WARNING)').Count
$concepts    = ($logContent | Select-String 'Applying concept').Count
$constraints = ($logContent | Select-String 'Applying constraint').Count

Write-Host ''
Write-Host '--- Analyze summary ---'
Write-Host "  Concepts applied:        $concepts"
Write-Host "  Constraints evaluated:   $constraints"
Write-Host "  Constraint violations:   $violations"
Write-Host "  Warnings:                $warnings"
Write-Host "  Exit code:               $analyzeExit"
Write-Host "  Log:                     $logFile"
if (Test-Path $reportDir) {
    $htmlReport = Join-Path $reportDir 'index.html'
    if (Test-Path $htmlReport) {
        Write-Host "  HTML report:             $htmlReport"
    }
}

if ($analyzeExit -ne 0) {
    Write-Warning "jQA analyze exited with code $analyzeExit (failOn:none - violations are warnings only)."
    Write-Warning "Review $logFile for details."
}

# ---- Generate violations report -----------------------------------------

$reportMdPath = Join-Path $logDir 'jqa-violations-report.md'
$reportScript = Join-Path $PSScriptRoot 'jqa_violations_report.py'
if (Test-Path $reportScript) {
    Write-Host ''
    Write-Host '--- Generating architecture health report ---'
    python $reportScript
    if ($LASTEXITCODE -eq 0 -and (Test-Path $reportMdPath)) {
        Write-Host ''
        Write-Host '*** Architecture health report ready ***'
        Write-Host "    $reportMdPath"
        Write-Host ''
        # Open in VS Code so the report appears immediately in the editor
        $codeCmd = Get-Command code -ErrorAction SilentlyContinue
        if ($codeCmd) {
            code $reportMdPath
        }
    } else {
        Write-Warning "Violations report script failed (exit $LASTEXITCODE) - check $reportScript."
    }
} else {
    Write-Warning "jqa_violations_report.py not found at $reportScript - skipping report generation."
}

Write-Host ''
Write-Host 'Analyze complete.'
# Always exit 0 to avoid blocking the make pipeline - failOn:none is set in jqassistant.yml
exit 0
