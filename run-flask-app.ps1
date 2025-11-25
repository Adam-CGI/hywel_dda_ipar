# Flask App Startup Script with SSL Certificate Configuration
# This script sets up the environment and starts the Flask application
# Usage: .\run-flask-app.ps1

Write-Host "🚀 Starting Hywel Dda IPAR Document Miner" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

# Set up SSL certificates
. .\setup-ssl-env.ps1

# Check if virtual environment exists
if (-not (Test-Path ".venv")) {
    Write-Host "❌ Virtual environment not found at .venv" -ForegroundColor Red
    Write-Host "Please run setup-python-env.ps1 first" -ForegroundColor Yellow
    exit 1
}

# Activate virtual environment
Write-Host "Activating virtual environment..." -ForegroundColor Yellow
& .\.venv\Scripts\Activate.ps1

# Check if .env file exists
if (-not (Test-Path "flask_app\.env")) {
    Write-Host "⚠️  Warning: .env file not found in flask_app directory" -ForegroundColor Yellow
    Write-Host "   The app will use default/environment variables" -ForegroundColor Yellow
    Write-Host ""
}

# Change to flask_app directory and run the app
Write-Host "Starting Flask application on port 8000..." -ForegroundColor Green
Write-Host ""
Set-Location flask_app
python application.py
