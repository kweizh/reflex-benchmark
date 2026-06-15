#!/bin/bash
set -e

# Generate a unique suffix
SUFFIX=$(python3 -c "import secrets; print(secrets.token_hex(4))")
APP_NAME="myproject-$SUFFIX"

# Deploy to Reflex Cloud
uv run reflex deploy \
  --app-name "$APP_NAME" \
  --project "$REFLEX_CLOUD_PROJECT_ID" \
  --token "$REFLEX_CLOUD_TOKEN" \
  --no-interactive

# Log the deployed app name
echo "Deployed app: $APP_NAME" > /home/user/myproject/deploy.log

# Ensure no Reflex background processes are left running
pkill -f reflex || true
pkill -f uvicorn || true
pkill -f node || true
