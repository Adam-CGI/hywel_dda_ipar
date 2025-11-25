# Pre-Deployment Validation Script
# Run this before deploying to Azure

param(
    [Parameter(Mandatory=$false)]
    [switch]$Fix = $false
)

function Write-Success { Write-Host "OK $args" -ForegroundColor Green }
function Write-Info { Write-Host "INFO $args" -ForegroundColor Cyan }
function Write-Warning { Write-Host "WARN $args" -ForegroundColor Yellow }
function Write-Error { Write-Host "ERROR $args" -ForegroundColor Red }

$hasErrors = 0
$hasWarnings = 0

Write-Info "=========================================="
Write-Info "Pre-Deployment Validation"
Write-Info "=========================================="

# Ensure we're in the flask_app directory
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptPath
Write-Info "Directory: $((Get-Location).Path)"
Write-Info ""

# CHECK: Required Files
Write-Info "CHECK 1: Required Files"
$requiredFiles = @("application.py", "requirements.txt", "runtime.txt", "startup.txt", ".env", "config.py")
foreach ($file in $requiredFiles) {
    if (Test-Path $file) {
        Write-Success "  $file"
    } else {
        Write-Error "  Missing: $file"
        $hasErrors++
    }
}

# CHECK: Runtime
Write-Info "`nCHECK 2: Python Runtime"
if (Test-Path "runtime.txt") {
    $runtime = (Get-Content "runtime.txt").Trim()
    if ($runtime -match "^python-3\.(9|10|11|12)$") {
        Write-Success "  $runtime"
    } else {
        Write-Error "  Invalid runtime: $runtime"
        $hasErrors++
    }
}

# CHECK: Essential Packages
Write-Info "`nCHECK 3: Requirements"
if (Test-Path "requirements.txt") {
    $requirements = Get-Content "requirements.txt"
    $essentialPackages = @("Flask", "gunicorn", "azure-storage-blob", "azure-cosmos", "azure-search-documents", "openai")
    
    foreach ($pkg in $essentialPackages) {
        $found = $false
        foreach ($line in $requirements) {
            if ($line -match "^$pkg") {
                $found = $true
                break
            }
        }
        if ($found) {
            Write-Success "  $pkg"
        } else {
            Write-Error "  Missing: $pkg"
            $hasErrors++
        }
    }
}

# CHECK: Startup Command
Write-Info "`nCHECK 4: Startup Command"
if (Test-Path "startup.txt") {
    $startup = (Get-Content "startup.txt").Trim()
    if ($startup -match "gunicorn.*application:app") {
        Write-Success "  Valid gunicorn command"
    } else {
        Write-Error "  Invalid startup command"
        $hasErrors++
    }
}

# CHECK: WSGI Entry Point
Write-Info "`nCHECK 5: WSGI Entry Point"
if (Test-Path "application.py") {
    $appContent = Get-Content "application.py" -Raw
    
    if ($appContent -match "app\s*=\s*create_app\(\)") {
        Write-Success "  Flask app creation found"
    } else {
        Write-Error "  Missing app = create_app()"
        $hasErrors++
    }
    
    if ($appContent -match "application\s*=\s*app") {
        Write-Success "  WSGI alias found"
    } else {
        Write-Warning "  Missing application = app alias"
        $hasWarnings++
    }
}

# CHECK: Environment Variables
Write-Info "`nCHECK 6: Environment Variables"
if (Test-Path ".env") {
    $envVars = @{}
    Get-Content ".env" | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#")) {
            if ($line -match "^([^=]+)=(.*)$") {
                $key = $matches[1].Trim()
                $value = $matches[2].Trim()
                if ($value -and $value -ne "your-*-here" -and $value -ne "...") {
                    $envVars[$key] = $value
                }
            }
        }
    }
    
    Write-Success "  Found $($envVars.Count) environment variables"
    
    $essentialEnvVars = @(
        "FLASK_ENV",
        "AZURE_STORAGE_CONNSTR",
        "AZURE_SEARCH_ENDPOINT",
        "AZURE_SEARCH_ADMIN_KEY",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_KEY",
        "COSMOS_ENDPOINT",
        "COSMOS_KEY",
        "AZURE_DOCINTEL_ENDPOINT",
        "AZURE_DOCINTEL_KEY"
    )
    
    $missingCount = 0
    foreach ($var in $essentialEnvVars) {
        if ($envVars.ContainsKey($var)) {
            Write-Success "  $var"
        } else {
            Write-Error "  Missing: $var"
            $missingCount++
        }
    }
    
    if ($missingCount -gt 0) {
        $hasErrors += $missingCount
    }
} else {
    Write-Error "  .env file not found"
    $hasErrors++
}

# CHECK: Azure CLI
Write-Info "`nCHECK 7: Azure CLI"
$azVersion = az version 2>$null
if ($azVersion) {
    Write-Success "  Azure CLI installed"
    
    $azAccount = az account show 2>$null
    if ($azAccount) {
        Write-Success "  Logged into Azure"
    } else {
        Write-Warning "  Not logged into Azure - run: az login"
        $hasWarnings++
    }
} else {
    Write-Error "  Azure CLI not installed"
    $hasErrors++
}

# CHECK: Directory Structure
Write-Info "`nCHECK 8: Directory Structure"
$requiredDirs = @("templates", "routes", "services")
foreach ($dir in $requiredDirs) {
    if (Test-Path $dir) {
        Write-Success "  $dir"
    } else {
        Write-Error "  Missing: $dir"
        $hasErrors++
    }
}

# SUMMARY
Write-Info "`n=========================================="
if ($hasErrors -gt 0) {
    Write-Error "VALIDATION FAILED - $hasErrors errors found"
    Write-Info "Fix the errors above before deploying"
    exit 1
} elseif ($hasWarnings -gt 0) {
    Write-Warning "VALIDATION PASSED WITH WARNINGS"
    Write-Info "Review the warnings above"
    Write-Info ""
    Write-Info "To deploy, run:"
    Write-Info "  .\deploy_webapp.ps1"
    exit 0
} else {
    Write-Success "VALIDATION PASSED - Ready to deploy"
    Write-Info ""
    Write-Info "To deploy, run:"
    Write-Info "  .\deploy_webapp.ps1"
    Write-Info ""
    Write-Info "With parameters:"
    Write-Host "  .\deploy_webapp.ps1 -WebAppName my-app -ResourceGroup my-rg" -ForegroundColor Gray
    exit 0
}
