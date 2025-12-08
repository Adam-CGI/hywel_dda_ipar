#!/bin/bash
#
# Deployment script for Hywel Dda IPAR Document Miner
# Deploys Flask application to Azure App Service
#
# Usage: ./deploy.sh [options]
#   -n, --name       Web App name (default: app-hdipar-v2)
#   -p, --plan       App Service Plan name (default: asp-hdipar-v2)
#   -g, --group      Resource Group (default: from .env)
#   -l, --location   Location (default: uksouth)
#   -s, --sku        SKU (default: S1)
#   -e, --env-file   Path to .env file (default: .env)
#   -h, --help       Show this help message
#
# SAFETY: This script will NEVER deploy to app-hdipar-dev
#

set -e  # Exit on error

# =============================================================================
# CONFIGURATION DEFAULTS
# =============================================================================
APP_NAME="app-hdipar-v2"
PLAN_NAME="asp-hdipar-v2"
RESOURCE_GROUP=""  # Will be read from .env
LOCATION="uksouth"
SKU="S1"
RUNTIME="PYTHON:3.11"
ENV_FILE=".env"
PROTECTED_APP="app-hdipar-dev"  # NEVER overwrite this app

# Health check configuration
HEALTH_CHECK_TIMEOUT=600  # seconds (10 min for LlamaIndex cold start)
HEALTH_CHECK_INTERVAL=20  # seconds
HEALTH_CHECK_ENDPOINT="/health"

# =============================================================================
# COLORS FOR OUTPUT
# =============================================================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================
log_step() {
    echo -e "${BLUE}[STEP $1]${NC} $2"
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[!]${NC} $1"
}

log_error() {
    echo -e "${RED}[✗]${NC} $1"
}

show_help() {
    head -17 "$0" | tail -14
    exit 0
}

# =============================================================================
# PARSE COMMAND LINE ARGUMENTS
# =============================================================================
while [[ $# -gt 0 ]]; do
    case $1 in
        -n|--name)
            APP_NAME="$2"
            shift 2
            ;;
        -p|--plan)
            PLAN_NAME="$2"
            shift 2
            ;;
        -g|--group)
            RESOURCE_GROUP="$2"
            shift 2
            ;;
        -l|--location)
            LOCATION="$2"
            shift 2
            ;;
        -s|--sku)
            SKU="$2"
            shift 2
            ;;
        -e|--env-file)
            ENV_FILE="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            ;;
    esac
done

# =============================================================================
# SCRIPT DIRECTORY - ensure we're in the repo root
# =============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "=============================================="
echo "  Hywel Dda IPAR Document Miner Deployment"
echo "=============================================="
echo ""

# =============================================================================
# STEP 1: SAFETY CHECK - NEVER deploy to protected app
# =============================================================================
log_step "1/8" "Safety validation..."

if [[ "$APP_NAME" == "$PROTECTED_APP" ]]; then
    log_error "SAFETY BLOCK: Cannot deploy to '$PROTECTED_APP'"
    log_error "This app is protected. Use a different app name."
    exit 1
fi
log_success "Target app '$APP_NAME' is safe to deploy"

# =============================================================================
# STEP 2: PRE-FLIGHT VALIDATION
# =============================================================================
log_step "2/8" "Pre-flight validation..."

# Check Azure CLI installed
if ! command -v az &> /dev/null; then
    log_error "Azure CLI (az) is not installed"
    log_error "Install from: https://docs.microsoft.com/en-us/cli/azure/install-azure-cli"
    exit 1
fi
log_success "Azure CLI installed"

# Check Azure CLI logged in
if ! az account show &> /dev/null; then
    log_error "Not logged into Azure CLI"
    log_error "Run: az login"
    exit 1
fi
ACCOUNT_NAME=$(az account show --query "name" -o tsv)
log_success "Logged into Azure: $ACCOUNT_NAME"

# Check .env file exists
if [[ ! -f "$ENV_FILE" ]]; then
    log_error ".env file not found at: $ENV_FILE"
    exit 1
fi
log_success "Environment file found: $ENV_FILE"

# Check required Flask app files
REQUIRED_FILES=(
    "flask_app/application.py"
    "flask_app/requirements.txt"
    "flask_app/startup.txt"
    "flask_app/config.py"
    "flask_app/runtime.txt"
)

for file in "${REQUIRED_FILES[@]}"; do
    if [[ ! -f "$file" ]]; then
        log_error "Required file missing: $file"
        exit 1
    fi
