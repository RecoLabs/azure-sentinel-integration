#!/bin/bash

# Azure Logic App Sentinel Data Ingestion Deployment Script
# This script deploys the Logic App for sending data to Azure Sentinel using Azure CLI
# Authentication is handled by the Logic App's built-in SAS token in the trigger URL

set -e
# Default values
RESOURCE_GROUP=""
LOCATION="East US"
# ENVIRONMENT="dev"
SUBSCRIPTION_ID=""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${BLUE}INFO:${NC} $1"
}

print_success() {
    echo -e "${GREEN}SUCCESS:${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}WARNING:${NC} $1"
}

print_error() {
    echo -e "${RED}ERROR:${NC} $1"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 -g <resource-group> [-l <location>] [-s <subscription-id>]"
    echo ""
    echo "Options:"
    echo "  -g, --resource-group    Azure resource group name (required)"
    echo "  -l, --location          Azure region (default: East US)"
    # echo "  -e, --environment       Environment (dev/prod) (default: dev)"
    echo "  -s, --subscription      Azure subscription ID (optional)"
    echo "  -h, --help              Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 -g my-resource-group"
    echo "  $0 -g my-resource-group -l \"West US 2\" -e prod"
    echo "  $0 -g my-resource-group -s \"12345678-1234-1234-1234-123456789012\""
    echo ""
    echo "Prerequisites:"
    echo "  - Azure CLI installed and logged in"
    echo "  - Log Analytics workspace ID and key configured in parameter files"
    echo "  - Azure Sentinel enabled on the target workspace (optional but recommended)"
    echo ""
    echo "Security:"
    echo "  - Authentication is handled by Logic App's built-in SAS authentication"
    echo "  - The trigger URL contains secure SAS tokens for access control"
    echo "  - No additional authentication tokens are required"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -g|--resource-group)
            RESOURCE_GROUP="$2"
            shift 2
            ;;
        -l|--location)
            LOCATION="$2"
            shift 2
            ;;
        # -e|--environment)
        #     ENVIRONMENT="$2"
        #     shift 2
        #     ;;
        -s|--subscription)
            SUBSCRIPTION_ID="$2"
            shift 2
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Validate required parameters
if [ -z "$RESOURCE_GROUP" ]; then
    print_error "Resource group is required"
    show_usage
    exit 1
fi

# # Validate environment
# if [[ "$ENVIRONMENT" != "dev" && "$ENVIRONMENT" != "prod" ]]; then
#     print_error "Environment must be 'dev' or 'prod'"
#     exit 1
# fi

# Set subscription if provided
if [ -n "$SUBSCRIPTION_ID" ]; then
    print_info "Setting Azure subscription to: $SUBSCRIPTION_ID"
    az account set --subscription "$SUBSCRIPTION_ID"
fi

# Check if Azure CLI is installed and user is logged in
if ! command -v az &> /dev/null; then
    print_error "Azure CLI is not installed. Please install it first."
    exit 1
fi

if ! az account show &> /dev/null; then
    print_error "You are not logged in to Azure. Please run 'az login' first."
    exit 1
fi

# Get current subscription info
CURRENT_SUBSCRIPTION=$(az account show --query "name" -o tsv)
CURRENT_SUBSCRIPTION_ID=$(az account show --query "id" -o tsv)
print_info "Using subscription: $CURRENT_SUBSCRIPTION ($CURRENT_SUBSCRIPTION_ID)"

# Check if resource group exists, create if it doesn't
print_info "Checking if resource group '$RESOURCE_GROUP' exists..."
if ! az group show --name "$RESOURCE_GROUP" &> /dev/null; then
    print_warning "Resource group '$RESOURCE_GROUP' does not exist. Creating it..."
    az group create --name "$RESOURCE_GROUP" --location "$LOCATION"
    print_success "Resource group '$RESOURCE_GROUP' created successfully"
else
    print_info "Resource group '$RESOURCE_GROUP' already exists"
fi

# Set parameter file based on environment
PARAM_FILE="azuredeploy.parameters.json"

