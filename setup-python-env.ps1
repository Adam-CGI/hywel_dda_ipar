# Python 3.11 Environment Setup Script
Write-Host "Setting up Python 3.11 Environment" -ForegroundColor Cyan
Write-Host ""

# Set up SSL certificates first
. .\setup-ssl-env.ps1

# Remove old virtual environment if it exists
if (Test-Path ".venv") {
    Write-Host "Removing existing virtual environment..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force .venv
}

# Create new virtual environment with Python 3.11
Write-Host "Creating virtual environment with Python 3.11..." -ForegroundColor Yellow
py -3.11 -m venv .venv

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& .\.venv\Scripts\Activate.ps1

# Upgrade pip
Write-Host "Upgrading pip..." -ForegroundColor Yellow
python -m pip install --upgrade pip

# Install dependencies
Write-Host ""
Write-Host "Installing Flask app dependencies..." -ForegroundColor Green
Write-Host "This may take a few minutes..." -ForegroundColor Yellow
Write-Host ""

pip install -r flask_app\requirements.txt

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Python environment setup complete!" -ForegroundColor Green
    Write-Host ""
    Write-Host "To start the Flask app, run: .\run-flask-app.ps1" -ForegroundColor Yellow
}
else {
    Write-Host ""
    Write-Host "Installation failed!" -ForegroundColor Red
    exit 1
}
