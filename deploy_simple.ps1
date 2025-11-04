param(
    [string]$WebAppName = "app-hdipar-dev",
    [string]$ResourceGroup = "RG_300000000120926_Hywel_Dda_AI"
)

Write-Host "Deploying to: $WebAppName" -ForegroundColor Cyan
Write-Host "Resource Group: $ResourceGroup" -ForegroundColor Cyan

# Pre-flight checks
Write-Host "Running pre-flight checks..." -ForegroundColor Yellow
$requiredFiles = @("wsgi.py", "requirements.txt", "startup.sh", "app")
foreach ($file in $requiredFiles) {
    if (Test-Path $file) {
        Write-Host "  [OK] $file exists" -ForegroundColor Green
    } else {
        Write-Host "  [ERROR] $file not found" -ForegroundColor Red
        exit 1
    }
}

# Check if web app exists
Write-Host "Checking web app..." -ForegroundColor Yellow
$webAppExists = az webapp show --name $WebAppName --resource-group $ResourceGroup --query "name" -o tsv 2>$null
if (-not $webAppExists) {
    Write-Host "Web app $WebAppName not found. Please create it first." -ForegroundColor Red
    exit 1
}
Write-Host "Web app exists: $WebAppName" -ForegroundColor Green

# Package files
Write-Host "Creating deployment package..." -ForegroundColor Yellow
$tempDir = "deploy_temp"
if (Test-Path $tempDir) {
    Remove-Item $tempDir -Recurse -Force
}
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

# Copy files
Copy-Item "wsgi.py" -Destination $tempDir
Copy-Item "requirements.txt" -Destination $tempDir
Copy-Item "startup.sh" -Destination $tempDir
Copy-Item "app" -Destination $tempDir -Recurse

# Show what's being deployed
$fileCount = (Get-ChildItem $tempDir -Recurse -File).Count
Write-Host "Package contains $fileCount files" -ForegroundColor Green

# Clean up any existing zip
if (Test-Path "deploy.zip") {
    Remove-Item "deploy.zip" -Force
}

# Create zip using Python (ensures forward slashes for Linux)
Write-Host "Creating cross-platform zip..." -ForegroundColor Yellow
python -c @"
import zipfile
import os
from pathlib import Path

zip_path = 'deploy.zip'
source_dir = '$tempDir'

with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
    for root, dirs, files in os.walk(source_dir):
        for file in files:
            file_path = os.path.join(root, file)
            # Use forward slashes for cross-platform compatibility
            arcname = os.path.relpath(file_path, source_dir).replace(os.sep, '/')
            zipf.write(file_path, arcname)
            
print(f'Created {zip_path}')
"@

Remove-Item $tempDir -Recurse -Force

$zipSize = (Get-Item "deploy.zip").Length / 1MB
$zipSizeMB = [math]::Round($zipSize, 2)
Write-Host "Created deploy.zip: ${zipSizeMB} MB" -ForegroundColor Green

# Deploy to Azure
Write-Host "Deploying to Azure (this may take 2-5 minutes)..." -ForegroundColor Yellow
az webapp deployment source config-zip --resource-group $ResourceGroup --name $WebAppName --src "deploy.zip" --timeout 600

if ($LASTEXITCODE -eq 0) {
    Write-Host "Deployment successful!" -ForegroundColor Green
    
    # Restart the app
    Write-Host "Restarting web app..." -ForegroundColor Yellow
    az webapp restart --name $WebAppName --resource-group $ResourceGroup
    
    # Wait for app to start
    Write-Host "Waiting for app to start (20 seconds)..." -ForegroundColor Yellow
    Start-Sleep -Seconds 20
    
    # Health check
    $appUrl = "https://$WebAppName.azurewebsites.net"
    Write-Host "Testing health endpoint..." -ForegroundColor Yellow
    try {
        $response = Invoke-WebRequest -Uri "$appUrl/health" -UseBasicParsing -TimeoutSec 30
        if ($response.StatusCode -eq 200) {
            Write-Host "Health check passed!" -ForegroundColor Green
            Write-Host "App URL: $appUrl" -ForegroundColor Cyan
        } else {
            Write-Host "Health check returned status: $($response.StatusCode)" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "Health check failed - app may still be starting. Check: $appUrl" -ForegroundColor Yellow
    }
    
    Write-Host "Deployment complete!" -ForegroundColor Green
} else {
    Write-Host "Deployment failed!" -ForegroundColor Red
    exit 1
}
