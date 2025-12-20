#!/bin/bash
# HIMARI Opus1 - TimescaleDB Analytics Setup
# Target: Hetzner CPX11 (2 vCPU, 4GB RAM, 40GB NVMe)
# Cost: ~$12/month

set -e

echo "=========================================="
echo "HIMARI Opus1 - TimescaleDB Setup"
echo "=========================================="

# Configuration - UPDATE THIS PASSWORD!
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-$(openssl rand -base64 24)}"
HIMARI_PASSWORD="${HIMARI_PASSWORD:-$(openssl rand -base64 24)}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root"
    exit 1
fi

# Step 1: Install prerequisites
log_info "Installing prerequisites..."
apt-get update
apt-get install -y gnupg postgresql-common apt-transport-https lsb-release wget

# Step 2: Add TimescaleDB repository
log_info "Adding TimescaleDB repository..."
echo "deb https://packagecloud.io/timescale/timescaledb/ubuntu/ $(lsb_release -c -s) main" | \
    tee /etc/apt/sources.list.d/timescaledb.list
wget --quiet -O - https://packagecloud.io/timescale/timescaledb/gpgkey | apt-key add -

# Step 3: Install TimescaleDB
log_info "Installing TimescaleDB with PostgreSQL 16..."
apt-get update
apt-get install -y timescaledb-2-postgresql-16

# Step 4: Run TimescaleDB tuning
log_info "Running TimescaleDB auto-tuning..."
timescaledb-tune --yes

# Step 5: Restart PostgreSQL
log_info "Restarting PostgreSQL..."
systemctl restart postgresql

# Step 6: Set postgres password
log_info "Setting PostgreSQL passwords..."
sudo -u postgres psql -c "ALTER USER postgres PASSWORD '$POSTGRES_PASSWORD';"

# Step 7: Create HIMARI database and user
log_info "Creating HIMARI database..."
sudo -u postgres psql << EOF
-- Create himari user
CREATE USER himari WITH PASSWORD '$HIMARI_PASSWORD';

-- Create database
CREATE DATABASE himari_analytics OWNER himari;

-- Connect to database
\c himari_analytics

-- Enable TimescaleDB
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE himari_analytics TO himari;
GRANT ALL ON SCHEMA public TO himari;
EOF

# Step 8: Configure PostgreSQL for remote access (optional, from private network only)
log_info "Configuring PostgreSQL network settings..."
PG_HBA="/etc/postgresql/16/main/pg_hba.conf"
echo "# HIMARI - Allow connections from private network" >> $PG_HBA
echo "host    himari_analytics    himari    10.0.0.0/8    scram-sha-256" >> $PG_HBA

POSTGRESQL_CONF="/etc/postgresql/16/main/postgresql.conf"
sed -i "s/#listen_addresses = 'localhost'/listen_addresses = '127.0.0.1'/" $POSTGRESQL_CONF

systemctl restart postgresql

# Step 9: Verify installation
log_info "Verifying TimescaleDB installation..."
sudo -u postgres psql -d himari_analytics -c "SELECT extname, extversion FROM pg_extension WHERE extname = 'timescaledb';"

echo ""
echo "=========================================="
echo "TimescaleDB Setup Complete!"
echo "=========================================="
echo ""
log_warn "SAVE THESE CREDENTIALS SECURELY!"
echo ""
echo "PostgreSQL (postgres user):"
echo "  Password: $POSTGRES_PASSWORD"
echo ""
echo "HIMARI Database User:"
echo "  Database: himari_analytics"
echo "  Username: himari"
echo "  Password: $HIMARI_PASSWORD"
echo ""
echo "Connection string:"
echo "  postgresql://himari:<password>@localhost:5432/himari_analytics"
echo ""
echo "Next step: Run ./07_timescale_schema.sh to create tables"
echo ""
