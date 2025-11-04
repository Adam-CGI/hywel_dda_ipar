# Quick Start - Azure App Service Deployment

## 🚀 Deploy in 3 Steps

### 1. Ensure Prerequisites
```powershell
# Check Azure CLI
az --version

# Login to Azure
az login
```

### 2. Run Deployment Script
```powershell
.\deploy_app_service.ps1
```

### 3. Enter Credentials When Prompted
- **Username**: Enter desired username (default: admin)
- **Password**: Enter secure password (min 8 characters)

## 🎉 Done!

Your app will be available at: **https://app-hdipar-dev.azurewebsites.net**

---

## 📋 What Gets Deployed

✅ Flask web application  
✅ Username/password authentication  
✅ All Azure service integrations  
✅ Document upload & search  
✅ RAG-powered chat interface  
✅ HTTPS-only security  

---

## 🔐 Authentication Details

- **Login URL**: https://app-hdipar-dev.azurewebsites.net/login
- **Logout URL**: https://app-hdipar-dev.azurewebsites.net/logout
- All routes are protected except `/health` and `/login`

---

## 🛠️ Useful Commands

### View Logs
```powershell
az webapp log tail --name app-hdipar-dev --resource-group RG_300000000120926_Hywel_Dda_AI
```

### Restart App
```powershell
az webapp restart --name app-hdipar-dev --resource-group RG_300000000120926_Hywel_Dda_AI
```

### Check Health
```powershell
curl https://app-hdipar-dev.azurewebsites.net/health
```

---

## 📖 Full Documentation

See [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) for complete deployment guide.

---

## ⚠️ Important Notes

1. **Credentials are secure**: Stored as environment variables, not in code
2. **HTTPS required**: App automatically enforces HTTPS
3. **Session-based auth**: Uses secure, HTTP-only cookies
4. **First deployment**: May take 5-10 minutes to fully start

---

## 🆘 Troubleshooting

**App won't start?**
- Check logs: `az webapp log tail`
- Verify all environment variables are set
- Ensure Python 3.11+ runtime

**Can't login?**
- Verify AUTH_USERNAME and AUTH_PASSWORD are set in App Settings
- Check browser allows cookies
- Ensure accessing via HTTPS

**Need help?**
- See full guide: [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
- Check Azure Portal: [App Service](https://portal.azure.com)
