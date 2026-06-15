#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/home/user/myproject"
LOG_FILE="${PROJECT_DIR}/deploy.log"

# Read credentials from environment
TOKEN="${REFLEX_CLOUD_TOKEN}"
PROJECT_ID="${REFLEX_CLOUD_PROJECT_ID}"

# Generate a unique app name suffix at deploy time
RANDOM_SUFFIX=$(python3 -c "import secrets; print(secrets.token_hex(4))")
APP_NAME="myapp-${RANDOM_SUFFIX}"

cd "${PROJECT_DIR}"

# Deploy to Reflex Cloud non-interactively
uv run reflex deploy \
  --app-name "${APP_NAME}" \
  --project "${PROJECT_ID}" \
  --token "${TOKEN}" \
  --no-interactive

# Write the deployed app name to the log file
echo "Deployed app: ${APP_NAME}" > "${LOG_FILE}"

# Kill any Reflex background processes (frontend on port 3000, backend on port 8000)
for PORT in 3000 8000; do
  pids=$(lsof -ti :${PORT} 2>/dev/null || true)
  if [ -n "${pids}" ]; then
    # shellcheck disable=SC2086
    kill ${pids} 2>/dev/null || true
  fi
done

echo "Deployment complete. App name: ${APP_NAME}"