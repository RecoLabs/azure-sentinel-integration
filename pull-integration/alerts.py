import json
import yaml
import base64
import requests
import logging
import os
from pathlib import Path
from datetime import datetime, timezone
from helper import get_logger, checkpoint_get, checkpoint_save, build_config_from_keyvault, validate_config

# Get the logger from helper.py (configured for file output)
logger = get_logger()

# Add console handler for stdout output
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

# Create formatter that matches the file logger format
console_formatter = logging.Formatter('%(asctime)s [%(levelname)s] [%(uuid)s] %(message)s')
console_handler.setFormatter(console_formatter)

# Add console handler to logger
logger.addHandler(console_handler)

CONFIG_PATH = Path(__file__).parent / "config.yaml"
RECO_API_TIMEOUT_IN_SECONDS = 30
RECO_ALERT_VIEW = "ALERT_VIEW_WITH_SHARED_STATUS"
CREATED_AT_FIELD = "updated_at"
DEMISTO_OCCURRED_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"
FILTER_RELATIONSHIP_AND = "AND"

def load_config():
    """
    Load configuration from either Key Vault (production) or local YAML file (development).
    """
    try:
        # Check if running in Azure Function (production mode)
        if os.getenv('AZURE_FUNCTIONS_ENVIRONMENT') or os.getenv('WEBSITE_SITE_NAME'):
            logger.info("Running in Azure environment, loading config from Key Vault...")
            config = build_config_from_keyvault()
        else:
            # Local development mode
            logger.info("Running in local environment, loading config from YAML file...")
            with open(CONFIG_PATH, 'r') as f:
                config = yaml.safe_load(f)
        
        # Validate configuration
        validate_config(config)
        logger.info("Configuration loaded and validated successfully.")
        return config
        
    except Exception as e:
        logger.exception(f"Failed to load config: {e}")
        raise

def create_alerts_payload(view_name, limit, after=None):
    filters = {"relationship": FILTER_RELATIONSHIP_AND, "filters": {"filters": []}}
    if after:
        filters["filters"]["filters"].append({
            "field": CREATED_AT_FIELD,
            "after": {"value": after.strftime(DEMISTO_OCCURRED_FORMAT)}
        })

    return {
        "getTableRequest": {
            "tableName": view_name,
            "pageSize": limit,
            "fieldFilters": filters,
            "fieldSorts": {
                "sorts": [{"sortBy": CREATED_AT_FIELD, "sortDirection": "SORT_DIRECTION_ASC"}]
            }
        }
    }

def parse_table_row_to_dict(cells):
    result = {}
    for cell in cells:
        key = cell.get("key")
        value = cell.get("value")
        if key and value:
            try:
                result[key] = base64.b64decode(value).decode("utf-8").replace('"', '')
            except Exception:
                result[key] = value
    return result

def fetch_alerts(config, after=None):
    url = f"https://{config['reco']['tenant_url']}/api/v1/policy-subsystem/alert-inbox/table"
    headers = {"Authorization": f"Bearer {config['reco']['api_key']}"}
    payload = create_alerts_payload(RECO_ALERT_VIEW, config['alerts']['fetch_limit'], after)

    logger.info(f"Fetching alert summaries from Reco after {after}...")
    resp = requests.put(url, json=payload, headers=headers, timeout=RECO_API_TIMEOUT_IN_SECONDS)
    if resp.status_code != 200:
        raise ValueError(f"Failed to retrieve data, status code: {resp.status_code}")

    rows = resp.json().get("getTableResponse", {}).get("data", {}).get("rows", [])
    alerts = [parse_table_row_to_dict(row.get("cells", [])) for row in rows]

    logger.info(f"Fetched {len(alerts)} alerts.")
    return alerts

