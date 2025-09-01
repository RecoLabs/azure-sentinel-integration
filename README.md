# Azure Sentinel Integration Solutions

A comprehensive collection of production-ready integration patterns for ingesting security data into Azure Sentinel. This repository provides both **Pull** and **Push** integration approaches, each optimized for different use cases and requirements.

## 🎯 Overview

This project demonstrates two distinct integration patterns for Azure Sentinel data ingestion:

1. **Pull Integration** - Timer-driven Azure Functions that proactively fetch data from external APIs
2. **Push Integration** - Event-driven Logic Apps that receive data via HTTP webhooks

Choose the pattern that best fits your data freshness requirements, processing complexity, and cost considerations.

## 🏗️ Repository Structure

```
azure-sentinel-integration/
├── pull-integration/          # Timer-driven Azure Function solution
│   ├── alerts.py             # Main alert processing logic
│   ├── function_app.py       # Azure Function entry point
│   ├── helper.py             # Utility functions and Key Vault integration
│   ├── infrastructure/       # ARM templates and deployment
│   └── deploy.sh            # Automated deployment script
├── push-webhook-integration/ # Event-driven Logic App solution
│   ├── azuredeploy.json     # ARM template for Logic App
│   ├── azuredeploy.parameters.json # Configuration parameters
│   └── deploy.sh           # Automated deployment script
└── README.md               # This file
```

## 🔄 Integration Pattern Comparison

### Pull Integration (Timer-Driven)
**Best for**: Batch processing, complex transformations, guaranteed data retrieval

- ✅ **Scheduled Processing**: CRON-based execution (every 15 minutes default)
- ✅ **State Management**: Checkpoint tracking for resume capability
- ✅ **Robust Error Handling**: Built-in retry logic and recovery mechanisms
- ✅ **Data Enrichment**: Complex processing and AI-generated summaries
- ✅ **Predictable Costs**: Fixed execution schedule with known resource usage

### Push Integration (Webhook-Driven)
**Best for**: Real-time ingestion, simple transformations, event-driven scenarios

- ✅ **Real-time Processing**: Near-instantaneous data ingestion (< 30 seconds)
- ✅ **Event-Driven**: React immediately to external system events
- ✅ **Cost Efficient**: Pay only for actual events processed
- ✅ **Simple Setup**: Minimal configuration and native Azure connectors
- ✅ **Auto-scaling**: Handles traffic spikes automatically

---

## 📊 Detailed Technical Comparison

| Aspect | Pull Integration | Push Integration |
|--------|------------------|------------------|
| **Technology Stack** | Azure Functions (Python 3.11) | Logic Apps (JSON workflow) |
| **Trigger Mechanism** | Timer/Schedule (CRON expressions) | HTTP Webhook/Event |
| **Data Flow Direction** | Azure → External System | External System → Azure |
| **Data Freshness** | 5-15 minutes (polling interval) | < 30 seconds (real-time) |
| **State Management** | Checkpoint tracking in Key Vault | Stateless processing |
| **Authentication** | Managed Identity + Key Vault RBAC | SAS tokens + Managed Connections |
| **Error Handling** | Built-in retry & recovery logic | Depends on sender + Logic App retries |
| **Processing Complexity** | High (custom Python logic) | Medium (JSON transformations) |
| **Cost Model** | Predictable (~$5-20/month) | Variable (~$0.0001/execution) |
| **Scaling** | Function App constraints | Auto-scaling Logic Apps |
| **Monitoring** | Application Insights + custom logs | Logic App run history + diagnostics |

---

## 🏗️ Architecture Comparison

### Pull Integration Architecture
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

### Push Integration Architecture
```
┌─────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   External  │    │   Logic App     │    │ Azure Sentinel  │
│   System    │───►│ (HTTP Trigger)  │───►│ / Log Analytics │
│             │    │                 │    │                 │
└─────────────┘    └─────────────────┘    └─────────────────┘
                           │                         
                           ▼                         
                   ┌─────────────────┐
                   │   Managed       │
                   │   Connections   │
                   └─────────────────┘
```

---

## ⚡ When to Use Each Pattern

### Use Pull Integration When:
- ✅ **Batch Processing**: Need to process large volumes of historical data
- ✅ **State Management**: Require checkpoint/resume capabilities
- ✅ **Data Transformation**: Complex processing and enrichment needed
- ✅ **Rate Limiting**: External API has strict rate limits
- ✅ **Reliability**: Need guaranteed data retrieval with retry logic
- ✅ **Scheduled Operations**: Business requires specific processing windows

**Example Use Cases:**
- Daily security report ingestion
- Bulk historical data migration
- Systems without webhook capabilities
- Compliance reporting on schedule

### Use Push Integration When:
- ✅ **Real-time Requirements**: Immediate data ingestion needed
- ✅ **Event-Driven**: React to specific triggers or alerts
- ✅ **Low Latency**: Minimize time between event and ingestion
- ✅ **Simple Transformation**: Minimal data processing required
- ✅ **Cost Efficiency**: Pay only for actual events
- ✅ **External Control**: Let external systems control timing

**Example Use Cases:**
- Real-time security alerts
- IoT sensor data streams
- User activity events
- Critical incident notifications

---

## 🔧 Implementation Details

### Pull Integration (Azure Functions)

