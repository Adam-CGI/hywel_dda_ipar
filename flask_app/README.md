# Azure Deployment Files for flask_app

This directory contains a self-contained Flask application ready for Azure App Service deployment.

## Deployment Instructions

### Deploy to Azure App Service (Linux)

```bash
# Navigate to the flask_app directory
cd flask_app

# Login to Azure (if not already logged in)
az login

# Deploy using az webapp up (creates app if doesn't exist)
az webapp up \
  --name hdipar-app-dev \
  --resource-group rg-hdipar-dev \
  --location uksouth \
  --runtime "PYTHON:3.11" \
  --sku B1

# Configure environment variables in Azure Portal or via CLI
az webapp config appsettings set \
  --name hdipar-app-dev \
  --resource-group rg-hdipar-dev \
  --settings @appsettings.json
```

### Test Locally

```bash
# From the flask_app directory
cd flask_app

# Create virtual environment
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Copy and configure .env file
copy .env.example .env
# Edit .env with your Azure service credentials

# Run locally
python application.py

# Or use gunicorn (production server)
gunicorn --bind=0.0.0.0:8000 --timeout 600 application:app
```

## Files Overview

- `application.py` - Main Flask app entry point (Azure auto-detects this)
- `startup.txt` - Gunicorn configuration for Azure App Service
- `requirements.txt` - Python dependencies
- `runtime.txt` - Python version specification
- `.deployment` - Azure build configuration
- `.env.example` - Environment variable template

## Structure

```
flask_app/
├── application.py       # WSGI entry point
├── config.py           # Configuration & Azure clients
├── startup.txt         # Azure startup command
├── requirements.txt    # Dependencies
├── runtime.txt         # Python 3.11
├── .deployment         # Build config
├── .env.example        # Env template
├── routes/             # Flask blueprints
├── services/           # Business logic
└── templates/          # HTML templates
```

## Important Notes

1. **All imports use relative paths** - services use `from config import` not `from flask_app.config`
2. **Self-contained** - No dependencies on parent directory
3. **Azure-ready** - Includes all required deployment files
4. **Environment-based** - Uses .env for configuration

## Health Checks

- `/health` - Basic health check
- `/ready` - Readiness probe (checks Azure service connections)

## Default Routes

- `/` - Redirects to chat UI
- `/api/documents/ui/chat` - Chat interface
- `/api/documents/ui/` - Document list
- `/api/documents/upload` - Upload endpoint
