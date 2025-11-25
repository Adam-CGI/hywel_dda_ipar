# Deployment Checklist - Flask App

## ✅ Pre-Deployment Verification

Run from `flask_app` directory:

```bash
cd flask_app
```

### 1. Required Files Present
- [x] `application.py` - WSGI entry point
- [x] `startup.txt` - Gunicorn command
- [x] `requirements.txt` - Dependencies with gunicorn
- [x] `runtime.txt` - Python 3.11
- [x] `.deployment` - Build config
- [x] `.env.example` - Environment template
- [x] `appsettings.json` - Azure app settings template

### 2. Test Import Structure
```bash
python -c "from application import app; print('✓ Success')"
```

### 3. Test Health Endpoints (local)
```bash
# Start app
python application.py

# In another terminal:
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

## 🚀 Deployment Commands

### Option 1: az webapp up (Recommended for first deploy)
```bash
cd flask_app

az webapp up \
  --name hdipar-app-dev \
  --resource-group rg-hdipar-dev \
  --location uksouth \
  --runtime "PYTHON:3.11" \
  --sku B1
```

### Option 2: Deploy to existing app
```bash
cd flask_app

# Create ZIP deployment package
az webapp deployment source config-zip \
  --name hdipar-app-dev \
  --resource-group rg-hdipar-dev \
  --src deploy.zip
```

### Option 3: Git-based deployment
```bash
# From flask_app directory
git init
git add .
git commit -m "Initial commit"

az webapp deployment source config-local-git \
  --name hdipar-app-dev \
  --resource-group rg-hdipar-dev

git remote add azure <git-url-from-above-command>
git push azure main
```

## 📝 Post-Deployment Steps

### 1. Configure App Settings
```bash
# Set environment variables (use your actual values)
az webapp config appsettings set \
  --name hdipar-app-dev \
  --resource-group rg-hdipar-dev \
  --settings \
    FLASK_ENV=production \
    AZURE_STORAGE_CONNSTR="your-connection-string" \
    AZURE_SEARCH_ENDPOINT="your-search-endpoint" \
    AZURE_SEARCH_ADMIN_KEY="your-search-key" \
    AZURE_OPENAI_ENDPOINT="your-openai-endpoint" \
    AZURE_OPENAI_API_KEY="your-openai-key" \
    COSMOS_ENDPOINT="your-cosmos-endpoint" \
    COSMOS_KEY="your-cosmos-key" \
    AZURE_DOCINTEL_ENDPOINT="your-di-endpoint" \
    AZURE_DOCINTEL_KEY="your-di-key"
```

Or use the appsettings.json file:
```bash
# Edit appsettings.json with your values, then:
az webapp config appsettings set \
  --name hdipar-app-dev \
  --resource-group rg-hdipar-dev \
  --settings @appsettings.json
```

### 2. Verify Deployment
```bash
# Get app URL
APP_URL=$(az webapp show \
  --name hdipar-app-dev \
  --resource-group rg-hdipar-dev \
  --query "defaultHostName" -o tsv)

# Test health endpoint
curl https://$APP_URL/health

# Test readiness endpoint
curl https://$APP_URL/ready
```

### 3. View Logs
```bash
# Enable logging
az webapp log config \
  --name hdipar-app-dev \
  --resource-group rg-hdipar-dev \
  --application-logging filesystem \
  --level information

# Stream logs
az webapp log tail \
  --name hdipar-app-dev \
  --resource-group rg-hdipar-dev
```

### 4. Enable Managed Identity (Recommended)
```bash
az webapp identity assign \
  --name hdipar-app-dev \
  --resource-group rg-hdipar-dev

# Grant permissions to Azure resources (Storage, Search, etc.)
```

## 🔍 Troubleshooting

### Check Deployment Status
```bash
az webapp deployment list-publishing-credentials \
  --name hdipar-app-dev \
  --resource-group rg-hdipar-dev
```

### SSH into Container
```bash
az webapp ssh \
  --name hdipar-app-dev \
  --resource-group rg-hdipar-dev
```

### Common Issues

1. **Import errors**: Verify all imports use relative paths (`from config import` not `from flask_app.config`)
2. **Port binding**: Azure sets PORT env var automatically, app uses PORT from config
3. **Startup timeout**: Increase timeout in startup.txt if needed
4. **Missing dependencies**: Verify requirements.txt includes gunicorn

## 📊 Monitoring

### Application Insights
- Configure `APPLICATIONINSIGHTS_CONNECTION_STRING` app setting
- View metrics in Azure Portal > Application Insights

### Health Checks
- Configure in Azure Portal > Health Check
- Set path to `/health`