**Key Components:**
- **Timer Trigger**: CRON-based scheduling (`0 */15 * * * *`)
- **State Management**: Checkpoint tracking in Key Vault
- **Error Handling**: Comprehensive retry logic and error recovery
- **Batch Processing**: Configurable batch sizes for efficiency
- **Authentication**: Managed Identity with Key Vault integration

**Configuration Example:**
```python
# Timer schedule: Every 15 minutes
@app.timer_trigger(schedule="0 */15 * * * *", arg_name="myTimer")
def reco_alert_processor(myTimer: func.TimerRequest) -> None:
    # Fetch new alerts since last checkpoint
    # Process and enrich data
    # Send to Azure Sentinel
    # Update checkpoint
```

### Push Integration (Logic Apps)

**Key Components:**
- **HTTP Trigger**: SAS token authentication
- **Native Connectors**: Built-in Log Analytics Data Collector
- **Automatic Authentication**: Azure handles HMAC-SHA256 signing
- **Request Enrichment**: Metadata addition (IP, timestamp, etc.)
- **Connection Management**: Secure credential storage

**Configuration Example:**
```json
{
  "trigger": {
    "kind": "Http",
    "type": "Request"
  },
  "actions": {
    "Send_Data": {
      "type": "ApiConnection",
      "inputs": {
        "host": {
          "connection": {
            "name": "@parameters('$connections')['azureloganalyticsdatacollector']['connectionId']"
          }
        }
      }
    }
  }
}
```

---

## 💰 Cost Comparison

### Pull Integration Costs
- **Predictable**: Fixed execution schedule
- **Components**: Function App (Consumption), Storage, Key Vault, App Insights
- **Scaling**: Based on execution time and memory usage
- **Estimate**: ~$5-20/month for typical workloads

### Push Integration Costs
- **Variable**: Based on incoming event volume
- **Components**: Logic App (Consumption), Managed Connections
- **Scaling**: Per-execution pricing
- **Estimate**: ~$0.0001 per execution + connector costs

---

## 📈 Performance Characteristics

### Pull Integration Performance
- **Latency**: 5-15 minutes (polling interval dependent)
- **Throughput**: High (batch processing)
- **Scalability**: Limited by Function App constraints
- **Reliability**: High (built-in retry mechanisms)

### Push Integration Performance
- **Latency**: < 30 seconds (near real-time)
- **Throughput**: Medium (per-event processing)
- **Scalability**: High (auto-scaling Logic Apps)
- **Reliability**: Dependent on sender implementation

---

## 🔐 Security Considerations

### Pull Integration Security
- **Authentication**: Managed Identity + Key Vault RBAC
- **Secrets Management**: Azure Key Vault with rotation
- **Network**: VNet integration possible
- **Audit**: Application Insights telemetry

### Push Integration Security
- **Authentication**: SAS tokens (built-in Logic Apps)
- **Endpoint Security**: HTTPS-only with Azure authentication
- **Connection Security**: Managed connections for credentials
- **Audit**: Logic App run history and diagnostics

---

## 🚀 Getting Started

### Quick Start - Pull Integration
```bash
cd pull-integration
./deploy.sh -g my-resource-group
```

### Quick Start - Push Integration  
```bash
cd push-webhook-integration
./deploy.sh -g my-resource-group
```

---

## 🔍 Monitoring and Troubleshooting

### Pull Integration Monitoring
```kusto
// Function execution logs
traces
| where cloud_RoleName contains "reco"
| order by timestamp desc

// Processing metrics
RecoAlert_CL
| where TimeGenerated > ago(6h)
| summarize AlertCount = count() by bin(TimeGenerated, 15m)
```

### Push Integration Monitoring
```kusto
// Recent ingested data
RecoAlert_CL
| where TimeGenerated > ago(1h)
| order by TimeGenerated desc

// Event volume analysis
RecoAlert_CL
| where TimeGenerated > ago(24h)
| summarize count() by bin(TimeGenerated, 1h)
```

---

## 🎯 Decision Matrix

Choose your integration pattern based on these key factors:

| Factor | Pull | Push | Weight |
|--------|------|------|--------|
| **Data Freshness Required** | 🟡 Delayed | 🟢 Real-time | High |
| **Processing Complexity** | 🟢 High capability | 🟡 Limited | Medium |
| **Cost Predictability** | 🟢 Predictable | 🟡 Variable | Medium |
| **Implementation Complexity** | 🟡 Higher | 🟢 Lower | Low |
| **External System Control** | 🟡 Azure controls | 🟢 External controls | Medium |
| **Reliability Requirements** | 🟢 Built-in retry | 🟡 Depends on sender | High |

**Legend**: 🟢 Better fit | 🟡 Adequate | 🔴 Poor fit

---

## 📚 Next Steps

1. **Evaluate Requirements**: Determine your specific needs for latency, volume, and complexity
2. **Choose Pattern**: Select pull or push based on the decision matrix above
3. **Deploy Solution**: Use the provided ARM templates and deployment scripts
4. **Monitor Performance**: Set up appropriate monitoring and alerting
5. **Iterate**: Optimize based on actual usage patterns and requirements

For detailed implementation guides, refer to:
- [Pull Integration README](./pull-integration/README.md)
- [Push Integration README](./push-webhook-integration/README.md)
