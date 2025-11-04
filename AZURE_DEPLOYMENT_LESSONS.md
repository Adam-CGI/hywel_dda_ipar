# 2025-11-03: Successful ZIP Deployment to Azure App Service

## What Was Uploaded

The following files and folders were included in the deployment ZIP package:

- `wsgi.py` (WSGI entry point)
- `requirements.txt` (Python dependencies)
- `startup.sh` (startup script for gunicorn)
- `app/` directory (all application code, including routes, services, templates, and models)

**Note:** The ZIP was created from the project root, with no extra parent folder. All files are at the root of the ZIP as required by Azure App Service Linux.

## How the Deployment Was Performed

1. **Stopped the App Service** to clear any stuck deployment:
    ```powershell
    $RG = "RG_300000000120926_Hywel_Dda_AI"
    $Web = "app-hdipar-dev"
    az webapp stop -g $RG -n $Web
    Start-Sleep -Seconds 5
    ```

2. **Started the App Service** after a short wait:
    ```powershell
    az webapp start -g $RG -n $Web
    Start-Sleep -Seconds 10
    ```

3. **Verified the deployment package exists:**
    ```powershell
    Test-Path deploy.zip  # Should return True
    ```

4. **Deployed the ZIP package using the Azure CLI with the --clean flag:**
    ```powershell
    az webapp deploy -g $RG -n $Web --src-path deploy.zip --type zip --clean true --restart true --timeout 600
    ```
    - The `--clean true` flag ensures the wwwroot is wiped before deploying, which resolves issues with stuck or partial deployments.
    - The `--restart true` flag restarts the app after deployment.

## Key Points

- The deployment package must have all files at the root (no extra parent folder).
- The `deploy.zip` was created using Python's `zipfile` module for cross-platform compatibility.
- The App Service was stopped and started to clear any deployment locks.
- The `az webapp deploy` command with `--clean` was used to ensure a clean deployment.
- After deployment, the app started successfully and gunicorn was able to find `wsgi.py`.

---
**This process is now the recommended approach for reliable Azure App Service deployments for this project.**
# Azure App Service Deployment - Lessons Learned

## Deployment Success Summary
**Date**: October 23, 2025  
**App Service**: app-hdipar-dev (B1 Linux tier, Python 3.11)  
**Deployment Method**: ZIP deployment via Azure CLI

---

## Critical Issue Resolved: Windows → Linux Path Incompatibility

### The Problem
When creating deployment packages on **Windows** using PowerShell's `Compress-Archive`, the resulting ZIP file contains **backslash paths** (e.g., `app\services\__init__.py`). When Azure extracts this ZIP on **Linux**, these backslashes are interpreted as **literal filename characters**, NOT directory separators. This caused:

```
Directory contents: ['app\\services\\__pycache__\\...']
App path: /tmp/8de1256aa02cdb3/app
App exists: False  ❌
```

The `app` directory didn't exist because it was never created - the files had literal backslashes in their names!

### The Solution
Use Python's `zipfile` module instead of PowerShell's `Compress-Archive`. Python's `zipfile` automatically uses **forward slashes** (POSIX-style paths) in ZIP archives, ensuring cross-platform compatibility.

**Before (Broken)**:
```powershell
Compress-Archive -Path "$tempDir\*" -DestinationPath "deploy.zip" -Force
```

**After (Working)**:
```powershell
python -c "import zipfile, os; z = zipfile.ZipFile('deploy.zip', 'w', zipfile.ZIP_DEFLATED); [z.write(os.path.join(r,f), os.path.relpath(os.path.join(r,f), 'deploy_temp')) for r,_,fs in os.walk('deploy_temp') for f in fs]; z.close()"
```

---

## Key Architectural Changes Made

### 1. **Renamed `app.py` → `run.py`**
**Why**: Avoided circular import conflict between root-level `app.py` and the `app/` package.

**Before**:
```
hywel_dda_rag/
├── app.py          # ❌ Conflicts with app/ package
└── app/
    └── __init__.py
```

**After**:
```
hywel_dda_rag/
├── run.py          # ✅ Local development entry point (not deployed)
├── wsgi.py         # ✅ Production entry point (deployed)
└── app/
    └── __init__.py # Contains create_app() factory
```

### 2. **Created `wsgi.py` Production Entry Point**
Dedicated WSGI entry point for Gunicorn with explicit path handling:

```python
import sys
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir in sys.path:
    sys.path.remove(current_dir)
sys.path.insert(0, current_dir)

from app import create_app
app = create_app()
```

**Key insight**: Azure extracts files to `/tmp/<hash>/` and doesn't automatically add it to `PYTHONPATH`, so we must do it explicitly.

### 3. **Moved `create_app()` to `app/__init__.py`**
Application factory function moved from `app.py` into the `app/` package to follow Flask best practices and avoid the circular import.

### 4. **Simplified `startup.sh`**
Clean 6-line startup script:

```bash
#!/bin/bash
echo "Starting Hywel Dda IPAR Document Miner"
cd /tmp/8de1256aa02cdb3 || cd /home/site/wwwroot
exec gunicorn --bind=0.0.0.0:8000 --workers=2 --timeout=120 wsgi:app
```

