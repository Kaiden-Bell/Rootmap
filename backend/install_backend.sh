#!/bin/bash
# Assumes a fresh ubuntu install, and that you are running this script as root.
# Execute this script from the Rootmap/backend/ directory.

DB_NAME="rootmap_db"
DB_USER="rootmap_user"

# Install dependencies
echo "Installing backend dependencies..."
apt update && apt upgrade -y
apt install -y postgresql curl

curl -LsSf https://astral.sh/uv/install.sh | sh
. "$HOME/.local/bin/env"

# Get IP address and subnet (network in CIDR form, e.g. 10.0.0.0/24)
echo "Getting IP address and subnet..."
IP=$(ip -brief address show eth0 | awk '{print $3}' | awk -F/ '{print $1}')
SUBNET=$(ip -o -4 route show dev eth0 proto kernel scope link | awk '{print $1; exit}')

PGVER=$(pg_lsclusters -h | awk '{print $1; exit}')
CONF_DIR="/etc/postgresql/${PGVER}/main"

# Configure PostgreSQL to listen on all interfaces (0.0.0.0)
echo "Configuring PostgreSQL to listen on all interfaces..."
echo "listen_addresses = '*'" | tee "${CONF_DIR}/conf.d/rootmap.conf" >/dev/null
HBA_LINE="host    ${DB_NAME}    ${DB_USER}    ${SUBNET}    scram-sha-256"
grep -qxF "$HBA_LINE" "${CONF_DIR}/pg_hba.conf" || echo "$HBA_LINE" >> "${CONF_DIR}/pg_hba.conf"

# Start and enable PostgreSQL service
echo "Starting and enabling PostgreSQL service..."
systemctl enable postgresql
systemctl restart "postgresql@${PGVER}-main"

# Create PostgreSQL user and database
echo "Creating PostgreSQL user and database..."
sudo -u postgres psql -c "CREATE USER ${DB_USER} WITH PASSWORD '12345';"
sudo -u postgres psql -c "CREATE DATABASE ${DB_NAME};"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};"
sudo -u postgres psql -c "ALTER DATABASE ${DB_NAME} OWNER TO ${DB_USER};"
sudo -u postgres psql -d ${DB_NAME} -c "GRANT ALL ON SCHEMA public TO ${DB_USER};"

# Write the DATABASE_URL to a .env file
echo "Writing DATABASE_URL to .env file..."
echo "DATABASE_URL=postgresql://${DB_USER}:12345@${IP}:5432/${DB_NAME}" | sudo tee -a .env

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
After=network.target postgresql.service

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
sudo systemctl restart $SERVICE_NAME.service

# Check status
echo "Checking service status..."
sudo systemctl status $SERVICE_NAME.service --no-pager