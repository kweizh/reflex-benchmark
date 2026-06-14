#!/usr/bin/env bash
set -euo pipefail

# Kill any process bound to port 3000
fuser -k 3000/tcp 2>/dev/null || true

# Kill any process bound to port 8000
fuser -k 8000/tcp 2>/dev/null || true
