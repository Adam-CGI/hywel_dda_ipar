# ============================================================================
# Azure App Service Deployment Script for Flask App
# ============================================================================
# This script deploys the flask_app to Azure App Service using az webapp up
# and configures all necessary environment variables from .env file
# ============================================================================

param(
    [Parameter(Mandatory=$false)]
    [string]$WebAppName = "app-hdipar-dev",
    
    [Parameter(Mandatory=$false)]
    [string]$ResourceGroup = "RG_300000000120926_Hywel_Dda_AI",
    
    [Parameter(Mandatory=$false)]
    [string]$Location = "uksouth",
    
    [Parameter(Mandatory=$false)]
    [string]$Sku = "S1",
    
    [Parameter(Mandatory=$false)]
    [string]$Runtime = "PYTHON:3.11"
)

# Color output functions
function Write-Success { Write-Host "OK $args" -ForegroundColor Green }
function Write-Info { Write-Host "INFO $args" -ForegroundColor Cyan }
function Write-Warning { Write-Host "WARN $args" -ForegroundColor Yellow }
function Write-Error { Write-Host "ERROR $args" -ForegroundColor Red }

Write-Info "=========================================="
Write-Info "Flask App Deployment to Azure App Service"
Write-Info "=========================================="

# Ensure we're in the flask_app directory
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptPath
Write-Info "Working directory: $(Get-Location)"

# ============================================================================
# STEP 1: Pre-deployment Validation
# ============================================================================
Write-Info "`n[STEP 1] Pre-deployment validation..."

# Check if logged into Azure
Write-Info "Checking Azure login status..."
$azAccount = az account show 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Error "Not logged into Azure. Running 'az login'..."
    az login
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Azure login failed. Exiting."
        exit 1
    }
}
Write-Success "Azure login verified"

# Check required files
$requiredFiles = @(
    "application.py",
    "requirements.txt",
    "runtime.txt",
    "startup.txt",
    ".env"
)

foreach ($file in $requiredFiles) {
    if (Test-Path $file) {
        Write-Success "Found: $file"
    } else {
        Write-Error "Missing required file: $file"
        exit 1
    }
}

# Validate Python entry point
Write-Info "Validating Flask application entry point..."
$appContent = Get-Content "application.py" -Raw
if ($appContent -match "app\s*=\s*create_app\(\)" -and $appContent -match "application\s*=\s*app") {
    Write-Success "WSGI entry point 'app' and 'application' found"
} else {
    Write-Warning "Could not verify WSGI entry point in application.py"
}

# ============================================================================
# STEP 2: Parse .env file for environment variables
# ============================================================================
Write-Info "`n[STEP 2] Loading environment variables from .env..."

if (-not (Test-Path ".env")) {
    Write-Error ".env file not found! Please create it from .env.example"
    exit 1
}

# Parse .env file (skip comments and empty lines)
$envVars = @{}
Get-Content ".env" | ForEach-Object {
    $line = $_.Trim()
    if ($line -and -not $line.StartsWith("#")) {
        if ($line -match "^(.+)=(.*)$") {
            $key = $matches[1].Trim()
            $value = $matches[2].Trim()
            # Remove quotes if present
            $value = $value -replace '^["\x27]|["\x27]$'
            $envVars[$key] = $value
        }
    }
}

Write-Success "Loaded $($envVars.Count) environment variables from .env"

# ============================================================================
# STEP 3: Deploy application using az webapp up
# ============================================================================
Write-Info "`n[STEP 3] Deploying application to Azure..."

# Build az webapp up command
$deployArgs = @(
    "webapp", "up"
    "--runtime", $Runtime
    "--sku", $Sku
    "--location", $Location
)

if ($WebAppName) {
    $deployArgs += "--name", $WebAppName
    Write-Info "Using webapp name: $WebAppName"
}

if ($ResourceGroup) {
    $deployArgs += "--resource-group", $ResourceGroup
    Write-Info "Using resource group: $ResourceGroup"
}

Write-Info "Running: az $($deployArgs -join ' ')"
Write-Info "This may take several minutes..."

# Execute deployment
& az $deployArgs

if ($LASTEXITCODE -ne 0) {
    Write-Error "Deployment failed!"
    exit 1
}

Write-Success "Application deployed successfully"

# Get the webapp name and resource group from deployment output
if (-not $WebAppName) {
    Write-Info "Detecting deployed webapp name..."
    # Try to get from last deployment
    $queryFilter = "[?state=='Running'].{name:name, rg:resourceGroup}"
    $webappList = az webapp list --query $queryFilter -o json | ConvertFrom-Json
    if ($webappList -and $webappList.Count -gt 0) {
        $WebAppName = $webappList[0].name
        $ResourceGroup = $webappList[0].rg
        Write-Info "Detected webapp: $WebAppName in resource group: $ResourceGroup"
    }
}