**Important**: Must use **ASCII-only** characters. Special characters like `✓` cause bash parsing errors on Linux.

---

## Deployment Checklist

### Pre-Deployment
- [ ] Ensure all files use **UTF-8 encoding without BOM**
- [ ] Verify `wsgi.py` exists and imports `create_app` correctly
- [ ] Confirm `startup.sh` has **LF line endings** (not CRLF)
- [ ] Test local imports: `python -c "from app import create_app; app = create_app()"`
- [ ] Verify all environment variables are set in Azure App Service

### Deployment Package Requirements
```
deploy_temp/
├── wsgi.py                    # WSGI entry point
├── requirements.txt           # Python dependencies
├── startup.sh                 # Startup script (LF line endings!)
└── app/                       # Application package
    ├── __init__.py            # Must contain create_app()
    ├── config.py
    ├── auth.py
    ├── routes/
    ├── services/
    └── templates/             # UI templates (HTMX + Tailwind)
```

**Exclude from deployment**:
- `run.py` (local development only)
- `tests/`
- `scripts/`
- `logs/`
- `.env` files
- `__pycache__/`
- `.git/`

### Deployment Script Best Practices

#### Use Python for ZIP Creation
```powershell
# Create temp directory with clean structure
$tempDir = "deploy_temp"
New-Item -ItemType Directory -Path $tempDir -Force | Out-Null

# Copy files
Copy-Item "wsgi.py" -Destination $tempDir
Copy-Item "requirements.txt" -Destination $tempDir
Copy-Item "startup.sh" -Destination $tempDir
Copy-Item "app" -Destination $tempDir -Recurse

# Use Python's zipfile for cross-platform compatibility
python -c "import zipfile, os; z = zipfile.ZipFile('deploy.zip', 'w', zipfile.ZIP_DEFLATED); [z.write(os.path.join(r,f), os.path.relpath(os.path.join(r,f), 'deploy_temp')) for r,_,fs in os.walk('deploy_temp') for f in fs]; z.close()"
```

#### Deploy with Extended Timeout
```powershell
az webapp deployment source config-zip `
    --resource-group $ResourceGroup `
    --name $WebAppName `
    --src "deploy.zip" `
    --timeout 600  # 10 minutes for large dependencies
```

---

## Common Pitfalls & Solutions

### Issue 1: "ModuleNotFoundError: No module named 'app'"
**Cause**: ZIP created with Windows backslashes on Linux system  
**Solution**: Use Python's `zipfile` module instead of `Compress-Archive`

### Issue 2: "startup.sh: not found" or syntax errors
**Cause**: 
- CRLF line endings (Windows style) instead of LF (Linux style)
- Special characters (e.g., `✓`, `→`) in script
**Solution**: 
- Use UTF-8 encoding with LF line endings
- Use ASCII-only characters in bash scripts

### Issue 3: Circular import errors
**Cause**: Root-level `app.py` conflicts with `app/` package  
**Solution**: Rename to `run.py` or use `wsgi.py` as entry point

### Issue 4: Deployment timeout
**Cause**: Large dependencies (pandas, numpy, Azure SDKs) take 8-10 minutes to install  
**Solution**: 
- Increase timeout to 600 seconds (`--timeout 600`)
- Deployment continues in background even after CLI timeout
- Check logs: `az webapp log tail --name <app-name> --resource-group <rg>`

### Issue 5: Environment variables not found
**Cause**: Azure App Service settings not configured  
**Solution**: Set all required variables:
```powershell
az webapp config appsettings set --name $WebAppName --resource-group $ResourceGroup --settings `
    AUTH_USERNAME="admin" `
    AUTH_PASSWORD="<secure-password>" `
    AZURE_STORAGE_CONNSTR="<connection-string>" `
    AZURE_SEARCH_ENDPOINT="https://<search-service>.search.windows.net" `
    # ... all other Azure service credentials
```

---

## Verification Steps

### 1. Check Deployment Logs
```powershell
az webapp log tail --name app-hdipar-dev --resource-group RG_300000000120926_Hywel_Dda_AI
```

Look for:
- ✅ `Starting gunicorn 21.2.0`
- ✅ `Listening at: http://0.0.0.0:8000`
- ✅ `Booting worker with pid: <pid>`
- ❌ `ModuleNotFoundError` (indicates path issues)
- ❌ `Worker failed to boot` (indicates startup errors)

### 2. Test Health Endpoint
```powershell
Invoke-WebRequest -Uri "https://app-hdipar-dev.azurewebsites.net/health" -UseBasicParsing
```

Expected: `200 OK` with JSON response

### 3. Test Authentication
```powershell
# Should redirect to login
Invoke-WebRequest -Uri "https://app-hdipar-dev.azurewebsites.net/" -UseBasicParsing
```

### 4. Verify UI Loads
Open in browser: `https://app-hdipar-dev.azurewebsites.net/`
- Login page should appear
- After login, document list should load
- HTMX dynamic updates should work
- Tailwind CSS styling should render

