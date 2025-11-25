# Azure App Service Deployment Checklist

## 🎯 Quick Start

```powershell
# 1. Navigate to flask_app directory
cd c:\Users\gille\git_repos\hywel_dda_rag\flask_app

# 2. Validate deployment readiness
.\validate_deployment.ps1

# 3. Deploy to Azure
.\deploy_webapp.ps1
```

---

## 📋 Pre-Deployment Checklist

### ✅ Local Environment
- [x] Python 3.11 installed
- [x] Azure CLI installed and logged in (`az login`)
- [x] `.env` file configured with all Azure credentials
- [x] Virtual environment activated (optional for deployment)
- [x] All dependencies in `requirements.txt`

### ✅ Required Files (All Present ✓)
- [x] `application.py` - WSGI entry point
- [x] `requirements.txt` - Python dependencies
- [x] `runtime.txt` - Python version (`python-3.11`)
- [x] `startup.txt` - Gunicorn startup command
- [x] `.env` - Environment variables (NOT committed to git)
- [x] `config.py` - Configuration module
- [x] `.deployment` - Azure deployment config

### ✅ Directory Structure
```
flask_app/
├── application.py          ✓ Main app entry point
├── config.py              ✓ Configuration
├── requirements.txt       ✓ Dependencies
├── runtime.txt            ✓ Python 3.11
├── startup.txt            ✓ Gunicorn command
├── .env                   ✓ Environment vars
├── routes/                ✓ Blueprint routes
│   ├── __init__.py
│   ├── documents.py
│   └── pages.py
├── services/              ✓ Business logic
│   ├── chat_service.py
│   ├── chunking_service.py
│   ├── cosmos_service.py
│   ├── embedding_service.py
│   ├── extraction_service.py
│   ├── indexing_pipeline_service.py
│   ├── search_index_service.py
│   ├── search_service.py
│   └── storage_service.py
└── templates/             ✓ HTML templates
    ├── base.html
    ├── chat.html
    ├── document_list.html
    └── ...
```

---

## 🚀 Deployment Configuration

### Current Configuration
```yaml
Resource Group: RG_300000000120926_Hywel_Dda_AI
Location: ukwest
App Name: app-hdipar-dev
Runtime: PYTHON:3.11
SKU: B1 (Basic)
```

### WSGI Entry Point
```python
# In application.py:
app = create_app()           # Flask app instance
application = app            # WSGI alias for Azure
```

### Startup Command (from startup.txt)
```bash
gunicorn --bind=0.0.0.0:8000 --timeout 600 --workers 4 --worker-class sync --access-logfile '-' --error-logfile '-' application:app
```

---

## 🔐 Environment Variables (Automatically Injected)

The deployment script will automatically inject these from your `.env` file:

### Application Settings
- `FLASK_ENV=development`
- `PORT=8000`
- `RESOURCE_GROUP=RG_300000000120926_Hywel_Dda_AI`
- `SUBSCRIPTION_ID=8fb6bbf9-f461-4ebb-9a0f-7636a6c8ad2b`
- `LOCATION=ukwest`

### Azure Storage
- `AZURE_STORAGE_ACCOUNT=sthdipardev`
- `AZURE_STORAGE_CONNSTR=DefaultEndpointsProtocol=https;...`
- Container names (raw, extracted, thumbs, manifests, archive)

### Azure AI Search
- `AZURE_SEARCH_ENDPOINT=https://ais-hdipar-dev.search.windows.net`
- `AZURE_SEARCH_ADMIN_KEY=[configured]`
- `AZURE_SEARCH_INDEX=ipar-chunks`

### Azure OpenAI
- `AZURE_OPENAI_ENDPOINT=https://aoai-hdipar-dev.openai.azure.com/`
- `AZURE_OPENAI_API_KEY=[configured]`
- `AZURE_OPENAI_EMBED_DEPLOYMENT=text-embedding-3-large`
- `AZURE_OPENAI_CHAT_DEPLOYMENT=gpt-4o-mini`

### Azure Document Intelligence
- `AZURE_DOCINTEL_ENDPOINT=https://di-hdipar-dev.cognitiveservices.azure.com/`
- `AZURE_DOCINTEL_KEY=[configured]`

