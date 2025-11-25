# Azure CLI Setup and Login Script
# This script configures Azure CLI with SSL certificates and performs login
# Usage: .\setup-azure-cli.ps1

Write-Host "☁️  Setting up Azure CLI" -ForegroundColor Cyan
Write-Host "========================" -ForegroundColor Cyan
Write-Host ""

# Set up SSL certificates
. .\setup-ssl-env.ps1

# Check if Azure CLI is installed
Write-Host "Checking Azure CLI installation..." -ForegroundColor Yellow
$azVersion = az version --output json 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Azure CLI is not installed" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install Azure CLI from:" -ForegroundColor Yellow
    Write-Host "  https://aka.ms/installazurecliwindows" -ForegroundColor White
    exit 1
}

Write-Host "✓ Azure CLI is installed" -ForegroundColor Green
Write-Host ""

# Configure Azure CLI to use certificate
Write-Host "Configuring Azure CLI certificate settings..." -ForegroundColor Yellow
az config set core.ca_bundle=$env:REQUESTS_CA_BUNDLE

Write-Host "✓ Azure CLI configured to use Zscaler certificate" -ForegroundColor Green
Write-Host ""

# Check if already logged in
Write-Host "Checking Azure login status..." -ForegroundColor Yellow
$accountInfo = az account show 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Already logged in to Azure" -ForegroundColor Green
    az account show --output table
} else {
    Write-Host "Not currently logged in to Azure" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Initiating Azure login..." -ForegroundColor Green
    Write-Host "A browser window will open for authentication" -ForegroundColor Cyan
    az login
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "✓ Successfully logged in to Azure!" -ForegroundColor Green
        az account show --output table
    } else {
        Write-Host ""
        Write-Host "❌ Azure login failed" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "Azure CLI is ready to use!" -ForegroundColor Green
