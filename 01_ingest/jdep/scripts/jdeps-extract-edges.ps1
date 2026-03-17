<#
.SYNOPSIS
    Extracts jar-to-jar dependency edges from jdeps-output.txt.

.DESCRIPTION
    Reads the jdeps output file produced by jdeps-run.ps1.
    Extracts only top-level jar dependency lines matching the pattern:
        <jar-filename> -> <jar-path-or-name>
    Normalises RHS values to bare filenames.
    Writes a NO-HEADER CSV with two columns [source_jar, target_jar]
    suitable for LOAD CSV in Neo4j Browser.

.PARAMETER FilterJava
    Drop edges where the target starts with "java" (JDK built-ins).

.EXAMPLE
    . .\00_orchestrate\scripts\load-env.ps1
    .\01_ingest\jdep\scripts\jdeps-extract-edges.ps1

    .\01_ingest\jdep\scripts\jdeps-extract-edges.ps1 -FilterJava
#>

[CmdletBinding()]
param(
    [switch]$FilterJava
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------------------
# Load config if not already loaded
# ---------------------------------------------------------------------------
if (-not $env:ARCHIM8_JDEPS_OUTPUT) {
    Write-Warning "Config not loaded -- loading now..."
    . (Join-Path $PSScriptRoot '..\..\..\00_orchestrate\scripts\load-env.ps1')
}

# Resolve paths
$ImportDir = if ($env:ARCHIM8_NEO4J_IMPORT_DIR) {
    $env:ARCHIM8_NEO4J_IMPORT_DIR
} else {
    Join-Path $PSScriptRoot '..\..\..\02_store\neo4j\docker\import'
}
$_resolved = Resolve-Path $ImportDir -ErrorAction SilentlyContinue
if ($_resolved) { $ImportDir = $_resolved.Path }

$JdepsOutput = Join-Path $ImportDir $(if ($env:ARCHIM8_JDEPS_OUTPUT) { $env:ARCHIM8_JDEPS_OUTPUT } else { 'jdeps-output.txt' })
$EdgesCsv    = Join-Path $ImportDir $(if ($env:ARCHIM8_JDEPS_EDGES_CSV) { $env:ARCHIM8_JDEPS_EDGES_CSV } else { 'jdeps-jar-edges.csv' })

# ---------------------------------------------------------------------------
# Validate
# ---------------------------------------------------------------------------
if (-not (Test-Path $JdepsOutput)) {
    Write-Error "jdeps output not found: $JdepsOutput  -- run jdeps-run.ps1 first."
    exit 1
}

# ---------------------------------------------------------------------------
# Parse edges
# ---------------------------------------------------------------------------
# jdeps top-level jar lines look like:
#   spring-core-5.3.20.jar -> spring-jcl-5.3.20.jar
#   spring-core-5.3.20.jar -> /path/to/lib.jar
#   spring-core-5.3.20.jar -> not found
#   spring-core-5.3.20.jar -> java.base
#
# We want lines where both LHS and RHS end with .jar (i.e. real jar deps).

$EdgeRows = [System.Collections.Generic.List[string]]::new()
$Seen     = [System.Collections.Generic.HashSet[string]]::new()

foreach ($line in Get-Content $JdepsOutput -Encoding UTF8) {
    # Match: <anything>.jar -> <anything>
    if ($line -match '^(\S+\.jar)\s+->\s+(.+)$') {
        $lhs = $Matches[1].Trim()
        $rhs = $Matches[2].Trim()

        # Skip "not found"
        if ($rhs -eq 'not found') { continue }

        # Optionally skip JDK modules
        if ($FilterJava -and ($rhs -match '^java\.' -or $rhs -match '^javax\.')) { continue }

        # Normalise RHS: extract filename from a path if it looks like one
        if ($rhs -like '*.jar') {
            $rhs = [IO.Path]::GetFileName($rhs)
        }

        # Deduplicate
        $key = "$lhs|$rhs"
        if ($Seen.Add($key)) {
            # CSV-escape: wrap in quotes if value contains comma
            $lhsCsv = if ($lhs -match ',') { "`"$lhs`"" } else { $lhs }
            $rhsCsv = if ($rhs -match ',') { "`"$rhs`"" } else { $rhs }
            $EdgeRows.Add("$lhsCsv,$rhsCsv")
        }
    }
}

# ---------------------------------------------------------------------------
# Write output (NO HEADERS)
# ---------------------------------------------------------------------------
$EdgeRows | Set-Content -Path $EdgesCsv -Encoding UTF8
Write-Host "Edges written: $EdgesCsv ($($EdgeRows.Count) rows)" -ForegroundColor Green
Write-Host ""
Write-Host "Next step: open 03_query/cypher/library/jdeps/neo4j-ingest-jdeps.cypher in Neo4j Browser." -ForegroundColor Cyan
