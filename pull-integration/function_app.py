"""
Azure Function entry point for Reco Alert Processor.

This function is triggered by a timer to periodically fetch alerts from Reco
and send them to Azure Sentinel directly via Azure Log Analytics API.

Uses Azure Functions Python v2 programming model with decorators.
"""

import datetime
import logging
import os
import azure.functions as func
from alerts import main as process_alerts

# Create the function app instance
app = func.FunctionApp()

@app.function_name(name="RecoAlertProcessor")
@app.timer_trigger(
    schedule=os.getenv("TIMER_SCHEDULE", "0 */5 * * * *"),  # Default: every 15 minutes
    arg_name="mytimer",
    run_on_startup=False,
    use_monitor=True
)
def reco_alert_processor(mytimer: func.TimerRequest) -> None:
    """
    Azure Function timer trigger for processing Reco alerts.
    
    This function:
    1. Fetches alerts from Reco API based on the last checkpoint
    2. Enriches alerts with additional metadata
    3. Sends alerts directly to Azure Log Analytics workspace
    4. Updates the checkpoint for the next run
    
    Args:
        mytimer: Timer trigger request object with schedule information
    """
    utc_timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    # Configure logging for this function
    function_logger = logging.getLogger("RecoAlertProcessor")
    function_logger.setLevel(logging.INFO)
    
    # Check if timer is past due (running late)
    if mytimer.past_due:
        function_logger.warning('Timer trigger is past due - function is running late!')
    
    # Log timer information for debugging
    function_logger.info(f"Reco Alert Processor started at {utc_timestamp}")
    function_logger.info(f"Timer schedule: {os.getenv('TIMER_SCHEDULE', '0 */5 * * * *')}")
    function_logger.info(f"Timer past due: {mytimer.past_due}")
    function_logger.info(f"Timer schedule status: {mytimer.schedule_status if hasattr(mytimer, 'schedule_status') else 'N/A'}")
    
    # Log environment variables for debugging
    function_logger.info(f"Azure Functions Environment: {os.getenv('AZURE_FUNCTIONS_ENVIRONMENT', 'Not Set')}")
    function_logger.info(f"Website Site Name: {os.getenv('WEBSITE_SITE_NAME', 'Not Set')}")
    
    try:
        # Execute the main alert processing logic
        result = process_alerts()
        
        # Log the processing results
        if result.get("status") == "success":
            function_logger.info(
                f"Alert processing completed successfully! "
                f"Stats: Processed={result.get('processed', 0)}, "
                f"Sent={result.get('sent', 0)}, "
                f"Failed={result.get('failed', 0)}, "
                f"Duration={result.get('duration_seconds', 0):.2f}s"
            )
        elif result.get("status") == "warning":
            function_logger.warning(
                f"Alert processing completed with warnings: {result.get('message', 'Unknown warning')}"
            )
        else:
            function_logger.error(
                f"Alert processing failed: {result.get('error', 'Unknown error')}"
            )
            # Don't raise exception for processing failures - let timer continue running
            
    except Exception as e:
        function_logger.exception(f"Unhandled exception in Azure Function: {e}")
        # Re-raise to mark the function execution as failed
        raise
    
    function_logger.info(f"Reco Alert Processor completed at {utc_timestamp}")
