# Setup Zscaler CA Certificate for Python, pip, and Azure CLI
# Run this script as Administrator

Write-Host "=== Zscaler CA Certificate Setup ===" -ForegroundColor Cyan
Write-Host ""

# Check if running as Administrator
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERROR: This script must be run as Administrator!" -ForegroundColor Red
    Write-Host "Right-click PowerShell and select 'Run as Administrator'" -ForegroundColor Yellow
    exit 1
}

# Paths
$zscalerPem = ".\ca_certificates\ZscalerRootCertificate-2048-SHA256.pem"
$customBundlePath = "$env:APPDATA\custom-ca-bundle.pem"

# Step 1: Copy Zscaler certificate to AppData
Write-Host "Step 1: Copying Zscaler certificate to $customBundlePath..." -ForegroundColor Green
if (Test-Path $zscalerPem) {
    Copy-Item $zscalerPem $customBundlePath -Force
    Write-Host "  [OK] Certificate copied successfully" -ForegroundColor Green
} else {
    Write-Host "  [ERROR] Zscaler certificate not found at $zscalerPem" -ForegroundColor Red
    exit 1
}

# Step 2: Configure pip to use custom CA bundle
Write-Host ""
Write-Host "Step 2: Configuring pip to use custom CA bundle..." -ForegroundColor Green
try {
    pip config set global.cert $customBundlePath
    Write-Host "  [OK] pip configured successfully" -ForegroundColor Green
} catch {
    Write-Host "  [ERROR] configuring pip: $_" -ForegroundColor Red
}

# Step 3: Set environment variables for Python requests library
Write-Host ""
Write-Host "Step 3: Setting environment variables..." -ForegroundColor Green
try {
    [System.Environment]::SetEnvironmentVariable("REQUESTS_CA_BUNDLE", $customBundlePath, "Machine")
    Write-Host "  [OK] REQUESTS_CA_BUNDLE set" -ForegroundColor Green
    
    [System.Environment]::SetEnvironmentVariable("SSL_CERT_FILE", $customBundlePath, "Machine")
    Write-Host "  [OK] SSL_CERT_FILE set" -ForegroundColor Green
    
    [System.Environment]::SetEnvironmentVariable("CURL_CA_BUNDLE", $customBundlePath, "Machine")
    Write-Host "  [OK] CURL_CA_BUNDLE set" -ForegroundColor Green
} catch {
    Write-Host "  [ERROR] setting environment variables: $_" -ForegroundColor Red
    Write-Host "  Make sure you're running as Administrator!" -ForegroundColor Yellow
}

# Step 4: Find and update Azure CLI certifi bundle
Write-Host ""
Write-Host "Step 4: Finding Azure CLI certifi bundle..." -ForegroundColor Green

$possiblePaths = @(
    "C:\Program Files (x86)\Microsoft SDKs\Azure\CLI2\Lib\site-packages\certifi\cacert.pem",
    "C:\Program Files\Microsoft SDKs\Azure\CLI2\Lib\site-packages\certifi\cacert.pem",
    "$env:USERPROFILE\.azure\python\Lib\site-packages\certifi\cacert.pem"
)

$azCliCertPath = $null
foreach ($path in $possiblePaths) {
    if (Test-Path $path) {
        $azCliCertPath = $path
        Write-Host "  [OK] Found Azure CLI certifi bundle at: $path" -ForegroundColor Green
        break
    }
}

if ($azCliCertPath) {
    # Check if Zscaler cert is already in the bundle
    $bundleContent = Get-Content $azCliCertPath -Raw
    if ($bundleContent -notmatch "Zscaler Root") {
        Write-Host "  Adding Zscaler certificate to Azure CLI bundle..." -ForegroundColor Yellow
        Get-Content $zscalerPem | Add-Content $azCliCertPath
        Write-Host "  [OK] Zscaler certificate added to Azure CLI bundle" -ForegroundColor Green
    } else {
        Write-Host "  [OK] Zscaler certificate already exists in Azure CLI bundle" -ForegroundColor Green
    }
} else {
    Write-Host "  [WARNING] Azure CLI certifi bundle not found in common locations" -ForegroundColor Yellow
    Write-Host "  Searching entire system (this may take a while)..." -ForegroundColor Yellow
    
    $found = Get-ChildItem -Path "C:\Program Files\" -Recurse -Filter cacert.pem -ErrorAction SilentlyContinue | 
             Where-Object { $_.FullName -match "Azure.*CLI" } | 
             Select-Object -First 1
    
    if ($found) {
        Write-Host "  [OK] Found at: $($found.FullName)" -ForegroundColor Green
        Get-Content $zscalerPem | Add-Content $found.FullName
        Write-Host "  [OK] Zscaler certificate added" -ForegroundColor Green
    } else {
        Write-Host "  [WARNING] Could not find Azure CLI certifi bundle" -ForegroundColor Yellow
        Write-Host "  You may need to manually add the certificate if Azure CLI has SSL issues" -ForegroundColor Yellow
    }
}

# Step 5: Update certifi for Python (used by many packages)
Write-Host ""
Write-Host "Step 5: Updating Python certifi bundle..." -ForegroundColor Green
try {
    $certifiPath = python -m certifi 2>$null
    if ($certifiPath -and (Test-Path $certifiPath)) {
        Write-Host "  Found certifi bundle at: $certifiPath" -ForegroundColor Cyan
        
        # Check if Zscaler cert is already in certifi
        $certifiContent = Get-Content $certifiPath -Raw
        if ($certifiContent -notmatch "Zscaler Root") {
            Get-Content $zscalerPem | Add-Content $certifiPath
            Write-Host "  [OK] Zscaler certificate added to certifi bundle" -ForegroundColor Green
        } else {
            Write-Host "  [OK] Zscaler certificate already exists in certifi bundle" -ForegroundColor Green
        }
    } else {
        Write-Host "  [WARNING] certifi not found or not installed" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  [WARNING] Could not update certifi: $_" -ForegroundColor Yellow
}

# Step 6: Verification
Write-Host ""
Write-Host "=== Verification ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Testing Python requests..." -ForegroundColor Yellow
try {
    python -c "import requests; r = requests.get('https://www.microsoft.com'); print(f'[OK] Python requests OK (Status: {r.status_code})')"
} catch {
    Write-Host "  [ERROR] Python requests failed: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "Testing Azure CLI..." -ForegroundColor Yellow
try {
    az version 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] Azure CLI OK" -ForegroundColor Green
    } else {
        Write-Host "  [WARNING] Azure CLI may have issues" -ForegroundColor Yellow
    }
} catch {
    Write-Host "  [WARNING] Could not test Azure CLI" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== Setup Complete ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "IMPORTANT: You must restart your terminal/IDE for environment variables to take effect!" -ForegroundColor Yellow
Write-Host ""
Write-Host "Environment variables set:" -ForegroundColor Cyan
Write-Host "  REQUESTS_CA_BUNDLE = $customBundlePath"
Write-Host "  SSL_CERT_FILE = $customBundlePath"
Write-Host "  CURL_CA_BUNDLE = $customBundlePath"
Write-Host ""
