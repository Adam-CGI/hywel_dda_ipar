 Azure App Service Deployment Guide
## Hywel Dda IPAR Document Miner

This guide walks you through deploying your Flask application to Azure App Service with username/password authentication.

## Prerequisites

- Azure CLI installed (`az --version`)
- Logged into Azure (`az login`)
- Your existing App Service Plan: `asp-hdipar-dev`
- Resource Group: `RG_300000000120926_Hywel_Dda_AI`
## Hywel Dda IPAR Document Miner (RAG)
## Architecture

### Authentication
## Architecture (Current)


### Editing the About Page / Branding
An end-user accessible **About** page now exists at `/about` describing the system purpose, boundaries, and roadmap.

To change the content (no code changes required):
1. Edit `flask_app/content/about.md` (Markdown).
2. Refresh the browser – content reloads per request.
3. Keep headings (`## What It Is`, `## What It Isn’t`, `## Future Development`) for consistency.

Branding can be overridden via environment variables:
```
BRAND_NAME="Hywel Dda University Health Board"
BRAND_TAGLINE="IPAR Document Miner (RAG Pilot)"
```
If unset, defaults are applied. These values appear in the navigation bar and page titles.

Tailwind gradient in the navigation uses NHS blues (#005EB8 → #0072CE → #003087). Adjust in `flask_app/templates/base.html` if needed.
```
app.py                 # Main Flask app with auth initialization
```
app.py                  # Root shim exposing Flask `app`
startup.txt             # Gunicorn start command
flask_app/app.py        # Main factory + routes registration
flask_app/config.py     # Env/config + Azure client factories
flask_app/routes/       # Flask blueprint(s)
flask_app/services/     # Azure integration services
flask_app/templates/    # HTMX/Tailwind templates
```
  routes/
    documents.py       # Protected document routes
  services/            # Azure service integrations
startup.sh             # Azure App Service startup script
```

## Deployment Steps

### Step 1: Review Configuration Files

The following files have been created for deployment:

1. **`app/auth.py`** - Authentication middleware
   - Session-based authentication
   - Login/logout routes
   - Secure password checking with timing attack protection

2. **`startup.sh`** - App Service startup script
   - Configures Python environment
   - Installs dependencies
   - Starts Gunicorn web server

3. **`deploy_app_service.ps1`** - Automated deployment script
   - Creates Web App if needed
   - Configures app settings
   - Deploys application code

4. **`.deployment`** - Azure deployment configuration
   - Enables build during deployment

### Step 2: Prepare Environment Variables

Create a local `.env` file (if you don't have one) with your Azure service credentials:

```env
# Authentication (will be set during deployment)
AUTH_USERNAME=admin
AUTH_PASSWORD=your-secure-password
SECRET_KEY=your-random-secret-key

# Flask Configuration
FLASK_ENV=production

# Azure Services (copy from your existing .env)
AZURE_STORAGE_CONNECTION_STRING=...
AZURE_SEARCH_ENDPOINT=...
AZURE_SEARCH_KEY=...
AZURE_OPENAI_ENDPOINT=...
AZURE_OPENAI_KEY=...
AZURE_OPENAI_API_VERSION=2024-02-15-preview
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=...
AZURE_DOCUMENT_INTELLIGENCE_KEY=...
COSMOS_ENDPOINT=...
COSMOS_KEY=...
COSMOS_DATABASE_NAME=ipar
```

### Step 3: Run the Deployment Script

Execute the PowerShell deployment script:

```powershell
# Run from the project root directory
.\deploy_app_service.ps1
```

The script will:
1. Check if Azure CLI is installed and you're logged in
2. Create the Web App (if it doesn't exist)
3. Prompt you for authentication credentials:
   - Username (default: admin)
   - Password (minimum 8 characters)
4. Configure all app settings from your `.env` file
5. Deploy your application code
6. Test the deployment

**Expected output:**
```
========================================
Hywel Dda IPAR - Azure Deployment
========================================

Deployment Configuration:
  Resource Group: RG_300000000120926_Hywel_Dda_AI
  App Service Plan: asp-hdipar-dev
  Web App Name: app-hdipar-dev
  Location: uksouth
  Runtime: PYTHON:3.11

Enter authentication credentials for the application:
Username (default: admin): admin
Password (min 8 characters): ********

Deployment Complete!
Application URL: https://app-hdipar-dev.azurewebsites.net
```

### Step 4: Verify Deployment

1. **Visit the application URL**: https://app-hdipar-dev.azurewebsites.net
2. You should be redirected to `/login`
3. Enter your username and password
4. After successful login, you'll access the chat interface

## Manual Deployment (Alternative)

If you prefer manual deployment:

### Create Web App
```powershell
az webapp create `
  --resource-group RG_300000000120926_Hywel_Dda_AI `
  --plan asp-hdipar-dev `
  --name app-hdipar-dev `
  --runtime "PYTHON:3.11"
```

### Configure App Settings
```powershell
# Set authentication credentials
az webapp config appsettings set `
  --resource-group RG_300000000120926_Hywel_Dda_AI `
  --name app-hdipar-dev `
  --settings `
    AUTH_USERNAME="admin" `
    AUTH_PASSWORD="your-secure-password" `
    SECRET_KEY="$(New-Guid)" `
    FLASK_ENV="production" `
    AZURE_STORAGE_CONNECTION_STRING="..." `
    AZURE_SEARCH_ENDPOINT="..." `
    # ... add all other Azure service settings
```

### Set Startup Command
```powershell
az webapp config set `
  --resource-group RG_300000000120926_Hywel_Dda_AI `
  --name app-hdipar-dev `
  --startup-file "startup.sh"
```

### Deploy Code
```powershell
az webapp up `
  --resource-group RG_300000000120926_Hywel_Dda_AI `
  --name app-hdipar-dev `
  --runtime "PYTHON:3.11"
```

## Security Considerations

### 1. Strong Passwords
- Use passwords with at least 12 characters
- Include uppercase, lowercase, numbers, and symbols
- Never commit passwords to source control

### 2. Secret Key
- Generate a random secret key (at least 32 characters)
- Change it periodically
- Never reuse across environments

### 3. HTTPS Only
The deployment script automatically enables HTTPS-only mode:
```powershell
az webapp update --set httpsOnly=true
```

### 4. Environment Variables
All sensitive configuration is stored as App Service application settings (environment variables), not in code.

### 5. Session Security
- Sessions are HTTP-only (prevents XSS attacks)
- Secure cookies in production (HTTPS required)
- SameSite=Lax (CSRF protection)

## Monitoring & Troubleshooting

### View Application Logs
```powershell
# Stream live logs
az webapp log tail --name app-hdipar-dev --resource-group RG_300000000120926_Hywel_Dda_AI

# Download logs
az webapp log download --name app-hdipar-dev --resource-group RG_300000000120926_Hywel_Dda_AI
```

### Restart Application
```powershell
az webapp restart --name app-hdipar-dev --resource-group RG_300000000120926_Hywel_Dda_AI
```

### Check Health Endpoint
```powershell
curl https://app-hdipar-dev.azurewebsites.net/health
```

Expected response:
```json
{
  "status": "healthy",
  "service": "hdipar-document-miner",
  "environment": "production"
}
```

### View in Azure Portal
https://portal.azure.com/#@/resource/subscriptions/8fb6bbf9-f461-4ebb-9a0f-7636a6c8ad2b/resourceGroups/RG_300000000120926_Hywel_Dda_AI/providers/Microsoft.Web/sites/app-hdipar-dev

## Post-Deployment

### Test Authentication
1. Navigate to application URL
2. Try accessing protected routes (should redirect to login)
3. Login with credentials
4. Verify access to all features:
   - Document upload
   - Document list
   - Search
   - Chat interface
5. Test logout functionality

### Test Application Features
```bash
# Health check (no auth required)
curl https://app-hdipar-dev.azurewebsites.net/health

# Login and get session cookie
curl -X POST https://app-hdipar-dev.azurewebsites.net/login \
  -d "username=admin&password=your-password" \
  -c cookies.txt

# Access protected endpoint with session
curl https://app-hdipar-dev.azurewebsites.net/api/documents/ \
  -b cookies.txt
```

## Updating the Application

### Update Code
```powershell
# Make your code changes, then redeploy
az webapp up --name app-hdipar-dev --resource-group RG_300000000120926_Hywel_Dda_AI
```

### Update App Settings
```powershell
az webapp config appsettings set `
  --name app-hdipar-dev `
  --resource-group RG_300000000120926_Hywel_Dda_AI `
  --settings KEY=value
```

### Update Python Version
```powershell
az webapp config set `
  --name app-hdipar-dev `
  --resource-group RG_300000000120926_Hywel_Dda_AI `
  --linux-fx-version "PYTHON:3.11"
```

## Cost Management

Your current plan:
- **SKU**: B1 (Basic)
- **Tier**: Basic
- **Cost**: ~£40/month
- **Features**: 
  - 1.75 GB RAM
  - 100 GB storage
  - Custom domains
  - Manual scale up to 3 instances

## Advanced Configuration

### Custom Domain
```powershell
az webapp config hostname add `
  --webapp-name app-hdipar-dev `
  --resource-group RG_300000000120926_Hywel_Dda_AI `
  --hostname your-domain.com
```

### Scale Up/Out
```powershell
# Scale up to higher tier
az appservice plan update `
  --name asp-hdipar-dev `
  --resource-group RG_300000000120926_Hywel_Dda_AI `
  --sku S1

# Scale out (add instances)
az appservice plan update `
  --name asp-hdipar-dev `
  --resource-group RG_300000000120926_Hywel_Dda_AI `
  --number-of-workers 3
```

### Enable Managed Identity
```powershell
az webapp identity assign `
  --name app-hdipar-dev `
  --resource-group RG_300000000120926_Hywel_Dda_AI
```

## Troubleshooting Common Issues

### Application Won't Start
1. Check startup logs: `az webapp log tail`
2. Verify `startup.sh` has executable permissions
3. Check Python version matches runtime
4. Verify all dependencies in `requirements.txt`

### Authentication Not Working
1. Verify `AUTH_USERNAME` and `AUTH_PASSWORD` are set
2. Check `SECRET_KEY` is configured
3. Ensure cookies are enabled in browser
4. Verify HTTPS is enabled (required for secure cookies)

### Slow Performance
1. Check Gunicorn worker configuration
2. Review Application Insights metrics
3. Consider scaling up or out
4. Enable caching for static assets

### Connection to Azure Services Failed
1. Verify connection strings in app settings
2. Check Azure service firewall rules
3. Verify managed identity permissions
4. Test connectivity from App Service console

## Support

For issues with:
- **Azure CLI**: https://docs.microsoft.com/cli/azure/
- **App Service**: https://docs.microsoft.com/azure/app-service/
- **Flask**: https://flask.palletsprojects.com/
- **Gunicorn**: https://docs.gunicorn.org/

## Next Steps

1. ✅ Deploy application
2. ✅ Configure authentication
3. ⬜ Set up custom domain (optional)
4. ⬜ Configure Application Insights monitoring
5. ⬜ Set up automated backups
6. ⬜ Configure auto-scaling rules
7. ⬜ Implement Azure Key Vault for secrets
8. ⬜ Set up staging slot for zero-downtime deployments
