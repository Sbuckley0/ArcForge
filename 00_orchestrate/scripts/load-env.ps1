<#
.SYNOPSIS
    Loads Archim8 environment variables from config files into the current session.

.DESCRIPTION
    Sources 00_orchestrate/config/archim8.env (committed defaults) and then
    00_orchestrate/config/archim8.local.env (developer overrides, gitignored) if it exists.
    Variables from archim8.local.env win over archim8.env.

.EXAMPLE
    # Dot-source so vars persist in your current shell:
    . .\00_orchestrate\scripts\load-env.ps1

.NOTES
    Must be dot-sourced (. .\00_orchestrate\scripts\load-env.ps1) -- not called as a normal
    script -- otherwise the variables are scoped to the child process and lost.
#>

[CmdletBinding()]
param()

# Resolve the archim8 repo root (15_tools/scripts/ -> 15_tools/ -> repo root)
$RepoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

function Import-EnvFile {
    param(
        [Parameter(Mandatory)][string]$Path
    )

    if (-not (Test-Path $Path)) {
        Write-Verbose "Config file not found, skipping: $Path"
        return
    }

    Write-Host "Loading config: $Path" -ForegroundColor Cyan

    foreach ($line in Get-Content $Path) {
        # Skip blanks and comments
        if ($line -match '^\s*$' -or $line -match '^\s*#') { continue }

        # Parse KEY=VALUE (value may contain = signs)
        if ($line -match '^\s*([^=]+?)\s*=\s*(.*)\s*$') {
            $key   = $Matches[1].Trim()
            $value = $Matches[2].Trim()

            # Strip inline comments (# after value)
            $value = ($value -replace '\s+#.*$', '').Trim()

            [System.Environment]::SetEnvironmentVariable($key, $value, 'Process')
            Set-Item -Path "env:$key" -Value $value
            Write-Verbose "  $key = $value"
        }
    }
}

Import-EnvFile -Path (Join-Path $RepoRoot '00_orchestrate\config\archim8.env')
Import-EnvFile -Path (Join-Path $RepoRoot '00_orchestrate\config\archim8.local.env')

Write-Host "Archim8 config loaded. Key values:" -ForegroundColor Green
Write-Host "  ARCHIM8_TARGET_REPO   = $env:ARCHIM8_TARGET_REPO"
Write-Host "  ARCHIM8_NEO4J_BOLT    = $env:ARCHIM8_NEO4J_BOLT"
Write-Host "  ARCHIM8_NEO4J_USER    = $env:ARCHIM8_NEO4J_USER"
