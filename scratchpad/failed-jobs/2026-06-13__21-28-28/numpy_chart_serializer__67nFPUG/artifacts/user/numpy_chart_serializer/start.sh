#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

# Ensure dependencies are installed
uv sync

# Initialize the Reflex frontend if .web directory doesn't exist
if [ ! -d ".web" ]; then
    uv run reflex init --template blank
fi

# Launch the app (both frontend on 3000 and backend on 8000)
uv run reflex run --loglevel info