def fetch_alert_details(config, alert_id):
    url = f"https://{config['reco']['tenant_url']}/api/v1/policy-subsystem/alert-inbox/{alert_id}"
    headers = {"Authorization": f"Bearer {config['reco']['api_key']}"}
    resp = requests.get(url, headers=headers, timeout=RECO_API_TIMEOUT_IN_SECONDS)

    if resp.status_code != 200:
        logger.error(f"Failed to fetch alert {alert_id}: {resp.status_code}")
        return None

    alert = resp.json().get("alert", {})
    alert.pop("aggregationRulesToKeys", None)

    for v in alert.get("policyViolations", []):
        try:
            decoded = json.loads(base64.b64decode(v.get("jsonData", "")))
            decoded.pop("violation", None)
            v["jsonData"] = decoded
        except Exception:
            pass

    return alert

def fetch_agent_summary(config, alert_id):
    """Fetch agent summary for a specific alert"""
    url = f"https://{config['reco']['tenant_url']}/api/v1/alert/summarize/{alert_id}"
    headers = {"Authorization": f"Bearer {config['reco']['api_key']}"}
    
    try:
        resp = requests.get(url, headers=headers, timeout=RECO_API_TIMEOUT_IN_SECONDS)
        if resp.status_code != 200:
            logger.warning(f"Failed to fetch agent summary for alert {alert_id}: {resp.status_code}")
            return None
        
        summary_data = resp.json()
        return summary_data.get("markdown", "")
    except Exception as e:
        logger.warning(f"Error fetching agent summary for alert {alert_id}: {e}")
        return None

