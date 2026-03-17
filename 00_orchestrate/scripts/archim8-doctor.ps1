# Archim8 Doctor -- full first-time setup and environment verification
#
# Checks: runtime tools, Python environment, configuration, disk space,
#         and LLM network connectivity.
#
# Usage:    make doctor
# Outputs:  .archim8-doctor-ok written to archim8 root on success (0 errors)

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
function Write-Info($msg)    { Write-Host "     $msg" -ForegroundColor DarkGray }
function Write-Section($msg) { Write-Host "`n--- $msg" -ForegroundColor Cyan }

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm"
Write-Host "`nArchim8 Doctor  ($timestamp)" -ForegroundColor White
Write-Host ("-" * 60) -ForegroundColor DarkGray

# ---------------------------------------------------------------------------
# RUNTIME TOOLS
# ---------------------------------------------------------------------------
Write-Section "Runtime Tools"

# Docker
$dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
if ($dockerCmd) {
    $dockerVer = docker version --format '{{.Server.Version}}' 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Pass "Docker               v$dockerVer"
    } else {
        Write-Fail "Docker               installed but daemon not running -- start Docker Desktop"
    }
} else {
    Write-Fail "Docker               not found on PATH -- install Docker Desktop"
}

# Java
$javaCmd = Get-Command java -ErrorAction SilentlyContinue
if ($javaCmd) {
    $javaRaw = java -version 2>&1 | Select-Object -First 1
    $javaVer = $javaRaw -replace '.*version "([^"]+)".*', '$1'
    Write-Pass "Java                 $javaVer  ($($javaCmd.Source))"
} else {
    Write-Warn "Java                 not found on PATH -- required for jdeps scanning"
}

# Maven
$mvnCmd = Get-Command mvn -ErrorAction SilentlyContinue
if ($mvnCmd) {
    $mvnRaw = mvn -version 2>&1 | Select-Object -First 1
    $mvnVer = $mvnRaw -replace 'Apache Maven ([0-9.]+).*', '$1'
    Write-Pass "Maven                $mvnVer  ($($mvnCmd.Source))"
} else {
    Write-Warn "Maven                not found on PATH -- required for target repo Maven builds"
}

# Python
$pythonExe = $null
foreach ($exe in @("python", "python3")) {
    $cmd = Get-Command $exe -ErrorAction SilentlyContinue
    if ($cmd) { $pythonExe = $exe; break }
}
if ($pythonExe) {
    $pyVer = & $pythonExe --version 2>&1
    if ($pyVer -match 'Python (\d+)\.(\d+)') {
        $pyMaj = [int]$Matches[1]; $pyMin = [int]$Matches[2]
        if ($pyMaj -ge 3 -and $pyMin -ge 10) {
            Write-Pass "Python               $pyVer"
        } else {
            Write-Warn "Python               $pyVer -- 3.10+ required"
        }
    } else {
        Write-Warn "Python               version undetected ($pyVer)"
    }
} else {
    Write-Fail "Python               not found on PATH"
}

# Git
$gitCmd = Get-Command git -ErrorAction SilentlyContinue
if ($gitCmd) {
    $gitVer = git --version 2>&1
    Write-Pass "Git                  $gitVer"
} else {
    Write-Warn "Git                  not found on PATH"
}

# ---------------------------------------------------------------------------
# PYTHON ENVIRONMENT
# ---------------------------------------------------------------------------
Write-Section "Python Environment"

# .venv may sit inside archim8/ or one level up at the workspace root
$venvPath = Join-Path $Archim8Root ".venv"
if (-not (Test-Path $venvPath)) {
    $venvPath = Join-Path (Split-Path -Parent $Archim8Root) ".venv"
}
if (Test-Path $venvPath) {
    Write-Pass ".venv                exists  ($venvPath)"
    $venvPython = Join-Path $venvPath "Scripts\python.exe"
    if (-not (Test-Path $venvPython)) {
        $venvPython = Join-Path $venvPath "bin/python"
    }
    if (Test-Path $venvPython) {
        $importChecks = @(
            @{ display = "langchain";        import = "langchain" },
            @{ display = "langgraph";        import = "langgraph" },
            @{ display = "neo4j";            import = "neo4j" },
            @{ display = "langchain_openai"; import = "langchain_openai" },
            @{ display = "pydantic";         import = "pydantic" },
            @{ display = "PyYAML";           import = "yaml" }
        )
        foreach ($check in $importChecks) {
            $result = & $venvPython -c "import $($check.import); v = getattr($($check.import), '__version__', 'ok'); print(v)" 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Pass "  $($check.display.PadRight(20)) $result"
            } else {
                Write-Fail "  $($check.display.PadRight(20)) not importable -- run: make setup"
            }
        }
    } else {
        Write-Warn ".venv python         executable not found -- run: make setup"
    }
} else {
    Write-Warn ".venv                not found -- run: make setup"
}