### Azure Cosmos DB
- `COSMOS_ENDPOINT=https://cosmos-hdipar-dev.documents.azure.com:443/`
- `COSMOS_KEY=[configured]`
- `COSMOS_DB=ipar`
- Collection names (documents, lineage, events, users)

### Application Insights
- `APPLICATIONINSIGHTS_CONNECTION_STRING=[configured]`

---

## 🔧 Deployment Steps

### Step 1: Pre-Validation
```powershell
cd flask_app
.\validate_deployment.ps1
```

**Expected Output:**
- ✅ All required files present
- ✅ Valid Python runtime
- ✅ Essential packages in requirements.txt
- ✅ Valid startup command
- ✅ WSGI entry points found
- ✅ Environment variables configured
- ✅ Azure CLI logged in

### Step 2: Deploy Application
```powershell
.\deploy_webapp.ps1
```

**This will:**
1. ✅ Verify Azure login
2. ✅ Validate required files
3. ✅ Load environment variables from .env
4. ✅ Deploy code using `az webapp up`
5. ✅ Configure all application settings
6. ✅ Set startup command
7. ✅ Enable logging
8. ✅ Restart application
9. ✅ Display deployment summary

### Step 3: Verify Deployment
```powershell
# Check health endpoint
curl https://app-hdipar-dev.azurewebsites.net/health

# Check readiness
curl https://app-hdipar-dev.azurewebsites.net/ready

# View live logs
az webapp log tail --name app-hdipar-dev --resource-group RG_300000000120926_Hywel_Dda_AI
```

---

## 🔍 Troubleshooting

### Issue: "Application Error" or 503
**Solution:**
```powershell
# Check logs
az webapp log tail --name app-hdipar-dev --resource-group RG_300000000120926_Hywel_Dda_AI

# Verify app settings
az webapp config appsettings list --name app-hdipar-dev --resource-group RG_300000000120926_Hywel_Dda_AI

# Restart app
az webapp restart --name app-hdipar-dev --resource-group RG_300000000120926_Hywel_Dda_AI
```

### Issue: Import Errors
**Root Cause:** Absolute imports (`flask_app.*`) may fail if directory structure is incorrect.

**Solution:**
- Ensure `application.py` is in the root of the deployed folder
- Verify `routes/` and `services/` are subdirectories
- Check sys.path modifications in `application.py`

### Issue: Environment Variables Not Working
**Solution:**
```powershell
# Re-run deployment script (it will update settings)
.\deploy_webapp.ps1

# Or manually set a specific variable
az webapp config appsettings set --name app-hdipar-dev --resource-group RG_300000000120926_Hywel_Dda_AI --settings "FLASK_ENV=production"
```

### Issue: Gunicorn Not Starting
**Solution:**
```powershell
# Verify startup command
az webapp config show --name app-hdipar-dev --resource-group RG_300000000120926_Hywel_Dda_AI --query "appCommandLine"

# Update startup command
az webapp config set --name app-hdipar-dev --resource-group RG_300000000120926_Hywel_Dda_AI --startup-file "gunicorn --bind=0.0.0.0:8000 --timeout 600 --workers 4 application:app"
```

---

## 🌐 Post-Deployment

### Test Endpoints
```powershell
# Health check (should return 200)
curl https://app-hdipar-dev.azurewebsites.net/health

# Readiness check (should return 200 if all Azure services accessible)
curl https://app-hdipar-dev.azurewebsites.net/ready

# Chat UI (should redirect and load)
curl https://app-hdipar-dev.azurewebsites.net/

# Document list
curl https://app-hdipar-dev.azurewebsites.net/api/documents/ui/
```

### Monitor Application
```powershell
# Stream logs
az webapp log tail --name app-hdipar-dev --resource-group RG_300000000120926_Hywel_Dda_AI

# Download logs
az webapp log download --name app-hdipar-dev --resource-group RG_300000000120926_Hywel_Dda_AI --log-file app_logs.zip

# View in portal
az webapp browse --name app-hdipar-dev --resource-group RG_300000000120926_Hywel_Dda_AI
```

