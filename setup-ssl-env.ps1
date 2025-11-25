# Setup SSL Certificate Environment for Zscaler
# This script configures all necessary environment variables for SSL certificate validation
# Run this before any Azure or Python operations: . .\setup-ssl-env.ps1

$certPath = Join-Path $PSScriptRoot "ca_certificates\ZscalerRootCertificate-2048-SHA256.pem"

# Python SSL certificates
$env:REQUESTS_CA_BUNDLE = $certPath
$env:SSL_CERT_FILE = $certPath
$env:CURL_CA_BUNDLE = $certPath
$env:PIP_CERT = $certPath

# Azure CLI SSL certificate
$env:AZURE_CLI_DISABLE_CONNECTION_VERIFICATION = "0"  # Keep verification on
$env:REQUESTS_CA_BUNDLE = $certPath

# Node.js (if needed)
$env:NODE_EXTRA_CA_CERTS = $certPath

# Git SSL certificate
$env:GIT_SSL_CAINFO = $certPath

Write-Host "✓ SSL certificate environment configured" -ForegroundColor Green
Write-Host "  Certificate: $certPath" -ForegroundColor Cyan
Write-Host ""
Write-Host "Environment variables set:" -ForegroundColor Yellow
Write-Host "  REQUESTS_CA_BUNDLE=$env:REQUESTS_CA_BUNDLE"
Write-Host "  SSL_CERT_FILE=$env:SSL_CERT_FILE"
Write-Host "  CURL_CA_BUNDLE=$env:CURL_CA_BUNDLE"
Write-Host "  PIP_CERT=$env:PIP_CERT"
Write-Host "  NODE_EXTRA_CA_CERTS=$env:NODE_EXTRA_CA_CERTS"
Write-Host "  GIT_SSL_CAINFO=$env:GIT_SSL_CAINFO"
Write-Host ""
Write-Host "You can now run:" -ForegroundColor Green
Write-Host "  - pip install (Python packages)"
Write-Host "  - az login (Azure CLI)"
Write-Host "  - python application.py (Flask app)"
