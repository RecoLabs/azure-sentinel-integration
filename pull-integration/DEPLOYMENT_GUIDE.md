# Azure Function Deployment Guide

## 🚀 Recommended: Using func CLI (Azure Functions Core Tools)

### Why func CLI is Better

✅ **Automatic dependency management** - Handles Python packages correctly  
✅ **Remote build** - Builds on Azure for better compatibility  
✅ **Faster deployments** - Optimized for Azure Functions  
✅ **Better error handling** - Clear deployment feedback  
✅ **No manual packaging** - Handles file exclusions automatically  

### Deployment Options

#### Option 1: Full Deployment (Infrastructure + Code)
```bash
# Deploy everything using deploy.sh (func CLI required)
./deploy.sh -g my-resource-group
```

#### Option 2: Direct func CLI Commands (Code Only)
```bash
# Basic deployment
func azure functionapp publish my-function-app

# With remote build (recommended for Python)
func azure functionapp publish my-function-app --build remote --no-bundler

# Include local settings
func azure functionapp publish my-function-app --publish-local-settings --build remote
```

## 📋 Deployment Comparison

| Method | Speed | Dependencies | Error Handling | Ease of Use |
|--------|-------|--------------|----------------|-------------|
| **func CLI** | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |

**Note**: Only func CLI is supported. ZIP deployment method has been removed for better reliability.

## 🔧 Prerequisites

### Install Azure Functions Core Tools
```bash
# macOS (via Homebrew)
brew tap azure/functions
brew install azure-functions-core-tools@4

# Windows (via npm)
npm install -g azure-functions-core-tools@4 --unsafe-perm true

# Linux (via apt)
curl https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor > microsoft.gpg
sudo mv microsoft.gpg /etc/apt/trusted.gpg.d/microsoft.gpg
sudo sh -c 'echo "deb [arch=amd64] https://packages.microsoft.com/repos/microsoft-ubuntu-$(lsb_release -cs)-prod $(lsb_release -cs) main" > /etc/apt/sources.list.d/dotnetdev.list'
sudo apt-get update
sudo apt-get install azure-functions-core-tools-4
```

### Verify Installation
```bash
func --version  # Should show 4.x.x
az --version    # Azure CLI
```

## 🎯 Common Deployment Scenarios

### Scenario 1: First Time Deployment
```bash
# Deploy infrastructure and code
./deploy.sh -g my-resource-group
```

### Scenario 2: Code Updates Only (Fastest)
```bash
# Fast deployment of code changes only
func azure functionapp publish my-function-app --build remote
```

### Scenario 3: Configuration Changes
```bash
# Deploy with updated local settings
func azure functionapp publish my-function-app --publish-local-settings --build remote
```

### Scenario 4: Different Environments
```bash
# Deploy to development environment
func azure functionapp publish my-function-app-dev --build remote

# Deploy to production environment  
func azure functionapp publish my-function-app-prod --build remote
```

## 🐛 Troubleshooting

### Issue: "Function not found" after deployment
**Solution**: Ensure `function_app.py` is in the root directory (not `__init__.py`)

### Issue: "Module import errors"
**Solution**: Use `--build remote` flag for proper dependency resolution

### Issue: "Timer trigger not working"
**Solution**: Check AzureWebJobsStorage connection string in Function App settings

### Issue: "Deployment timeout"
**Solution**: 
```bash
# Increase timeout and use smaller deployment
func azure functionapp publish my-function-app --build remote --timeout 300
```

## 📊 Monitoring Deployments

### Check Deployment Status
```bash
# View function app status
az functionapp show --resource-group <rg> --name <app> --query "state"

# List deployed functions
az functionapp function list --resource-group <rg> --name <app>

# Stream logs
az functionapp logs tail --resource-group <rg> --name <app>
```

### Test Timer Trigger
```bash
# Check for timer logs in Application Insights
# Timer should execute every 15 minutes automatically
# Look for logs containing "Timer trigger" or "RecoAlertProcessor"
```

## 🔄 Best Practices

1. **Always use remote build** for Python functions: `--build remote`
2. **Test locally first** with `func start` before deploying
3. **Use code-only deployments** for frequent updates
4. **Version your deployments** with git tags
5. **Monitor after deployment** to ensure timer is working
6. **Keep local.settings.json** updated but never commit secrets

## 🚨 Important Notes

- **Timer triggers require storage**: Ensure AzureWebJobsStorage is configured
- **Python dependencies**: Let Azure handle with `--build remote`
- **Local testing**: Use `func start` to test before deployment
- **Storage connectivity**: This was the root cause of your timer issues!

## 🆘 Emergency Fixes

### Quick redeploy (if function stopped working):
```bash
func azure functionapp publish my-function-app --build remote --force
```

### Reset function app:
```bash
az functionapp restart --resource-group <rg> --name <app>
```

### Check storage connection:
```bash
az functionapp config appsettings list --resource-group <rg> --name <app> --query "[?name=='AzureWebJobsStorage']"
```
