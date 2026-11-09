#!/bin/bash
# Assumes a fresh ubuntu install, and that you are running this script as root.
# Execute this script from the Rootmap/backend/ directory.

# Install dependencies
echo "Installing backend dependencies..."
apt update && apt upgrade -y
apt install -y postgresql
apt install curl -y
curl -LsSf https://astral.sh/uv/install.sh | sh
. "$HOME/.local/bin/env"

# Get IP address and subnet mask
echo "Getting IP address and subnet mask..."
IP=$(ip -brief address show eth0 | awk '{print $3}' | awk -F/ '{print $1}')
SUBNET=$(ip -o -4 addr show dev eth0 | awk '{print $4}' | cut -d "/" -f 2)

# Configure PostgreSQL to listen on all interfaces (0.0.0.0)
echo "Configuring PostgreSQL to listen on all interfaces..."
sudo sed -i "s/#listen_addresses = 'localhost'/listen_addresses = '*'/g" /etc/postgresql/*/main/postgresql.conf
echo "host    rootmap_db      rootmap_user    ${IP}/${SUBNET}       scram-sha-256" | sudo tee -a /etc/postgresql/*/main/pg_hba.conf

# Start and enable PostgreSQL service
echo "Starting and enabling PostgreSQL service..."
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create PostgreSQL user and database
echo "Creating PostgreSQL user and database..."
sudo -u postgres psql -c "CREATE USER rootmap_user WITH PASSWORD '12345';"
sudo -u postgres psql -c "CREATE DATABASE rootmap_db;"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE rootmap_db TO rootmap_user;"
sudo -u postgres psql -c "ALTER DATABASE rootmap_db OWNER TO rootmap_user;"
sudo -u postgres psql -d rootmap_db -c "GRANT ALL ON SCHEMA public TO rootmap_user;"

# Write the DATABASE_URL to a .env file
echo "Writing DATABASE_URL to .env file..."
echo "DATABASE_URL=postgresql://rootmap_user:12345@${IP}:5432/rootmap_db" | sudo tee -a .env

# Sync the project and initialize the database
echo "Syncing the project and initializing the database..."
uv sync --locked
uv run python -m src.db.init_db

# Configuration
SERVICE_NAME="rootmap_backend"
APP_MODULE="main:app"
HOST="0.0.0.0"
PORT="2005"
APP_USER="root"

# Detect directory and current uv path
PROJECT_DIR=$(pwd)
UV_BINARY=$(which uv)

# Create systemd service file
echo "Writing systemd service file..."
SERVICE_FILE_CONTENT="[Unit]
Description=Rootmap Backend Service
After=network.target

[Service]
User=$APP_USER
Group=$APP_USER
WorkingDirectory=$PROJECT_DIR
ExecStart=$UV_BINARY run uvicorn $APP_MODULE --host $HOST --port $PORT
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target"

echo "$SERVICE_FILE_CONTENT" | sudo tee /etc/systemd/system/$SERVICE_NAME.service > /dev/null

# Reload systemd and start the service
echo "Reloading systemd daemon..."
sudo systemctl daemon-reload

echo "Enabling and starting $SERVICE_NAME.service..."
sudo systemctl enable $SERVICE_NAME.service
sudo systemctl start $SERVICE_NAME.service

# Check status
echo "Checking service status..."
sudo systemctl status $SERVICE_NAME.service --no-pager