---

## Environment Configuration

### Required Azure Services
All connection strings must be configured as App Service application settings:

1. **Azure Storage** (`AZURE_STORAGE_CONNSTR`)
   - Containers: `raw/`, `extracted/`, `thumbs/`, `manifests/`, `archive/`

2. **Azure AI Search** (`AZURE_SEARCH_ENDPOINT`, `AZURE_SEARCH_KEY`)
   - Index: `ipar-chunks` (auto-created on first upload)
   - Vector field: 3072 dimensions (text-embedding-3-large)

3. **Azure OpenAI** (`AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_KEY`)
   - Embedding model: `text-embedding-3-large`
   - Chat model: `gpt-4o` or `gpt-4`

4. **Azure Document Intelligence** (`AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT`, `AZURE_DOCUMENT_INTELLIGENCE_KEY`)
   - For PDF text extraction

5. **Azure Cosmos DB** (`AZURE_COSMOS_CONNSTR`)
   - Database: `ipar`
   - Collections: `documents`, `events`, `lineage`, `users`

6. **Application Insights** (`APPLICATIONINSIGHTS_CONNECTION_STRING`)
   - For telemetry and monitoring

### Authentication Settings
```
AUTH_USERNAME=admin
AUTH_PASSWORD=<secure-password>
```

---

## Production Recommendations

### 1. Security
- [ ] Use **Azure Key Vault** for secrets (not app settings)
- [ ] Enable **Managed Identity** for Azure service access
- [ ] Replace basic auth with **Azure AD B2C** or **Entra ID**
- [ ] Enable **HTTPS only** (already configured)
- [ ] Set up **IP restrictions** if needed

### 2. Performance
- [ ] Scale up to **P1V2** or higher tier for production
- [ ] Increase Gunicorn workers: `--workers=4` (for P-tier)
- [ ] Enable **Azure CDN** for static assets
- [ ] Configure **Application Insights** alerting

### 3. Reliability
- [ ] Set up **deployment slots** (staging → production)
- [ ] Enable **automatic healing** rules
- [ ] Configure **health check** endpoint monitoring
- [ ] Implement **circuit breakers** for Azure service calls

### 4. Monitoring
- [ ] Application Insights dashboards
- [ ] Log Analytics workspace queries
- [ ] Alert rules for:
  - 4xx/5xx error rates
  - Response time > 2s
  - Memory/CPU > 80%
  - Failed document uploads

---

## Quick Reference Commands

### Deploy
```powershell
.\deploy_simple.ps1
```

### View Logs
```powershell
az webapp log tail --name app-hdipar-dev --resource-group RG_300000000120926_Hywel_Dda_AI
```

### Restart App
```powershell
az webapp restart --name app-hdipar-dev --resource-group RG_300000000120926_Hywel_Dda_AI
```

### Update Environment Variable
```powershell
az webapp config appsettings set --name app-hdipar-dev --resource-group RG_300000000120926_Hywel_Dda_AI --settings KEY="value"
```

### SSH into Container (for debugging)
```powershell
az webapp ssh --name app-hdipar-dev --resource-group RG_300000000120926_Hywel_Dda_AI
```

---

## Deployment Timeline

Typical deployment takes **8-12 minutes**:
1. **ZIP upload**: 5-10 seconds
2. **Build phase**: 7-10 minutes (installing pandas, numpy, Azure SDKs, etc.)
3. **Container start**: 30-60 seconds
4. **Health check**: 10-20 seconds

**Note**: Azure CLI may timeout after 10 minutes, but deployment continues in background. Check logs to verify success.

---

## Success Criteria

✅ Deployment successful when:
1. `az webapp deployment source config-zip` completes (or times out with build in progress)
2. Logs show: `Starting gunicorn` and `Listening at: http://0.0.0.0:8000`
3. Health endpoint returns `200 OK`
4. UI loads at root URL with login page
5. Authentication works (can log in)
6. No errors in Application Insights

---

## For Future Deployments

### Always Use This Workflow:
1. **Test locally**: `python run.py` (should work without errors)
2. **Verify imports**: `python -c "from app import create_app; app = create_app()"`
3. **Run deployment script**: `.\deploy_simple.ps1`
4. **Monitor logs**: `az webapp log tail ...` (watch for errors)
5. **Test endpoints**: Health, login, upload, search, chat
6. **Check Application Insights**: Verify no exceptions

### Remember:
- **Windows → Linux**: Use Python's `zipfile`, not `Compress-Archive`
- **Line endings**: LF (Unix) for `startup.sh`, not CRLF (Windows)
- **ASCII only**: No special characters in bash scripts
- **Path handling**: `wsgi.py` must add current dir to `sys.path`
- **Patience**: Large dependency install takes 8-10 minutes

---

## Document Version
- **Created**: October 23, 2025
- **Last Updated**: October 23, 2025
- **Deployment**: app-hdipar-dev (successful)
- **Python**: 3.11.13
- **Flask**: 3.0.0
- **Gunicorn**: 21.2.0
