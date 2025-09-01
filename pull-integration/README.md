# Reco Alert Processor - Azure Function

A production-ready Azure Function that periodically fetches alerts from Reco and sends them to Azure Sentinel for security monitoring and analysis.

## 🏗️ Architecture Overview

```
┌─────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Reco API  │    │  Azure Function │    │ Azure Sentinel  │
│             │◄──►│   (Timer)       │───►│ / Log Analytics │
│             │    │                 │    │                 │
└─────────────┘    └─────────────────┘    └─────────────────┘
                           │                         
                           ▼                         
                   ┌─────────────────┐    ┌─────────────────┐
                   │   Key Vault     │    │ Application     │
                   │ (Secrets/Config)│    │   Insights      │
                   └─────────────────┘    └─────────────────┘
```

## 🚀 Features

- **Scheduled Processing**: Timer-triggered function runs every X minutes (configurable)
- **Secure Configuration**: All sensitive data stored in Azure Key Vault
- **Resilient Design**: Retry logic, error handling, and checkpoint management
- **Direct Log Analytics Integration**: Sends data directly to Azure Log Analytics workspace using Data Collector API
- **Comprehensive Monitoring**: Application Insights integration for telemetry
- **Agent Summaries**: Fetches AI-generated alert summaries from Reco
- **Infrastructure as Code**: Complete ARM templates for deployment

## 📋 Prerequisites

Before deploying, ensure you have:

1. **Azure Subscription** with appropriate permissions
2. **Azure CLI** installed and configured
3. **Log Analytics Workspace** (for Azure Sentinel)
4. **Reco API Credentials** (tenant URL and API key)

## 🏗️ Infrastructure Components

The solution deploys the following Azure resources:

- **Function App** (Consumption plan Y1 - timer-triggered)
- **Storage Account** (for Function App runtime)
- **Key Vault** (for sensitive configuration and checkpoints)
- **Application Insights** (for monitoring and telemetry)
- **Hosting Plan** (Linux consumption plan for Python 3.11)
- **RBAC Assignments** (Key Vault Secrets Officer role for Function App managed identity)

## 🔧 Configuration

### Required Secrets in Key Vault

| Secret Name | Description | Example |
|-------------|-------------|---------|
| `reco-tenant-url` | Your Reco tenant URL | `customer.reco.ai` |
| `reco-api-key` | Reco API authentication key | `your-api-key-here` |
| `reco-fetch-limit` | Max alerts per API call | `100` |
| `azure-workspace-id` | Log Analytics workspace ID | `12345678-1234-...` |
| `azure-workspace-key` | Log Analytics workspace key | `workspace-key-here` |
| `azure-log-type` | Custom log table name | `RecoAlert` |
| `checkpoint-last-alert-run-time` | Last processing timestamp | *Auto-generated* |

> **Note**: Checkpoint secrets are automatically created and managed by the application. Secret names use hyphens for Azure Key Vault compliance.

### Timer Schedule Configuration

The function uses CRON expressions for scheduling:

- `0 */15 * * * *` - Every 15 minutes
- `0 */5 * * * *` - Every 5 minutes  
- `0 0 */1 * * *` - Every hour
- `0 0 9,17 * * *` - 9 AM and 5 PM daily

## 🚀 Quick Start

### 1. Configure Parameters

Edit the parameters file with your specific values:

```bash
# Edit the parameters file
vim infrastructure/azuredeploy.parameters.json
```

Update the following values:
- `logAnalyticsWorkspaceId`: Your Log Analytics workspace ID
- `logAnalyticsWorkspaceKey`: Your Log Analytics workspace key
- `recoTenantUrl`: Your Reco tenant URL (e.g., customer.reco.ai)
- `recoApiKey`: Your Reco API key
- Other optional settings like timer schedule, fetch limit, etc.

### 2. Create Resource Group

```bash
# Create a resource group (if it doesn't exist)
az group create --name "my-resource-group" --location "East US"
```

### 3. Deploy Infrastructure

```bash
# Make the script executable
chmod +x deploy.sh

# Deploy everything
./deploy.sh -g my-resource-group
```

That's it! The deployment script will:
- Deploy Function App, Key Vault, Storage, and Application Insights
- Automatically configure all secrets in Key Vault
- Deploy the function code
- Set up all necessary permissions

### 4. Test the Function

```bash
# Trigger the function manually
az functionapp function invoke \
  --resource-group "my-resource-group" \
  --name "your-function-app" \
  --function-name "RecoAlertProcessor"
```

## 📊 Monitoring and Troubleshooting

### Application Insights Queries

```kusto
// Function execution logs
traces
| where cloud_RoleName contains "reco"
| order by timestamp desc

// Function performance
requests
| where cloud_RoleName contains "reco"
| summarize avg(duration), count() by bin(timestamp, 5m)

// Function errors
exceptions
| where cloud_RoleName contains "reco"
| order by timestamp desc
```

### Log Analytics Queries

