# Azure Logic App - Sentinel Data Ingestion Proxy

A robust, enterprise-ready Azure Logic App that acts as an HTTPS proxy for ingesting data into Azure Sentinel/Log Analytics, using Logic App's built-in SAS authentication and **Azure's native Log Analytics Data Collector connector**.

## 🚀 Features

- **SAS Token Authentication** - Secure access using Logic App's built-in authentication
- **Native Azure Integration** - Uses built-in Log Analytics Data Collector connector 
- **No Manual Authentication** - Azure handles HMAC-SHA256 signing automatically
- **Custom Log Tables** - Configurable log table names with automatic `_CL` suffix
- **Request Enrichment** - Automatically adds metadata (source IP, user agent, timestamps)
- **Comprehensive Error Handling** - Detailed error responses and logging
- **ARM Template Deployment** - Infrastructure as Code with parameterization
- **Environment Support** - Separate configurations for dev/staging/production
- **Connection Management** - Managed connections for secure credential storage

## 📋 Prerequisites

- Azure subscription with appropriate permissions
- **Azure Log Analytics workspace** (existing)
- Azure CLI or PowerShell for deployment
- Log Analytics workspace ID and primary/secondary key

## 🏗️ Architecture

```
[Client] --HTTPS POST--> [Logic App (SAS Auth)] --Connector--> [Log Analytics] --> [Azure Sentinel]
                                    ↓
                            [Connection Management]
                                    ↓
                            [Automatic Authentication]
```

## 📁 Project Structure

```
logic-app-sentinel-integration/
├── azuredeploy.json                # ARM template for deployment
├── azuredeploy.parameters.json     # Default parameters
├── deploy.sh                       # Bash deployment script
└── README.md                       # This file
```

## ⚙️ Key Parameters

| Parameter | Type | Description | Default |
|-----------|------|-------------|---------|
| `logicAppName` | string | Name of the Logic App | `logic-app-sentinel-{uniqueString}` |
| `workspaceId` | string | Log Analytics workspace ID | *(required)* |
| `workspaceKey` | securestring | Log Analytics workspace key | *(required)* |
| `logType` | string | Custom log table name | `CustomLogData` |
| `timeoutInSeconds` | int | API call timeout | `30` |
| `location` | string | Azure region | `resourceGroup().location` |

## 🔐 Authentication & Security

### SAS Token Authentication

The Logic App uses Azure's built-in **Shared Access Signature (SAS)** authentication:

- **Automatic**: No custom token implementation required
- **Secure**: Generated and managed by Azure
- **URL-based**: Authentication parameters included in trigger URL
- **Time-limited**: Configurable expiration

**Sample authenticated URL structure:**
```
https://{region}.logic.azure.com/workflows/{id}/triggers/manual/paths/invoke?api-version=2019-05-01&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig={signature}
```

### Connection Security

- **Managed Connections**: Azure handles Log Analytics authentication
- **Credential Isolation**: Workspace keys stored securely in connection
- **No HMAC Implementation**: Azure connector handles signing automatically

## 🚀 Quick Start

### 1. Log Analytics Workspace Setup

Ensure you have your Log Analytics workspace details:
```bash
# Get workspace ID (from Azure Portal or CLI)
az monitor log-analytics workspace show \
  --resource-group "your-rg" \
  --workspace-name "your-workspace" \
  --query "customerId" -o tsv

# Get workspace key (primary or secondary)
az monitor log-analytics workspace get-shared-keys \
  --resource-group "your-rg" \
  --workspace-name "your-workspace" \
  --query "primarySharedKey" -o tsv
```

### 2. Update Parameters

Edit your parameter file (e.g., `azuredeploy.parameters.json`):
```json
{
  "workspaceId": {
    "value": "63126b46-3e13-414b-b89a-c866b3079a39"
  },
  "workspaceKey": {
    "value": "your-workspace-key-here"
  },
  "logType": {
    "value": "MyCustomLogs"
  }
}
```

### 3. Deploy

**Using Bash:**
```bash
./deploy.sh -g RESOURCEGROUP
```

## 📤 Usage

### Basic Request

