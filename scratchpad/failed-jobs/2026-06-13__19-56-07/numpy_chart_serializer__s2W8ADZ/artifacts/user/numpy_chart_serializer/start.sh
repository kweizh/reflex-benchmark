#!/bin/bash
set -e
cd /home/user/numpy_chart_serializer
uv sync
# reflex init is already done, but if .web is missing it should run.
if [ ! -d ".web" ]; then
    uv run reflex init --template blank
fi
uv run reflex db init
uv run reflex db migrate
uv run reflex run --loglevel info
