#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

# 1. Sync dependencies
uv sync

# 2. Initialize Reflex if .web is missing
if [ ! -d ".web" ]; then
    uv run reflex init --template blank
fi

# 3. Launch the Reflex app (backend on 8000, frontend on 3000)
uv run reflex run --loglevel info
