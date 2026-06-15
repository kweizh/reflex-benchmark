#!/usr/bin/env bash
set -eo pipefail

# Check for required environment variables
if [ -z "${REFLEX_CLOUD_TOKEN}" ]; then
  echo "Error: REFLEX_CLOUD_TOKEN is not set." >&2
  exit 1
fi

if [ -z "${REFLEX_CLOUD_PROJECT_ID}" ]; then
  echo "Error: REFLEX_CLOUD_PROJECT_ID is not set." >&2
  exit 1
fi

PROJECT_DIR="/home/user/myproject"
cd "${PROJECT_DIR}"

# Generate a unique app name with a random suffix
SUFFIX=$(python3 -c "import secrets; print(secrets.token_hex(4))")
APP_NAME="myproject-${SUFFIX}"

echo "Deploying app: ${APP_NAME} to Reflex Cloud..."

# Run the deploy command
uv run reflex deploy \
  --app-name "${APP_NAME}" \
  --project "${REFLEX_CLOUD_PROJECT_ID}" \
  --token "${REFLEX_CLOUD_TOKEN}" \
  --no-interactive

# Write the deployed app name to deploy.log
echo "Deployed app: ${APP_NAME}" > "${PROJECT_DIR}/deploy.log"
echo "Successfully logged deployment name to ${PROJECT_DIR}/deploy.log"

# Cleanup function to kill any Reflex background processes (frontend on 3000 or backend on 8000)
echo "Cleaning up any background processes..."
python3 -c '
import os, signal
target_ports = {3000, 8000}
inodes = set()
for proto in ["tcp", "tcp6"]:
    path = f"/proc/net/{proto}"
    if os.path.exists(path):
        with open(path, "r") as f:
            for line in f.readlines()[1:]:
                parts = line.strip().split()
                if len(parts) >= 10:
                    try:
                        _, port_hex = parts[1].split(":")
                        port = int(port_hex, 16)
                        if port in target_ports:
                            inodes.add(parts[9])
                    except:
                        pass
for pid_str in os.listdir("/proc"):
    if pid_str.isdigit():
        pid = int(pid_str)
        if pid == os.getpid():
            continue
        killed = False
        fd_dir = f"/proc/{pid_str}/fd"
        if os.path.exists(fd_dir):
            try:
                for fd in os.listdir(fd_dir):
                    link = os.readlink(os.path.join(fd_dir, fd))
                    if link.startswith("socket:["):
                        inode = link[8:-1]
                        if inode in inodes:
                            print(f"Killing process {pid} listening on port")
                            os.kill(pid, signal.SIGKILL)
                            killed = True
                            break
            except:
                pass
        if killed:
            continue
        cmdline_path = f"/proc/{pid_str}/cmdline"
        if os.path.exists(cmdline_path):
            try:
                with open(cmdline_path, "rb") as f:
                    cmdline = f.read().replace(b"\x00", b" ").decode("utf-8", errors="ignore")
                if cmdline:
                    cmd_lower = cmdline.lower()
                    if "reflex" in cmd_lower or "granian" in cmd_lower or "bun" in cmd_lower:
                        if "deploy.sh" not in cmdline and "bash" not in cmd_lower:
                            print(f"Killing background process {pid}: {cmdline[:100]}")
                            os.kill(pid, signal.SIGKILL)
            except:
                pass
'

echo "Cleanup complete."