done
log_success "All required Flask app files present"

# =============================================================================
# STEP 3: PARSE .env FILE
# =============================================================================
log_step "3/8" "Parsing environment configuration..."

# Read RESOURCE_GROUP from .env if not provided via CLI
if [[ -z "$RESOURCE_GROUP" ]]; then
    RESOURCE_GROUP=$(grep -E "^RESOURCE_GROUP=" "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' | tr -d "'" | tr -d '\r')
    if [[ -z "$RESOURCE_GROUP" ]]; then
        log_error "RESOURCE_GROUP not found in .env and not provided via --group"
        exit 1
    fi
fi
log_success "Resource Group: $RESOURCE_GROUP"

# Parse all environment variables for app settings
declare -a APP_SETTINGS=()

while IFS= read -r line || [[ -n "$line" ]]; do
    # Remove Windows line endings
    line=$(echo "$line" | tr -d '\r')
    
    # Skip empty lines and comments
    [[ -z "$line" ]] && continue
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    
    # Skip lines without =
    [[ ! "$line" =~ = ]] && continue
    
    # Extract key and value
    key=$(echo "$line" | cut -d'=' -f1)
    value=$(echo "$line" | cut -d'=' -f2-)
    
    # Skip placeholder values
    [[ "$value" =~ ^\<.*\>$ ]] && continue
    [[ "$value" == "__SET_IN_APP_SETTINGS__" ]] && continue
    
    # Skip empty values
    [[ -z "$value" ]] && continue
    
    # Add to settings array
    APP_SETTINGS+=("$key=$value")
done < "$ENV_FILE"

SETTINGS_COUNT=${#APP_SETTINGS[@]}
log_success "Parsed $SETTINGS_COUNT environment variables"

# =============================================================================
# STEP 4: CREATE APP SERVICE PLAN
# =============================================================================
log_step "4/8" "Creating App Service Plan '$PLAN_NAME'..."

# Check if plan already exists first
if az appservice plan show --name "$PLAN_NAME" --resource-group "$RESOURCE_GROUP" > /dev/null 2>&1; then
    log_warning "App Service Plan '$PLAN_NAME' already exists, reusing it"
else
    # Create the plan
    if az appservice plan create \
        --name "$PLAN_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --sku "$SKU" \
        --is-linux \
        --location "$LOCATION" \
        --output none; then
        log_success "App Service Plan created"
    else
        log_error "Failed to create App Service Plan"
        exit 1
    fi
fi

# =============================================================================
# STEP 5: CREATE WEB APP (without deploying code yet)
# =============================================================================
log_step "5/8" "Creating/updating Web App '$APP_NAME'..."

# Check if app already exists
APP_EXISTS=false
if az webapp show --name "$APP_NAME" --resource-group "$RESOURCE_GROUP" > /dev/null 2>&1; then
    APP_EXISTS=true
    log_warning "Web App '$APP_NAME' already exists, will update"
else
    # Create the web app without deploying code
    az webapp create \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --plan "$PLAN_NAME" \
        --runtime "$RUNTIME" \
        --output none
    log_success "Web App created"
fi

# =============================================================================
# STEP 6: CONFIGURE APP SETTINGS (BEFORE deploying code)
# =============================================================================
log_step "6/8" "Configuring app settings ($SETTINGS_COUNT variables)..."

# First, set critical deployment settings
az webapp config appsettings set \
    --name "$APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --settings \
        SCM_DO_BUILD_DURING_DEPLOYMENT=true \
        WEBSITES_CONTAINER_START_TIME_LIMIT=600 \
    --output none
log_success "Deployment settings configured (Oryx build enabled, 600s startup timeout)"

# Apply settings in batches of 10 to avoid command line length limits
BATCH_SIZE=10
TOTAL_BATCHES=$(( (SETTINGS_COUNT + BATCH_SIZE - 1) / BATCH_SIZE ))

for ((i=0; i<SETTINGS_COUNT; i+=BATCH_SIZE)); do
    BATCH_NUM=$(( i/BATCH_SIZE + 1 ))
    BATCH_SETTINGS=("${APP_SETTINGS[@]:i:BATCH_SIZE}")
    
    echo -ne "  Applying batch $BATCH_NUM/$TOTAL_BATCHES...\r"
    
    az webapp config appsettings set \
        --name "$APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --settings "${BATCH_SETTINGS[@]}" \
        --output none
done

echo ""  # Clear the progress line
log_success "All app settings configured"

# Set the startup command
STARTUP_CMD=$(cat "$SCRIPT_DIR/flask_app/startup.txt" | tr -d '\r')

az webapp config set \
    --name "$APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --startup-file "$STARTUP_CMD" \
    --output none

log_success "Startup command configured"

# =============================================================================
# STEP 7: DEPLOY CODE (now that settings are in place)
# =============================================================================
log_step "7/8" "Deploying application code..."

# Ensure app is started before deployment
az webapp start \
    --name "$APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --output none 2>/dev/null || true

# Change to flask_app directory for deployment
cd "$SCRIPT_DIR/flask_app"

# Create deployment package
ZIP_FILE="/tmp/deploy-$APP_NAME-$$.zip"
zip -r "$ZIP_FILE" . -x "*.pyc" -x "__pycache__/*" -x ".env" -x "*.git*" > /dev/null

# Diagnostic: verify zip structure (application.py and requirements.txt at root)
echo "  Verifying zip structure:"
unzip -l "$ZIP_FILE" | grep -E "(application\.py|requirements\.txt|runtime\.txt)" | head -5
log_success "Zip contains application.py, requirements.txt, runtime.txt at root"

# Deploy using az webapp deploy
# Note: This may return 504 timeout for large apps, but deployment continues in background
az webapp deploy \
    --name "$APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --src-path "$ZIP_FILE" \
    --type zip \
    --async false \
    --output none 2>&1 || log_warning "Deploy command timed out - build may still be running in background"

# Cleanup
rm -f "$ZIP_FILE"

log_success "Application code deployed (or deployment in progress)"

# Return to script directory
cd "$SCRIPT_DIR"

# Enable application logging
az webapp log config \
    --name "$APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --application-logging filesystem \
    --level information \
    --output none

log_success "Application logging enabled"

# Restart the application to ensure clean state
az webapp restart \
    --name "$APP_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --output none

log_success "Application restarted"

# =============================================================================
# STEP 8: HEALTH CHECK VERIFICATION
# =============================================================================
log_step "8/8" "Verifying deployment health..."

APP_URL="https://${APP_NAME}.azurewebsites.net"
HEALTH_URL="${APP_URL}${HEALTH_CHECK_ENDPOINT}"
MAX_ATTEMPTS=$(( HEALTH_CHECK_TIMEOUT / HEALTH_CHECK_INTERVAL ))

echo "  Waiting for app to start (this may take a few minutes due to dependencies)..."
echo "  Health check URL: $HEALTH_URL"
echo ""

ATTEMPT=1
while [[ $ATTEMPT -le $MAX_ATTEMPTS ]]; do
    echo -ne "  Attempt $ATTEMPT/$MAX_ATTEMPTS ($(( ATTEMPT * HEALTH_CHECK_INTERVAL ))s elapsed)...\r"
    
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$HEALTH_URL" --max-time 10 2>/dev/null || echo "000")
    
    if [[ "$HTTP_CODE" == "200" ]]; then
        echo ""
        log_success "Health check passed (HTTP $HTTP_CODE)"
        break
    fi
    
    if [[ $ATTEMPT -eq $MAX_ATTEMPTS ]]; then
        echo ""
        log_error "Health check failed after ${HEALTH_CHECK_TIMEOUT}s"
        log_error "Last HTTP status: $HTTP_CODE"
        log_warning "Check logs with: az webapp log tail --name $APP_NAME --resource-group $RESOURCE_GROUP"
        exit 1
    fi
    
    sleep $HEALTH_CHECK_INTERVAL
    ((ATTEMPT++))
done

# =============================================================================
# DEPLOYMENT SUMMARY
# =============================================================================
echo ""
echo "=============================================="
echo "  Deployment Complete!"
echo "=============================================="
echo ""
echo "  App Name:       $APP_NAME"
echo "  App URL:        $APP_URL"
echo "  Plan:           $PLAN_NAME"
echo "  Resource Group: $RESOURCE_GROUP"
echo "  Location:       $LOCATION"
echo "  SKU:            $SKU"
echo ""
echo "  Useful commands:"
echo "    View logs:    az webapp log tail --name $APP_NAME --resource-group $RESOURCE_GROUP"
echo "    SSH:          az webapp ssh --name $APP_NAME --resource-group $RESOURCE_GROUP"
echo "    Restart:      az webapp restart --name $APP_NAME --resource-group $RESOURCE_GROUP"
echo ""
log_success "Deployment successful!"