# ---------------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------------
Write-Section "Configuration"

$localEnvPath = Join-Path $Archim8Root "00_orchestrate\config\archim8.local.env"
$templatePath = Join-Path $Archim8Root "00_orchestrate\config\archim8.local.env.template"

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
            Write-Warn "  $var   -- not set (edit archim8.local.env)"
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
    Write-Fail "archim8.local.env   not found"
    Write-Info "Copy the template and fill in your values:"
    Write-Info "  cp `"$templatePath`" `"$localEnvPath`""
}

# ---------------------------------------------------------------------------
# DISK SPACE
# ---------------------------------------------------------------------------
Write-Section "Disk Space"

$drive = (Split-Path -Qualifier $Archim8Root).TrimEnd(':')
$disk  = Get-PSDrive $drive -ErrorAction SilentlyContinue
if ($disk) {
    $freeGB = [math]::Round($disk.Free / 1GB, 1)
    if ($freeGB -ge 10) {
        Write-Pass "Free disk space      ${freeGB} GB on drive ${drive}:"
    } elseif ($freeGB -ge 5) {
        Write-Warn "Free disk space      ${freeGB} GB on drive ${drive}: -- jQA scans can use 2-5 GB"
    } else {
        Write-Fail "Free disk space      ${freeGB} GB on drive ${drive}: -- critically low, scan may fail"
    }
}

# ---------------------------------------------------------------------------
# NETWORK CONNECTIVITY (LLM endpoint -- optional)
# ---------------------------------------------------------------------------
Write-Section "Network Connectivity"

$provider = $envVars["ARCHIM8_LLM_PROVIDER"]
if (-not $provider) { $provider = "github-models" }

switch ($provider.ToLower()) {
    "azure" {
        $endpoint = $envVars["AZURE_OPENAI_ENDPOINT"]
        if ($endpoint -and $endpoint -ne 'https://your-instance.openai.azure.com/') {
            try {
                $uri  = [System.Uri]$endpoint
                $conn = Test-NetConnection -ComputerName $uri.Host -Port 443 `
                            -InformationLevel Quiet -WarningAction SilentlyContinue
                if ($conn) { Write-Pass "Azure OpenAI         reachable  ($($uri.Host))" }
                else        { Write-Warn "Azure OpenAI         unreachable ($($uri.Host)) -- check network/VPN" }
            } catch {
                Write-Warn "Azure OpenAI         could not resolve endpoint: $endpoint"
            }
        } else {
            Write-Warn "Azure OpenAI         AZURE_OPENAI_ENDPOINT not set"
        }
    }
    "openai" {
        $conn = Test-NetConnection -ComputerName "api.openai.com" -Port 443 `
                    -InformationLevel Quiet -WarningAction SilentlyContinue
        if ($conn) { Write-Pass "OpenAI API           reachable  (api.openai.com)" }
        else        { Write-Warn "OpenAI API           unreachable -- check network/VPN" }
    }
    default {
        # github-models
        $token = $envVars["GITHUB_TOKEN"]
        if ($token) {
            $conn = Test-NetConnection -ComputerName "models.inference.ai.azure.com" -Port 443 `
                        -InformationLevel Quiet -WarningAction SilentlyContinue
            if ($conn) { Write-Pass "GitHub Models        reachable  (models.inference.ai.azure.com)" }
            else        { Write-Warn "GitHub Models        unreachable -- check network/VPN" }
        } else {
            Write-Warn "GitHub Models        GITHUB_TOKEN not set -- required for github-models provider"
        }
    }
}

# ---------------------------------------------------------------------------
# SUMMARY
# ---------------------------------------------------------------------------
Write-Host "`n$('-' * 60)" -ForegroundColor DarkGray

if ($Errors -eq 0 -and $Warnings -eq 0) {
    Write-Host "All checks passed -- Archim8 is ready." -ForegroundColor Green
} elseif ($Errors -eq 0) {
    Write-Host "$Warnings warning(s) -- optional gaps above. Core setup is functional." -ForegroundColor Yellow
} else {
    Write-Host "$Errors error(s), $Warnings warning(s) -- resolve errors before running pipelines." -ForegroundColor Red
    Write-Host "See README.md Quick start for setup instructions." -ForegroundColor DarkGray
}

# Write .archim8-doctor-ok marker if there are no hard errors
# Warnings are acceptable (e.g. Maven missing, warnings-only connectivity)
if ($Errors -eq 0) {
    $markerPath = Join-Path $Archim8Root ".archim8-doctor-ok"
    Get-Date -Format "yyyy-MM-ddTHH:mm:ss" | Set-Content $markerPath
    Write-Host "Marker written: .archim8-doctor-ok" -ForegroundColor DarkGray
}

Write-Host ""
