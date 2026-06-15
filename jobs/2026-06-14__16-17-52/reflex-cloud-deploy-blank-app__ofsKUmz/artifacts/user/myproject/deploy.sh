#!/usr/bin/env bash
# deploy.sh – non-interactive deploy of a Reflex app to Reflex Cloud.
# Reads REFLEX_CLOUD_TOKEN and REFLEX_CLOUD_PROJECT_ID from the environment.
# Generates a unique app name at execution time so each run is distinct.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Validate required environment variables ──────────────────────────────────
: "${REFLEX_CLOUD_TOKEN:?REFLEX_CLOUD_TOKEN must be set}"
: "${REFLEX_CLOUD_PROJECT_ID:?REFLEX_CLOUD_PROJECT_ID must be set}"

# ── Generate a unique app name at runtime ────────────────────────────────────
SUFFIX="$(python3 -c "import secrets; print(secrets.token_hex(4))")"
APP_NAME="myproject-${SUFFIX}"

echo "Deploying app: ${APP_NAME}"

# ── Deploy to Reflex Cloud ────────────────────────────────────────────────────
uv run reflex deploy \
  --app-name "${APP_NAME}" \
  --project "${REFLEX_CLOUD_PROJECT_ID}" \
  --token "${REFLEX_CLOUD_TOKEN}" \
  --no-interactive \
  --loglevel info

# ── Record deployed app name ─────────────────────────────────────────────────
echo "Deployed app: ${APP_NAME}" > "${SCRIPT_DIR}/deploy.log"
echo "Deploy log written to ${SCRIPT_DIR}/deploy.log"

# ── Kill any Reflex background processes that may have been started ───────────
# Frontend (port 3000) and backend (port 8000)
for PORT in 3000 8000; do
  PIDS="$(lsof -ti tcp:${PORT} 2>/dev/null || true)"
  if [ -n "${PIDS}" ]; then
    echo "Killing processes on port ${PORT}: ${PIDS}"
    echo "${PIDS}" | xargs kill -9 2>/dev/null || true
  fi
done

# Also kill any lingering reflex processes by name
pkill -f "reflex run" 2>/dev/null || true
pkill -f "uvicorn"    2>/dev/null || true

echo "Done. App '${APP_NAME}' deployed to Reflex Cloud."
