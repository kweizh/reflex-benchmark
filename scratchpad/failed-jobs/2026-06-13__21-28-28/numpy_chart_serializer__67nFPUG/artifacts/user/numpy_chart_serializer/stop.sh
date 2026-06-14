#!/usr/bin/env bash
set -euo pipefail

# Kill any process listening on ports 3000 and 8000
for port in 3000 8000; do
    pids=$(lsof -t -i :"$port" 2>/dev/null || true)
    if [ -n "$pids" ]; then
        echo "Killing processes on port $port: $pids"
        kill -9 $pids 2>/dev/null || true
    fi
done

# Also kill any reflex-related processes
pkill -f "reflex run" 2>/dev/null || true
pkill -f "reflex" 2>/dev/null || true

# Wait briefly and verify ports are free
sleep 1
for port in 3000 8000; do
    if lsof -t -i :"$port" 2>/dev/null; then
        echo "Warning: port $port is still in use"
        lsof -t -i :"$port" 2>/dev/null | xargs kill -9 2>/dev/null || true
    fi
done

echo "Ports 3000 and 8000 are now free."