if [ ! -f "$PARAM_FILE" ]; then
    print_error "Parameter file '$PARAM_FILE' not found"
    exit 1
fi

print_info "Using parameter file: $PARAM_FILE"

# Validate that workspace parameters are configured
print_info "Validating Log Analytics workspace configuration..."
WORKSPACE_ID=$(grep -o '"YOUR_.*_WORKSPACE_ID_HERE"' "$PARAM_FILE" || true)
WORKSPACE_KEY=$(grep -o '"YOUR_.*_WORKSPACE_KEY_HERE"' "$PARAM_FILE" || true)

if [ -n "$WORKSPACE_ID" ] || [ -n "$WORKSPACE_KEY" ]; then
    print_warning "Please update the Log Analytics workspace ID and key in $PARAM_FILE before deployment"
    print_info "You can find these values in Azure Portal > Log Analytics workspace > Settings > Agents"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Deployment cancelled. Please update the parameter file and try again."
        exit 0
    fi
fi

# Deploy the ARM template
print_info "Starting deployment of Logic App for Azure Sentinel data ingestion..."
DEPLOYMENT_NAME="reco-logic-app-sentinel"

az deployment group create \
    --resource-group "$RESOURCE_GROUP" \
    --template-file "azuredeploy.json" \
    --parameters "@$PARAM_FILE" \
    --name "$DEPLOYMENT_NAME" \
    --verbose

az deployment group wait --resource-group "$RESOURCE_GROUP" --name "$DEPLOYMENT_NAME" --created

if [ $? -eq 0 ]; then
    print_success "Deployment completed successfully!"
    
    # Get deployment outputs using multiple query fields in a single call
    print_info "Retrieving deployment outputs..."
    
    # Use a single query with multiple output fields to avoid multiple API calls
    OUTPUTS=$(az deployment group show \
        --resource-group "$RESOURCE_GROUP" \
        --name "$DEPLOYMENT_NAME" \
        --query "{logicAppName:properties.outputs.logicAppName.value,triggerUrl:properties.outputs.triggerEndpointUrl.value,logTable:properties.outputs.targetLogTable.value,workspaceId:properties.outputs.workspaceId.value}" \
        -o tsv 2>/dev/null || echo "N/A	N/A	N/A	N/A")
    
    # Parse the tab-separated output
    IFS=$'\t' read -r LOGIC_APP_NAME TRIGGER_URL LOG_TABLE WORKSPACE_ID_OUTPUT <<< "$OUTPUTS"
    
    # Validate that we got the outputs successfully
    if [[ "$LOGIC_APP_NAME" == "N/A" ]] || [[ -z "$LOGIC_APP_NAME" ]]; then
        print_warning "Could not retrieve some deployment outputs. The deployment may still be successful."
        print_info "You can manually check the outputs in Azure Portal or run:"
        echo "az deployment group show --resource-group \"$RESOURCE_GROUP\" --name \"$DEPLOYMENT_NAME\" --query \"properties.outputs\""
    fi
    
    echo ""
    print_success "=== DEPLOYMENT SUMMARY ==="
    echo "Logic App Name: $LOGIC_APP_NAME"
    echo "Resource Group: $RESOURCE_GROUP"
    # echo "Environment: $ENVIRONMENT"
    echo "Trigger URL: $TRIGGER_URL"
    echo "Target Log Table: $LOG_TABLE"
    echo "Workspace ID: $WORKSPACE_ID_OUTPUT"
    echo ""
    print_info "You can test the Logic App by sending a POST request to the trigger URL."
    print_info "Note: The trigger URL contains SAS authentication - no additional headers needed!"
    print_info "Example:"
    echo "curl -X POST '$TRIGGER_URL' \\"
    echo "  -H 'Content-Type: application/json' \\"
    echo "  -d '{\"message\": \"Hello Azure Sentinel\", \"severity\": \"Info\"}'"
    echo ""
    print_info "Data will appear in Log Analytics / Azure Sentinel under the table: $LOG_TABLE"
    print_info "You can query it in Azure Portal with KQL: $LOG_TABLE | take 10"
else
    print_error "Deployment failed!"
    exit 1
fi 