```kusto
// View ingested alerts
RecoAlert_CL
| where TimeGenerated > ago(1h)
| order by TimeGenerated desc

// Alert summary by severity
RecoAlert_CL
| where TimeGenerated > ago(24h)
| extend Severity = tostring(parse_json(requestData_s).severity)
| summarize count() by Severity

// Monitor processing metrics
RecoAlert_CL
| where TimeGenerated > ago(6h)
| extend BatchId = tostring(parse_json(requestData_s).batch_id)
| summarize AlertCount = count() by BatchId, bin(TimeGenerated, 15m)
```

### Common Issues

**Function Not Triggering:**
- Check timer schedule syntax
- Verify Function App is running
- Review Function App logs

**Key Vault Access Errors:**
- Verify managed identity has "Key Vault Secrets Officer" role for read/write access
- Check Key Vault RBAC configuration (not access policies)
- Ensure secrets exist with correct names (no underscores in names)
- Wait 5-10 minutes for role assignment propagation after deployment

**Reco API Errors:**
- Validate API key and tenant URL
- Check network connectivity
- Review rate limiting

**Azure Sentinel Integration Issues:**
- Verify Log Analytics workspace credentials
- Check Data Collector API connectivity
- Validate workspace ID and key configuration
- Review custom log table creation permissions

## 🔐 Security Best Practices

### Key Vault Security
- Enable soft delete and purge protection (7 days retention configured)
- Use Azure RBAC authorization (enableRbacAuthorization: true)
- Function App assigned "Key Vault Secrets Officer" role for read/write access
- Secret names use hyphens instead of underscores for compliance
- Monitor access with diagnostic settings
- Implement secret rotation for API keys and workspace keys

### Function App Security
- Use managed identity for authentication
- Enable HTTPS only
- Implement proper CORS settings
- Monitor for suspicious activity

### Network Security
- Consider VNet integration for premium plans
- Use private endpoints for Key Vault
- Implement IP restrictions if needed

## 📁 Project Structure

```
alert-pull/
├── alerts.py                     # Main alert processing logic
├── helper.py                     # Utility functions (logging, Key Vault, checkpoints)
├── function_app.py               # Azure Function entry point with timer trigger
├── config.yaml                   # Local development configuration template
├── host.json                     # Function host configuration
├── requirements.txt              # Python dependencies
├── local.settings.json           # Local development settings
├── deploy.sh                     # Deployment script
├── DEPLOYMENT_GUIDE.md          # Detailed deployment instructions
├── infrastructure/
│   ├── azuredeploy.json          # Complete ARM template with RBAC and Key Vault
│   └── azuredeploy.parameters.json # ARM template parameters
├── logs/                         # Local log files directory
└── README.md                     # This file
```

## 🔄 Data Flow

1. **Timer Trigger**: Function executes on schedule (configurable CRON expression)
2. **Configuration**: Load secrets from Key Vault using managed identity
3. **Checkpoint**: Retrieve last run timestamp from Key Vault (`checkpoint-last-alert-run-time`)
4. **Fetch Alerts**: Call Reco API for new alerts after checkpoint timestamp
5. **Enrich Data**: Fetch detailed alert information and AI-generated summaries
6. **Send to Sentinel**: POST directly to Azure Log Analytics Data Collector API in batches
7. **Update Checkpoint**: Save new timestamp to Key Vault (only on successful transmission)
8. **Logging**: Write telemetry to Application Insights and local log files

## 📈 Performance Considerations

### Function App Sizing

**Consumption Plan (Y1) - Only Option:**
- Cost-effective: Pay only for execution time
- Automatic scaling: Scales based on demand
- Suitable for: Periodic alert processing (every 15 minutes default)
- Limitations: Cold starts, 5-minute timeout, 1.5GB memory
- Perfect for: This use case where function runs periodically

### Optimization Tips

- Batch alert processing for efficiency
- Use async/await for I/O operations
- Implement exponential backoff for retries
- Monitor memory usage and execution time

## 🎛️ Customization

### Modify Timer Schedule

Update the `timerSchedule` parameter in ARM template or environment variable.

### Add Custom Fields

Modify the `_metadata` section in `alerts.py`:

```python
full_alert["_metadata"] = {
    "processed_at": datetime.now(timezone.utc).isoformat(),
    "source": "reco-alert-processor",
    "processor_version": "1.0",
    "custom_field": "your_value"
}
```

### Change Batch Size

Modify `batch_size` in `send_to_azure_sentinel()` function (default: 100 alerts per batch).

## 🔄 Maintenance

### Regular Tasks

1. **Monitor Performance**: Check execution times and success rates
2. **Review Logs**: Look for errors or warnings in Application Insights
3. **Update Dependencies**: Keep Python packages up to date
4. **Rotate Secrets**: Periodically update API keys and workspace keys
5. **Scale Review**: Assess if current hosting plan meets needs

### Disaster Recovery

- Key Vault: Enabled soft delete and backup
- Function App: Source code in version control
- Configuration: ARM templates for infrastructure
- Data: Checkpoints stored in Key Vault for resume capability

## 📞 Support

For issues or questions:

1. Check Application Insights logs for function execution details
2. Review Function App logs in Azure Portal
3. Validate Key Vault secret configuration and RBAC permissions
4. Test individual components (Reco API connectivity, Log Analytics Data Collector API)
5. Verify checkpoint management in Key Vault