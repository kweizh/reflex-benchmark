#!/bin/bash
cd /home/user/numpy_chart_serializer
uv sync
if [ ! -d ".web" ]; then
    uv run reflex init --template blank
fi
uv run reflex run --loglevel info &
