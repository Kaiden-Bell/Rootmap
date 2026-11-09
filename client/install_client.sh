#!/bin/bash
# Assumes a fresh ubuntu install, and that you are running this script as root.
# Execute this script from the Rootmap/client/ directory.

# Install dependencies
apt update && apt upgrade -y
apt install curl -y
curl -LsSf https://astral.sh/uv/install.sh | sh
. "$HOME/.local/bin/env"
uv sync --locked

echo "Send system information to the head node: uv run main.py --head-ip 10.105.165.112 --head-port 2005"