def send_to_azure_sentinel(alerts, config):
    """
    Send alerts directly to Azure Log Analytics workspace using the Data Collector API.
    
    Args:
        alerts (list): List of enriched alert dictionaries
        config (dict): Configuration containing workspace credentials and settings
    """
    if not alerts:
        logger.info("No alerts to send to Azure Sentinel.")
        return {"sent": 0, "failed": 0}
    
    import hashlib
    import hmac
    import base64
    from datetime import datetime, timezone
    
    # Configuration
    workspace_id = config["alerts"]["workspace_id"]
    workspace_key = config["alerts"]["workspace_key"]
    log_type = config["alerts"]["log_type"]
    
    max_retries = config.get("processing", {}).get("max_retries", 3)
    retry_delay = config.get("processing", {}).get("retry_delay", 5)
    timeout = config.get("processing", {}).get("http_timeout", 30)
    
    # Azure Log Analytics Data Collector API endpoint
    uri = f"https://{workspace_id}.ods.opinsights.azure.com/api/logs?api-version=2016-04-01"
    
    logger.info(f"Sending {len(alerts)} enriched alerts to Azure Log Analytics workspace: {workspace_id}")
    
    def build_signature(workspace_id, workspace_key, date, content_length, method, content_type, resource):
        """Build the authorization signature for Azure Log Analytics Data Collector API."""
        x_headers = f"x-ms-date:{date}"
        string_to_hash = f"{method}\n{content_length}\n{content_type}\n{x_headers}\n{resource}"
        bytes_to_hash = bytes(string_to_hash, 'UTF-8')
        decoded_key = base64.b64decode(workspace_key)
        encoded_hash = base64.b64encode(hmac.new(decoded_key, bytes_to_hash, digestmod=hashlib.sha256).digest()).decode()
        authorization = f"SharedKey {workspace_id}:{encoded_hash}"
        return authorization
    
    def send_batch_to_workspace(batch, batch_idx):
        """Send a batch of alerts to Log Analytics workspace."""
        # Prepare the data
        body = json.dumps(batch)
        content_length = len(body)
        
        # Generate RFC 1123 timestamp
        rfc1123date = datetime.now(timezone.utc).strftime('%a, %d %b %Y %H:%M:%S GMT')
        
        # Build authorization signature
        signature = build_signature(
            workspace_id, 
            workspace_key, 
            rfc1123date, 
            content_length, 
            'POST', 
            'application/json', 
            '/api/logs'
        )
        
        # Headers for the request
        headers = {
            'content-type': 'application/json',
            'Authorization': signature,
            'Log-Type': log_type,
            'x-ms-date': rfc1123date,
            'time-generated-field': 'timestamp'
        }
        
        # Send the request
        for attempt in range(max_retries):
            try:
                logger.debug(f"Sending batch {batch_idx} to Log Analytics, attempt {attempt + 1}")
                
                response = requests.post(
                    uri,
                    data=body,
                    headers=headers,
                    timeout=timeout
                )
                
                if response.status_code in (200, 202):
                    logger.info(f"Successfully sent batch {batch_idx} ({len(batch)} alerts) to workspace")
                    return True
                else:
                    logger.warning(f"Batch {batch_idx} attempt {attempt + 1} failed: HTTP {response.status_code}")
                    logger.debug(f"Response: {response.text}")
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Batch {batch_idx} attempt {attempt + 1} timed out after {timeout}s")
            except requests.exceptions.ConnectionError as e:
                logger.warning(f"Batch {batch_idx} attempt {attempt + 1} connection error: {e}")
            except Exception as e:
                logger.warning(f"Batch {batch_idx} attempt {attempt + 1} unexpected error: {e}")
            
            # Wait before retry (except on last attempt)
            if attempt < max_retries - 1:
                logger.info(f"Retrying batch {batch_idx} in {retry_delay} seconds...")
                import time
                time.sleep(retry_delay)
        
        return False
    
    # Process alerts in batches (Log Analytics API has size limits)
    batch_size = 100  # Smaller batches for Log Analytics API
    total_sent = 0
    total_failed = 0
    
    for batch_idx, i in enumerate(range(0, len(alerts), batch_size), 1):
        batch = alerts[i:i+batch_size]
        
        # Add timestamp and metadata to each alert
        processed_batch = []
        for alert in batch:
            processed_alert = dict(alert)  # Copy the alert
            
            # Ensure timestamp is present for Log Analytics
            if 'timestamp' not in processed_alert:
                processed_alert['timestamp'] = datetime.now(timezone.utc).isoformat()
            
            # Add processing metadata
            processed_alert['_ingestion_metadata'] = {
                'processor_source': 'reco-alert-processor',
                'processor_version': '1.0',
                'batch_id': f"batch_{batch_idx}",
                'ingested_at': datetime.now(timezone.utc).isoformat(),
                'workspace_id': workspace_id
            }
            
            processed_batch.append(processed_alert)
        
        logger.info(f"Processing batch {batch_idx}: {len(batch)} alerts (items {i+1}-{i+len(batch)})")
        
        if send_batch_to_workspace(processed_batch, batch_idx):
            total_sent += len(batch)
        else:
            total_failed += len(batch)
            logger.error(f"Failed to send batch {batch_idx} after {max_retries} attempts")
    
    # Log final summary
    logger.info(f"Alert transmission summary: {total_sent} sent, {total_failed} failed")
    
    if total_failed > 0:
        failure_rate = (total_failed / len(alerts)) * 100
        logger.warning(f"Alert transmission failure rate: {failure_rate:.1f}%")
        
        # If failure rate is high, don't update checkpoint
        if failure_rate > 50:
            logger.error("High failure rate detected. Checkpoint will not be updated to allow retry on next run.")
            raise Exception(f"High alert transmission failure rate: {failure_rate:.1f}%")
    
    return {"sent": total_sent, "failed": total_failed}

