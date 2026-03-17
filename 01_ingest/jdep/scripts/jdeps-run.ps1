<#
.SYNOPSIS
    Builds the target Maven project and runs jdeps across all runtime JARs.

.DESCRIPTION
    1. Optionally runs `mvn clean package -DskipTests` in ARCHIM8_TARGET_REPO.
    2. Collects all runtime JARs (excludes sources/tests/javadoc/shaded; detects
       Spring Boot fat JARs by presence of an original-*.jar sibling and excludes them).
    3. Builds a classpath string from those JARs.
    4. Runs `jdeps` against each JAR (verbose:class is slow; we use default summary).
    5. Writes the combined output to the Neo4j import folder as jdeps-output.txt.

.PARAMETER SkipBuild
    Pass -SkipBuild to skip `mvn clean package` and use existing target/ artifacts.

.PARAMETER FilterJava
    Pass -FilterJava to exclude dependencies on java.* and javax.* modules from output.

.EXAMPLE
    . .\00_orchestrate\scripts\load-env.ps1
    .\01_ingest\jdep\scripts\jdeps-run.ps1

    .\01_ingest\jdep\scripts\jdeps-run.ps1 -SkipBuild -FilterJava
#>

[CmdletBinding()]
param(
    [switch]$SkipBuild,
    [switch]$FilterJava
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------------------
# 1. Load config if not already loaded
# ---------------------------------------------------------------------------
if (-not $env:ARCHIM8_TARGET_REPO) {
    Write-Warning "ARCHIM8_TARGET_REPO not set -- loading config..."
    . (Join-Path $PSScriptRoot '..\..\..\00_orchestrate\scripts\load-env.ps1')
}

$TargetRepo  = $env:ARCHIM8_TARGET_REPO
$JdepsOutput = if ($env:ARCHIM8_JDEPS_OUTPUT) { $env:ARCHIM8_JDEPS_OUTPUT } else { 'jdeps-output.txt' }

# Resolve import dir
$ImportDir = if ($env:ARCHIM8_NEO4J_IMPORT_DIR) {
    $env:ARCHIM8_NEO4J_IMPORT_DIR
} else {
    Join-Path $PSScriptRoot '..\..\..\02_store\neo4j\docker\import'
}
$_resolved = Resolve-Path $ImportDir -ErrorAction SilentlyContinue
if ($_resolved) { $ImportDir = $_resolved.Path }

$OutputFile = Join-Path $ImportDir $JdepsOutput

# ---------------------------------------------------------------------------
# 2. Validate prerequisites
# ---------------------------------------------------------------------------
if (-not (Test-Path $TargetRepo)) {
    Write-Error "ARCHIM8_TARGET_REPO does not exist: $TargetRepo"
    exit 1
}

if (-not (Get-Command 'jdeps' -ErrorAction SilentlyContinue)) {
    Write-Error "'jdeps' not found on PATH.  Install JDK 11+ and ensure JAVA_HOME/bin is in PATH."
    exit 1
}

# ---------------------------------------------------------------------------
# 3. Optional Maven build
# ---------------------------------------------------------------------------
if (-not $SkipBuild) {
    Write-Host "Building target project: $TargetRepo" -ForegroundColor Cyan
    Push-Location $TargetRepo
    try {
        & mvn clean package -DskipTests
        if ($LASTEXITCODE -ne 0) { throw "mvn build failed (exit $LASTEXITCODE)" }
    } finally {
        Pop-Location
    }
} else {
    Write-Host "Skipping Maven build (-SkipBuild)" -ForegroundColor Yellow
}

# ---------------------------------------------------------------------------
# 4. Collect runtime JARs
# ---------------------------------------------------------------------------
Write-Host "Collecting JARs from: $TargetRepo" -ForegroundColor Cyan

$Jars = Get-ChildItem -Path $TargetRepo -Recurse -Filter '*.jar' |
    Where-Object {
        $_.Name -notlike '*-sources.jar'       -and
        $_.Name -notlike '*-tests.jar'         -and
        $_.Name -notlike '*-test.jar'          -and
        $_.Name -notlike '*-javadoc.jar'       -and
        $_.Name -notlike '*-test-fixtures.jar' -and
        $_.Name -notlike '*-shaded.jar'        -and
        # Exclude Spring Boot fat JARs: when original-<name>.jar exists in the
        # same directory, the un-prefixed JAR is the repackaged fat JAR.
        # We prefer the thin original JAR which contains only this module's classes.
        -not (Test-Path (Join-Path $_.DirectoryName "original-$($_.Name)"))
    }

if ($Jars.Count -eq 0) {
    Write-Error "No JARs found under $TargetRepo.  Run without -SkipBuild or check the project structure."
    exit 1
}

Write-Host "Found $($Jars.Count) JAR(s)" -ForegroundColor Green

$Classpath = ($Jars | ForEach-Object { $_.FullName }) -join [IO.Path]::PathSeparator

# ---------------------------------------------------------------------------
# 5. Run jdeps
# ---------------------------------------------------------------------------
New-Item -ItemType Directory -Force -Path $ImportDir | Out-Null

Write-Host "Running jdeps -> $OutputFile" -ForegroundColor Cyan

$AllOutput = [System.Collections.Generic.List[string]]::new()

try {
    foreach ($Jar in $Jars) {
        Write-Verbose "  jdeps $($Jar.Name)"
        $lines = & jdeps --multi-release base --class-path $Classpath $Jar.FullName 2>&1
        if ($null -ne $lines) {
            $AllOutput.AddRange([string[]]@($lines))
        }
    }
} catch {
    Write-Warning "jdeps failed on a JAR: $_"
    Write-Warning "Position: $($_.InvocationInfo.PositionMessage)"
}

Write-Host "Collected $($AllOutput.Count) lines from $($Jars.Count) JARs" -ForegroundColor Cyan

if ($FilterJava) {
    Write-Host "Filtering java.* / javax.* dependencies" -ForegroundColor Yellow
    $AllOutput = $AllOutput | Where-Object { ($_ -notmatch '-> java\.') -and ($_ -notmatch '-> javax\.') }
}

$AllOutput | Set-Content -Path $OutputFile -Encoding UTF8
Write-Host "jdeps output written: $OutputFile ($($AllOutput.Count) lines)" -ForegroundColor Green
