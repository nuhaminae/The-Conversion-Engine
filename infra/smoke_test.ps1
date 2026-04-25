# infram/smoke_test.ps1
#
# This script performs a "Day 0" readiness check to ensure the environment
# is correctly configured to run the Conversion Engine project.
#
# RUN: .\infra\smoke_test.ps1

# --- Setup: Helper functions ---
function Write-Pass {
    param([string]$Message)
    Write-Host "[ " -NoNewline; Write-Host "PASS" -ForegroundColor Green -NoNewline; Write-Host " ] $Message"
}

function Write-Fail {
    param([string]$Message)
    Write-Host "[ " -NoNewline; Write-Host "FAIL" -ForegroundColor Red -NoNewline; Write-Host " ] $Message"
}

function Write-Warn {
    param([string]$Message)
    Write-Host "[ " -NoNewline; Write-Host "WARN" -ForegroundColor Yellow -NoNewline; Write-Host " ] $Message"
}

function Test-Command {
    param([string]$Command)
    if (Get-Command $Command -ErrorAction SilentlyContinue) {
        Write-Pass "Command '$Command' is installed."
    } else {
        Write-Fail "Command '$Command' is not found. Please install it."
    }
}

function Get-VariableStatus {
    param([string]$VarName)
    $envVar = Get-ChildItem Env: | Where-Object { $_.Name -eq $VarName }
    if ($envVar) {
        Write-Pass "Environment variable '$VarName' is set."
    } else {
        Write-Fail "Environment variable '$VarName' is not set. Please add it to your .env file."
    }
}

Write-Host "--- Starting Conversion Engine Smoke Test ---"
Write-Host "This test will check your local environment configuration."

# --- 1. Check for required tools ---
Write-Host "`n1. Checking for required tools..."
Test-Command "docker"
Test-Command "poetry"
Test-Command "git"

# --- 2. Check for and load environment file ---
Write-Host "`n2. Checking for .env file..."
$envFile = "./.env"

if (Test-Path $envFile) {
    Write-Pass ".env file found at project root."
    # Load environment variables from .env file
    Get-Content $envFile | ForEach-Object {
        if ($_ -match '^(?<key>[^=]+)=(?<value>.*)$') {
            [System.Environment]::SetEnvironmentVariable($matches.key, $matches.value, 'Process')
        }
    }
} else {
    Write-Fail ".env file not found at project root. Please create one from the template."
    exit 1
}

# --- 3. Check for required environment variables ---
Write-Host "`n3. Checking for essential API keys and variables..."
Get-VariableStatus "OPENROUTER_API_KEY"
Get-VariableStatus "RESEND_API_KEY"
Get-VariableStatus "HUBSPOT_API_KEY"
Get-VariableStatus "LANGFUSE_SECRET_KEY"
Get-VariableStatus "LANGFUSE_PUBLIC_KEY"
Get-VariableStatus "SENDER_EMAIL"

# --- 4. Check project structure ---
Write-Host "`n4. Checking for key directories and files..."
if (Test-Path "./pyproject.toml") { Write-Pass "File 'pyproject.toml' found at project root." } else { Write-Fail "File 'pyproject.toml' is missing." }
if (Test-Path "./conversion_engine_backend/main.py") { Write-Pass "Directory 'conversion_engine_backend' with main.py found." } else { Write-Fail "'main.py' not found." }
"enrichment", "llm", "services" | ForEach-Object {
    if (Test-Path "./$_") { Write-Pass "Logic directory '$_/' found." } else { Write-Fail "Logic directory '$_/' is missing." }
}
if (Test-Path "./data") { Write-Pass "Directory 'data/' found." } else { Write-Warn "Directory 'data/' is missing." }


# --- 5. Check Docker status ---
Write-Host "`n5. Checking Docker service status..."
docker info | Out-Null
if ($?) {
    Write-Pass "Docker daemon is running."
} else {
    Write-Fail "Docker daemon is not running. Please start Docker."
}

Write-Host "`n--- Smoke Test Complete ---"
Write-Host "Review the output above. Address any FAIL or WARN messages to ensure a smooth project experience."
