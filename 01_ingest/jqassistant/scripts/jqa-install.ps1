<#
.SYNOPSIS
    Builds the archim8-jqa Docker image.
.DESCRIPTION
    Builds the jQAssistant 2.x container image using docker compose.
    Idempotent — skips if the image already exists (use -Force to rebuild).

    The image is defined in 01_ingest/jqassistant/Dockerfile.
    It downloads the jQA 2.9.1 Neo4j v5 CLI distribution at build time.

    Called by: make jqa-install
    Output:    Docker image archim8-jqa:2.9.1
#>

[CmdletBinding()]
param(
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

$version     = '2.9.1'
$imageName   = "archim8-jqa:$version"

# Paths: $PSScriptRoot = .../01_ingest/jqassistant/scripts
$jqaDir      = Split-Path $PSScriptRoot -Parent          # .../01_ingest/jqassistant
$ingestDir   = Split-Path $jqaDir -Parent                # .../01_ingest
$arcRoot     = Split-Path $ingestDir -Parent             # archim8 root
$composeFile = Join-Path $arcRoot '02_store\neo4j\docker\docker-compose.yml'

# Load Archim8 env so ARCHIM8_TARGET_REPO is set (required by docker compose volume parsing)
$loadEnvScript = Join-Path $arcRoot '00_orchestrate\scripts\load-env.ps1'
if (Test-Path $loadEnvScript) {
    . $loadEnvScript
}
# docker compose requires ARCHIM8_TARGET_REPO to parse the volume spec even during build.
# If it's not set, provide a placeholder so compose can parse the file.
if (-not $env:ARCHIM8_TARGET_REPO) {
    $env:ARCHIM8_TARGET_REPO = $env:TEMP
}

Write-Host ''
Write-Host 'jQAssistant Docker Build -- Archim8'
Write-Host "  Image:   $imageName"
Write-Host "  Compose: $composeFile"
Write-Host ''

if (-not $Force) {
    $ErrorActionPreference = 'Continue'
    $inspect = docker image inspect $imageName 2>&1
    $imageExists = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = 'Stop'
    if ($imageExists) {
        Write-Host "Image already exists: $imageName"
        Write-Host '  Use -Force to rebuild.'
        exit 0
    }
}

Write-Host 'Building Docker image (downloads ~134 MB jQA distribution during build)...'
docker compose -f $composeFile build jqa

if ($LASTEXITCODE -ne 0) {
    Write-Error 'Docker build failed.'
    exit 1
}

Write-Host ''
Write-Host "Build complete: $imageName"
Write-Host "  Run 'make jqa-scan' to scan the target repository."