# ============================================================================
# STEP 4: Configure Application Settings (Environment Variables)
# ============================================================================
Write-Info "`n[STEP 4] Configuring application settings..."

if (-not $WebAppName -or -not $ResourceGroup) {
    Write-Warning "Cannot configure app settings without webapp name and resource group"
    Write-Warning "Please run this script again with -WebAppName and -ResourceGroup parameters"
    exit 0
}

# Configure app settings in batches to avoid command line length limits
$settingsArgs = @()
foreach ($key in $envVars.Keys) {
    $value = $envVars[$key]
    # Escape special characters for Azure CLI
    $escapedValue = $value -replace '"', '\"'
    $settingsArgs += "$key=`"$escapedValue`""
}

Write-Info "Configuring $($settingsArgs.Count) application settings..."

# Split into chunks of 10 to avoid command line length issues
$chunkSize = 10
for ($i = 0; $i -lt $settingsArgs.Count; $i += $chunkSize) {
    $chunk = $settingsArgs[$i..[Math]::Min($i + $chunkSize - 1, $settingsArgs.Count - 1)]
    Write-Info "Setting batch $([Math]::Floor($i / $chunkSize) + 1) of $([Math]::Ceiling($settingsArgs.Count / $chunkSize))..."
    
    az webapp config appsettings set `
        --name $WebAppName `
        --resource-group $ResourceGroup `
        --settings $chunk `
        --output none
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to set application settings batch $([Math]::Floor($i / $chunkSize) + 1)"
    }
}

Write-Success "Application settings configured"

# ============================================================================
# STEP 5: Configure startup command
# ============================================================================
Write-Info "`n[STEP 5] Configuring startup command..."

$startupCommand = Get-Content "startup.txt" -Raw
$startupCommand = $startupCommand.Trim()

Write-Info "Setting startup command: $startupCommand"

az webapp config set `
    --name $WebAppName `
    --resource-group $ResourceGroup `
    --startup-file "$startupCommand" `
    --output none

if ($LASTEXITCODE -eq 0) {
    Write-Success "Startup command configured"
} else {
    Write-Warning "Failed to set startup command (may already be set)"
}

# ============================================================================
# STEP 6: Enable logging
# ============================================================================
Write-Info "`n[STEP 6] Enabling application logging..."

az webapp log config `
    --name $WebAppName `
    --resource-group $ResourceGroup `
    --web-server-logging filesystem `
    --level information `
    --output none

if ($LASTEXITCODE -eq 0) {
    Write-Success "Logging enabled"
} else {
    Write-Warning "Failed to enable logging"
}

# ============================================================================
# STEP 7: Restart application
# ============================================================================
Write-Info "`n[STEP 7] Restarting application to apply changes..."

az webapp restart `
    --name $WebAppName `
    --resource-group $ResourceGroup `
    --output none

if ($LASTEXITCODE -eq 0) {
    Write-Success "Application restarted"
} else {
    Write-Error "Failed to restart application"
}

# ============================================================================
# STEP 8: Display deployment information
# ============================================================================
Write-Info "`n=========================================="
Write-Success "Deployment Complete!"
Write-Info "=========================================="

$webappUrl = "https://$WebAppName.azurewebsites.net"

Write-Info ""
Write-Info "📋 Deployment Summary:"
Write-Info "  • Web App Name: $WebAppName"
Write-Info "  • Resource Group: $ResourceGroup"
Write-Info "  • Location: $Location"
Write-Info "  • Runtime: $Runtime"
Write-Info "  • SKU: $Sku"
Write-Info "  • URL: $webappUrl"
Write-Info ""
Write-Info "🔍 Useful Commands:"
Write-Info "  • View logs:       az webapp log tail --name $WebAppName --resource-group $ResourceGroup"
Write-Info "  • Browse app:      az webapp browse --name $WebAppName --resource-group $ResourceGroup"
Write-Info "  • Check health:    curl $webappUrl/health"
Write-Info "  • Check readiness: curl $webappUrl/ready"
Write-Info ""
Write-Warning "Note: The application may take 2-3 minutes to fully start up"
Write-Info "   Check the /health endpoint to verify the app is running"
Write-Info ""
Write-Info "Opening browser in 5 seconds..."
Start-Sleep -Seconds 5
Start-Process $webappUrl

Write-Info "`nDeployment script completed successfully!"
