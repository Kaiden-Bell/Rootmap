#!/bin/bash
# Assumes install_backend.sh has been run, and that you are running this script as root.
# Execute this script from the Rootmap/frontend/ directory.

# Install dependencies
echo "Installing frontend dependencies..."
apt update && apt upgrade -y
apt install npm -y
npm install

# Configuration
SERVICE_NAME="rootmap_frontend"
HOST="0.0.0.0"
PORT="5173"
APP_USER="root"

# Detect project directory
PROJECT_DIR=$(pwd)

# Create systemd service file
echo "Writing systemd service file..."
SERVICE_FILE_CONTENT="[Unit]
Description=Rootmap Frontend Service
After=network.target rootmap_backend.service

[Service]
Type=simple
User=$APP_USER
WorkingDirectory=$PROJECT_DIR
ExecStart=/usr/bin/npm run dev -- --host $HOST --port $PORT
Restart=on-failure

[Install]
WantedBy=multi-user.target"

echo "$SERVICE_FILE_CONTENT" | sudo tee /etc/systemd/system/$SERVICE_NAME.service > /dev/null

# Reload systemd and start the service
echo "Reloading systemd daemon..."
sudo systemctl daemon-reload

echo "Enabling and starting $SERVICE_NAME.service..."
sudo systemctl enable $SERVICE_NAME.service
sudo systemctl restart $SERVICE_NAME.service

# Check status
echo "Checking service status..."
sudo systemctl status $SERVICE_NAME.service --no-pager