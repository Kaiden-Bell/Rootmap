#!/bin/bash
# Assumes a fresh ubuntu install, and that you are running this script as root.
# Execute this script from the Rootmap/client/ directory.

# Install dependencies
apt update && apt upgrade -y
apt install curl -y
curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin UV_NO_MODIFY_PATH=1 sh
uv sync --locked

echo "Send system information to the head node: uv run main.py --head-ip <head_ip> --head-port <head_backend_port>"