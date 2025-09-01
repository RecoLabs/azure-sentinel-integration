import logging
import uuid
import os
import json
from datetime import datetime
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential


def get_logger(name="alert-processor", log_level=logging.INFO):
    """
    Create a logger with consistent formatting and UUID for tracking.
    
    Args:
        name (str): Logger name
        log_level: Logging level (default: INFO)
    
    Returns:
        logging.Logger: Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Only configure if not already configured
    if not logger.handlers:
        logger.setLevel(log_level)
        
        # Generate unique UUID for this session
        session_uuid = str(uuid.uuid4())[:8]
        
        # Create formatter with UUID
        formatter = logging.Formatter(
            f'%(asctime)s [%(levelname)s] [{session_uuid}] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # File handler for persistent logging
        try:
            log_dir = "/tmp/logs" if os.path.exists("/tmp") else "logs"
            os.makedirs(log_dir, exist_ok=True)
            
            file_handler = logging.FileHandler(
                f"{log_dir}/alert-processor.log", 
                mode='a', 
                encoding='utf-8'
            )
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            print(f"Warning: Could not create file handler: {e}")
        
        # Console handler for immediate feedback
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # Store UUID as logger attribute for access in other modules
        logger.uuid = session_uuid
    
    return logger


def get_keyvault_client(vault_url=None):
    """
    Create Azure Key Vault client using managed identity or service principal.
    
    Args:
        vault_url (str): Key Vault URL (if None, gets from environment)
    
    Returns:
        SecretClient: Azure Key Vault secret client
    """
    if not vault_url:
        vault_url = os.getenv('AZURE_KEYVAULT_URL')
        if not vault_url:
            raise ValueError("AZURE_KEYVAULT_URL environment variable is required")
    
    # Use DefaultAzureCredential which handles:
    # - Managed Identity (when running in Azure)
    # - Service Principal (when AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID are set)
    # - Azure CLI (when running locally)
    credential = DefaultAzureCredential()
    
    return SecretClient(vault_url=vault_url, credential=credential)


def checkpoint_get(checkpoint_key, default_value=None):
    """
    Retrieve checkpoint value from Azure Key Vault.
    
    Args:
        checkpoint_key (str): Key name for the checkpoint
        default_value: Default value if checkpoint doesn't exist
    
    Returns:
        str: Checkpoint value or default_value
    """
    try:
        vault_client = get_keyvault_client()
        # Replace underscores with hyphens for Azure Key Vault naming compliance
        secret_name = f"checkpoint-{checkpoint_key.replace('_', '-')}"
        
        try:
            secret = vault_client.get_secret(secret_name)
            return secret.value
        except Exception as e:
            logger = get_logger()
            logger.info(f"Checkpoint '{checkpoint_key}' not found in Key Vault: {e}")
            return default_value
            
    except Exception as e:
        logger = get_logger()
        logger.error(f"Failed to retrieve checkpoint '{checkpoint_key}' from Key Vault: {e}")
        return default_value


def checkpoint_save(checkpoint_key, value):
    """
    Save checkpoint value to Azure Key Vault.
    
    Args:
        checkpoint_key (str): Key name for the checkpoint
        value (str): Value to save
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        vault_client = get_keyvault_client()
        # Replace underscores with hyphens for Azure Key Vault naming compliance
        secret_name = f"checkpoint-{checkpoint_key.replace('_', '-')}"
        
        # Convert value to string if it isn't already
        value_str = str(value)
        
        # Set the secret in Key Vault
        vault_client.set_secret(secret_name, value_str)
        
        logger = get_logger()
        logger.info(f"Successfully saved checkpoint '{checkpoint_key}' to Key Vault")
        return True
        
    except Exception as e:
        logger = get_logger()
        logger.error(f"Failed to save checkpoint '{checkpoint_key}' to Key Vault: {e}")
        return False


def get_secret(secret_name):
    """
    Retrieve a secret from Azure Key Vault.
    
    Args:
        secret_name (str): Name of the secret to retrieve
    
    Returns:
        str: Secret value
    
    Raises:
        Exception: If secret cannot be retrieved
    """
    try:
        vault_client = get_keyvault_client()
        secret = vault_client.get_secret(secret_name)
        return secret.value
    except Exception as e:
        logger = get_logger()
        logger.error(f"Failed to retrieve secret '{secret_name}' from Key Vault: {e}")
        raise


def build_config_from_keyvault():
    """
    Build configuration dictionary by retrieving secrets from Key Vault.
    This replaces the need for a config.yaml file when running in Azure.
    
    Returns:
        dict: Configuration dictionary
    """
    logger = get_logger()
    logger.info("Building configuration from Azure Key Vault...")
    
    try:
        config = {
            'reco': {
                'tenant_url': get_secret('reco-tenant-url'),
                'api_key': get_secret('reco-api-key')
            },
            'alerts': {
                'fetch_limit': int(get_secret('reco-fetch-limit')),
                'workspace_id': get_secret('azure-workspace-id'),
                'workspace_key': get_secret('azure-workspace-key'),
                'log_type': get_secret('azure-log-type')
            },
            'azure': {
                'keyvault_url': os.getenv('AZURE_KEYVAULT_URL'),
                'function_name': os.getenv('AZURE_FUNCTIONS_ENVIRONMENT', 'local')
            }
        }
        
        logger.info("Configuration successfully built from Key Vault")
        return config
        
    except Exception as e:
        logger.error(f"Failed to build configuration from Key Vault: {e}")
        raise


def validate_config(config):
    """
    Validate configuration dictionary to ensure all required fields are present.
    
    Args:
        config (dict): Configuration dictionary
    
    Returns:
        bool: True if valid, raises exception if invalid
    """
    required_fields = {
        'reco.tenant_url': ['reco', 'tenant_url'],
        'reco.api_key': ['reco', 'api_key'],
        'alerts.fetch_limit': ['alerts', 'fetch_limit'],
        'alerts.workspace_id': ['alerts', 'workspace_id'],
        'alerts.workspace_key': ['alerts', 'workspace_key'],
        'alerts.log_type': ['alerts', 'log_type']
    }
    
    missing_fields = []
    
    for field_name, field_path in required_fields.items():
        try:
            current = config
            for key in field_path:
                current = current[key]
            
            if not current:
                missing_fields.append(field_name)
                
        except (KeyError, TypeError):
            missing_fields.append(field_name)
    
    if missing_fields:
        raise ValueError(f"Missing required configuration fields: {', '.join(missing_fields)}")
    
    return True
