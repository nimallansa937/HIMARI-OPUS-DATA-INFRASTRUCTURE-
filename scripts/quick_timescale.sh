#!/bin/bash
# Quick TimescaleDB setup
timescaledb-tune --yes
systemctl restart postgresql
sleep 3
sudo -u postgres psql -c "CREATE DATABASE himari_analytics;"
sudo -u postgres psql -d himari_analytics -c "CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;"
echo "TimescaleDB setup complete!"
sudo -u postgres psql -d himari_analytics -c "SELECT extversion FROM pg_extension WHERE extname = 'timescaledb';"
