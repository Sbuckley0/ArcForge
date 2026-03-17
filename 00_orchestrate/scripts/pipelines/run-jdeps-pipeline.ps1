<#
.SYNOPSIS
    Pipeline: build Maven project → run jdeps → extract jar-to-jar edges → CSV.

.DESCRIPTION
    Orchestrates the jdeps ingestion pipeline in three steps:
      1. load-env.ps1             — load Archim8 config into the session
      2. jdeps-run.ps1            — (optionally) build, then run jdeps across all JARs
      3. jdeps-extract-edges.ps1  — parse jdeps output and write jdeps-jar-edges.csv

    Output lands in:  02_store/neo4j/docker/import/jdeps-jar-edges.csv

    After completion, open http://localhost:7474 and run:
        03_query/cypher/library/jdeps/neo4j-ingest-jdeps.cypher

.PARAMETER SkipBuild
    Skip `mvn clean package` and use existing target/ artifacts.

.PARAMETER FilterJava
    Drop edges to java.* / javax.* JDK modules.

.EXAMPLE
    # From repo root — full pipeline
    .\00_orchestrate\scripts\pipelines\run-jdeps-pipeline.ps1

    # Skip Maven build, filter JDK edges
    .\00_orchestrate\scripts\pipelines\run-jdeps-pipeline.ps1 -SkipBuild -FilterJava
#>

[CmdletBinding()]
param(
    [switch]$SkipBuild,
    [switch]$FilterJava
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$ScriptsDir = Split-Path -Parent $PSScriptRoot           # 00_orchestrate/scripts/
$RepoRoot   = Split-Path -Parent (Split-Path -Parent $ScriptsDir)  # archim8 root
$TasksDir   = Join-Path $RepoRoot '01_ingest\jdep\scripts'

# ---------------------------------------------------------------------------
# 1. Load config
# ---------------------------------------------------------------------------
. (Join-Path $ScriptsDir 'load-env.ps1')

# ---------------------------------------------------------------------------
# 2. Run jdeps against the target repo
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "=== Step 1/2: jdeps run ===" -ForegroundColor Cyan

$runArgs = @{}
if ($SkipBuild)  { $runArgs['SkipBuild']  = $true }
if ($FilterJava) { $runArgs['FilterJava'] = $true }

& (Join-Path $TasksDir 'jdeps-run.ps1') @runArgs

# ---------------------------------------------------------------------------
# 3. Extract jar-to-jar edges → CSV
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "=== Step 2/2: extract edges ===" -ForegroundColor Cyan

$extractArgs = @{}
if ($FilterJava) { $extractArgs['FilterJava'] = $true }

& (Join-Path $TasksDir 'jdeps-extract-edges.ps1') @extractArgs

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
Write-Host ""
Write-Host "Pipeline complete." -ForegroundColor Green
Write-Host "Output: 02_store/neo4j/docker/import/jdeps-jar-edges.csv" -ForegroundColor Cyan
Write-Host "Next:   make docker-up  →  open http://localhost:7474  →  run neo4j-ingest-jdeps.cypher" -ForegroundColor Cyan