### Configure Custom Domain (Optional)
```powershell
# Add custom domain
az webapp config hostname add --webapp-name app-hdipar-dev --resource-group RG_300000000120926_Hywel_Dda_AI --hostname "your-domain.com"

# Configure SSL
az webapp config ssl bind --name app-hdipar-dev --resource-group RG_300000000120926_Hywel_Dda_AI --certificate-thumbprint [thumbprint] --ssl-type SNI
```

---

## 📊 Performance Tuning

### Recommended Settings for Production

**Gunicorn Workers:**
```bash
# Formula: (2 x CPU cores) + 1
# B1 SKU has 1 core, so: (2 x 1) + 1 = 3 workers
# Current: 4 workers (slightly over, but acceptable)
```

**Timeout Settings:**
```bash
# Current: 600 seconds (10 minutes)
# Good for document processing operations
# Reduce to 300 for faster failure detection if needed
```

**Scale Up Options:**
```powershell
# View available SKUs
az appservice plan list-skus

# Scale up to S1 (production)
az appservice plan update --name [plan-name] --resource-group RG_300000000120926_Hywel_Dda_AI --sku S1
```

---

## 🔒 Security Checklist

- [x] `.env` file NOT committed to git (.gitignore configured)
- [x] All secrets stored in Azure App Settings (encrypted at rest)
- [x] HTTPS enforced (Azure default)
- [ ] Authentication configured (External ID - future)
- [ ] CORS configured if needed
- [ ] IP restrictions configured if needed
- [x] Application Insights enabled for monitoring

---

## 📝 Useful Commands Reference

```powershell
# Deploy / Re-deploy
.\deploy_webapp.ps1

# Stream logs
az webapp log tail --name app-hdipar-dev --resource-group RG_300000000120926_Hywel_Dda_AI

# Restart app
az webapp restart --name app-hdipar-dev --resource-group RG_300000000120926_Hywel_Dda_AI

# Stop app
az webapp stop --name app-hdipar-dev --resource-group RG_300000000120926_Hywel_Dda_AI

# Start app
az webapp start --name app-hdipar-dev --resource-group RG_300000000120926_Hywel_Dda_AI

# View configuration
az webapp config show --name app-hdipar-dev --resource-group RG_300000000120926_Hywel_Dda_AI

# Update app setting
az webapp config appsettings set --name app-hdipar-dev --resource-group RG_300000000120926_Hywel_Dda_AI --settings "KEY=VALUE"

# Browse in portal
az webapp browse --name app-hdipar-dev --resource-group RG_300000000120926_Hywel_Dda_AI

# SSH into container (for debugging)
az webapp ssh --name app-hdipar-dev --resource-group RG_300000000120926_Hywel_Dda_AI
```

---

## ✅ Success Criteria

Your deployment is successful when:

1. ✅ Health endpoint returns 200: `/health`
2. ✅ Readiness endpoint returns 200: `/ready`
3. ✅ Chat UI loads: `/` (redirects to `/api/documents/ui/chat`)
4. ✅ Document list loads: `/api/documents/ui/`
5. ✅ No errors in application logs
6. ✅ Can upload and process a test PDF document
7. ✅ Search functionality works
8. ✅ Chat RAG functionality works

---

## 🎉 Next Steps After Deployment

1. **Test Full Pipeline:**
   - Upload a test PDF document
   - Verify extraction and indexing
   - Test search functionality
   - Test RAG chat with citations

2. **Configure Monitoring:**
   - Set up Application Insights alerts
   - Configure availability tests
   - Set up log analytics queries

3. **Implement Authentication:**
   - Configure External ID (Microsoft Entra)
   - Set up user roles
   - Test authentication flow

4. **Performance Testing:**
   - Load test with multiple concurrent users
   - Optimize database queries
   - Configure CDN if needed

5. **Documentation:**
   - Update README with production URL
   - Document API endpoints
   - Create user guide

---

**Last Updated:** November 6, 2025  
**Maintainer:** Hywel Dda AI Team  
**App URL:** https://app-hdipar-dev.azurewebsites.net