def main():
    """
    Main function to orchestrate alert processing workflow.
    """
    start_time = datetime.now(timezone.utc)
    logger.info("=" * 60)
    logger.info("Starting Reco Alert Processor")
    logger.info(f"Start time: {start_time.isoformat()}")
    logger.info("=" * 60)
    
    try:
        # Load configuration
        logger.info("Loading configuration...")
        config = load_config()
        logger.info("Configuration loaded successfully.")

        # Get last checkpoint
        after_str = checkpoint_get("last_alert_run_time")
        logger.info(f"Last alert run time: {after_str}")
        after = datetime.strptime(after_str, DEMISTO_OCCURRED_FORMAT) if after_str else None

        # Fetch raw alerts from Reco
        logger.info(f"Fetching alerts after {after}...")
        raw_alerts = fetch_alerts(config, after)
        
        if not raw_alerts:
            logger.info("No new alerts found. Processing complete.")
            return {"status": "success", "message": "No new alerts", "processed": 0}

        # Enrich alerts with detailed information
        logger.info(f"Enriching {len(raw_alerts)} alerts with detailed information...")
        enriched_alerts = []
        failed_enrichments = 0
        
        fetch_summaries = config.get("processing", {}).get("fetch_agent_summary", True)
        
        for idx, alert in enumerate(raw_alerts, 1):
            try:
                # Decode alert ID
                alert_id = alert.get("id")
                if not alert_id:
                    logger.warning(f"Alert {idx} missing ID, skipping...")
                    failed_enrichments += 1
                    continue
                    
                decoded_id = base64.b64decode(alert_id).decode("utf-8")
                logger.debug(f"Processing alert {idx}/{len(raw_alerts)}: {decoded_id}")
                
                # Fetch detailed alert information
                full_alert = fetch_alert_details(config, decoded_id)
                if not full_alert:
                    logger.warning(f"Failed to fetch details for alert {decoded_id}")
                    failed_enrichments += 1
                    continue
                
                # Add metadata
                full_alert["_metadata"] = {
                    "processed_at": datetime.now(timezone.utc).isoformat(),
                    "source": "reco-alert-processor",
                    "processor_version": "1.0"
                }
                
                # Optionally fetch agent summary
                if fetch_summaries:
                    try:
                        agent_summary = fetch_agent_summary(config, decoded_id)
                        if agent_summary:
                            full_alert["agent_summary"] = agent_summary
                            logger.debug(f"Added agent summary to alert {decoded_id}")
                    except Exception as e:
                        logger.warning(f"Failed to fetch agent summary for alert {decoded_id}: {e}")
                
                enriched_alerts.append(full_alert)
                
            except Exception as e:
                failed_enrichments += 1
                logger.warning(f"Failed to process alert {idx}: {e}")

        # Log enrichment results
        logger.info(f"Alert enrichment complete: {len(enriched_alerts)} successful, {failed_enrichments} failed")
        
        if not enriched_alerts:
            logger.warning("No alerts were successfully enriched. Processing complete.")
            return {"status": "warning", "message": "No alerts enriched", "processed": 0}

        # Send alerts to Azure Sentinel
        logger.info("Sending enriched alerts to Azure Sentinel...")
        transmission_result = send_to_azure_sentinel(enriched_alerts, config)
        
        # Update checkpoint only if transmission was successful
        if transmission_result["failed"] == 0 or transmission_result["failed"] < len(enriched_alerts) * 0.5:
            now = datetime.now(timezone.utc).strftime(DEMISTO_OCCURRED_FORMAT)
            if checkpoint_save("last_alert_run_time", now):
                logger.info(f"Successfully updated checkpoint (last run time): {now}")
            else:
                logger.warning("Failed to update checkpoint in Key Vault")
        else:
            logger.warning("Checkpoint not updated due to high transmission failure rate")

        # Calculate processing summary
        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()
        
        logger.info("=" * 60)
        logger.info("Alert processing completed successfully")
        logger.info(f"Duration: {duration:.2f} seconds")
        logger.info(f"Raw alerts fetched: {len(raw_alerts)}")
        logger.info(f"Alerts enriched: {len(enriched_alerts)}")
        logger.info(f"Alerts sent: {transmission_result['sent']}")
        logger.info(f"Alerts failed: {transmission_result['failed']}")
        logger.info("=" * 60)
        
        return {
            "status": "success",
            "processed": len(enriched_alerts),
            "sent": transmission_result["sent"],
            "failed": transmission_result["failed"],
            "duration_seconds": duration
        }

    except Exception as e:
        end_time = datetime.now(timezone.utc)
        duration = (end_time - start_time).total_seconds()
        
        logger.exception("Unhandled error during alert script execution")
        logger.error(f"Processing failed after {duration:.2f} seconds")
        
        return {
            "status": "error",
            "error": str(e),
            "duration_seconds": duration
        }

if __name__ == "__main__":
    print("Starting alert script...")
    main()