```bash
curl -X POST 'YOUR_TRIGGER_URL_WITH_SAS' \
  -H 'Content-Type: application/json' \
  -d '{
    "eventType": "security_alert",
    "severity": "High", 
    "message": "Suspicious login detected",
    "source": "firewall",
    "timestamp": "2024-01-15T10:30:00Z"
  }'
```

### Response (Success)

```json
{
  "status": "success",
  "message": "Data successfully sent to Azure Sentinel / Log Analytics", 
  "requestId": "08585329112324420665",
  "timestamp": "2024-01-15T10:30:15.123Z",
  "logType": "RecoAlert_CL"
}
```

## 📊 Monitoring and Data Verification

### Query Your Data

**KQL Query Examples:**
```kql
// View recent ingested data
RecoAlert_CL
| where TimeGenerated > ago(1h)
| order by TimeGenerated desc

// Count events by severity  
RecoAlert_CL
| where TimeGenerated > ago(24h)
| summarize count() by severity_s
| render piechart


### Key Metrics to Monitor

- **Ingestion Rate**: `RecoAlert_CL | summarize count() by bin(TimeGenerated, 1h)`
- **Error Analysis**: Monitor Logic App run history in Azure Portal
- **Connection Health**: Check connection status in Logic App connections
- **Data Latency**: Typical ingestion time is 2-5 minutes

## 🎛️ Customization

### Adding Custom Fields

Modify the `Prepare_Log_Analytics_Data` action to include additional fields:
```json
{
  "timestamp": "@utcnow()",
  "requestId": "@variables('RequestId')",
  "customField1": "value1",
  "customField2": "@variables('SomeVariable')",
  "requestData": "@json(variables('RequestBody'))"
}
```

### Connection Configuration

The Logic App creates a managed connection that:
- Stores workspace credentials securely
- Handles authentication automatically  
- Can be reused across multiple Logic Apps
- Supports connection monitoring and health checks

## 🔧 Troubleshooting

### Common Issues

**Connection Authentication Failures:**
- Verify workspace ID and key are correct
- Check workspace permissions
- Ensure connection is properly configured

**Data Not Appearing in Log Analytics:**
- Wait 2-5 minutes for ingestion
- Check Logic App run history for errors
- Verify log table name and KQL queries
- Validate JSON data format

**Logic App Trigger Issues:**
- Confirm SAS URL is complete and valid
- Check trigger configuration
- Verify HTTP method is POST
- Review request headers and content-type

## 🏭 Production Deployment

### Security Checklist

- ✅ Use SAS authentication (built-in)
- ✅ Store workspace keys in managed connections
- ✅ Enable diagnostic logging
- ✅ Configure appropriate RBAC permissions
- ✅ Monitor connection health
- ✅ Set up alerting for failures
- ✅ Regular connection key rotation

### Best Practices

1. **Performance**: Monitor ingestion rates and Logic App execution times
2. **Connection Management**: Monitor connection status and refresh keys as needed
3. **Error Handling**: Set up alerts for Logic App failures
4. **Data Governance**: Define log retention and access policies


### Testing

```bash
# Test basic ingestion
curl -X POST 'YOUR_TRIGGER_URL' \
  -H 'Content-Type: application/json' \
  -d '{"test": "data", "severity": "Info"}'

# Test with custom payload
curl -X POST 'YOUR_TRIGGER_URL' \
  -H 'Content-Type: application/json' \
  -d '{"eventType": "test", "message": "Test message", "source": "manual"}'
```

### Verification

1. **Immediate**: Check Logic App run history
2. **Short-term**: Query Log Analytics after 2-5 minutes
3. **Long-term**: Verify data appears in Azure Sentinel

## 📚 Additional Resources

- [Azure Logic Apps Documentation](https://docs.microsoft.com/azure/logic-apps/)
- [Log Analytics Data Collector API](https://docs.microsoft.com/azure/azure-monitor/logs/data-collector-api)
- [Azure Sentinel Documentation](https://docs.microsoft.com/azure/sentinel/) 
- [KQL Quick Reference](https://docs.microsoft.com/azure/data-explorer/kql-quick-reference)
- [Logic App Connectors](https://docs.microsoft.com/connectors/azureloganalyticsdatacollector/)

---

**Note**: The trigger URL contains SAS authentication parameters. Keep this URL secure and do not expose it in public repositories or logs. 
