#!/bin/bash
# Kill processes on port 3000 and 8000
fuser -k 3000/tcp || true
fuser -k 8000/tcp || true
