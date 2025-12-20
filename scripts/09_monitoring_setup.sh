#!/bin/bash
# HIMARI Opus1 - Monitoring Setup (Prometheus + Grafana Cloud)
# Zero-cost monitoring stack

set -e

echo "=========================================="
echo "HIMARI Opus1 - Monitoring Setup"
echo "=========================================="

# Configuration
PROMETHEUS_VERSION="2.48.0"
NODE_EXPORTER_VERSION="1.7.0"
REDPANDA_IP="${REDPANDA_IP:-localhost}"

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

# Step 1: Install Prometheus
log_info "Installing Prometheus ${PROMETHEUS_VERSION}..."
cd /opt
wget https://github.com/prometheus/prometheus/releases/download/v${PROMETHEUS_VERSION}/prometheus-${PROMETHEUS_VERSION}.linux-amd64.tar.gz
tar -xzf prometheus-${PROMETHEUS_VERSION}.linux-amd64.tar.gz
mv prometheus-${PROMETHEUS_VERSION}.linux-amd64 prometheus
rm prometheus-${PROMETHEUS_VERSION}.linux-amd64.tar.gz

# Step 2: Create Prometheus configuration
log_info "Creating Prometheus configuration..."
mkdir -p /data/prometheus

cat > /opt/prometheus/prometheus.yml << EOF
# HIMARI Opus1 - Prometheus Configuration
global:
  scrape_interval: 15s
  evaluation_interval: 15s

# Alerting rules
rule_files:
  - "alert_rules.yml"

scrape_configs:
  # Prometheus self-monitoring
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  # Flink metrics
  - job_name: 'flink'
    static_configs:
      - targets: ['localhost:9249']
    metrics_path: /metrics

  # Redis metrics (requires redis_exporter)
  - job_name: 'redis'
    static_configs:
      - targets: ['localhost:9121']

  # Node metrics (system health)
  - job_name: 'node'
    static_configs:
      - targets: ['localhost:9100']

  # Redpanda metrics
  - job_name: 'redpanda'
    static_configs:
      - targets: ['${REDPANDA_IP}:9644']
    metrics_path: /public_metrics

# Uncomment and configure for Grafana Cloud integration
# remote_write:
#   - url: https://prometheus-prod-XX-prod-XX.grafana.net/api/prom/push
#     basic_auth:
#       username: <your-grafana-cloud-user-id>
#       password: <your-grafana-cloud-api-key>
EOF

# Step 3: Create systemd service for Prometheus
log_info "Creating Prometheus systemd service..."
cat > /etc/systemd/system/prometheus.service << 'EOF'
[Unit]
Description=Prometheus
After=network.target

[Service]
User=root
ExecStart=/opt/prometheus/prometheus \
    --config.file=/opt/prometheus/prometheus.yml \
    --storage.tsdb.path=/data/prometheus \
    --storage.tsdb.retention.time=15d \
    --web.listen-address=127.0.0.1:9090
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Step 4: Install Node Exporter
log_info "Installing Node Exporter ${NODE_EXPORTER_VERSION}..."
cd /opt
wget https://github.com/prometheus/node_exporter/releases/download/v${NODE_EXPORTER_VERSION}/node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64.tar.gz
tar -xzf node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64.tar.gz
mv node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64/node_exporter /usr/local/bin/
rm -rf node_exporter-${NODE_EXPORTER_VERSION}.linux-amd64*

# Step 5: Create systemd service for Node Exporter
log_info "Creating Node Exporter systemd service..."
cat > /etc/systemd/system/node_exporter.service << 'EOF'
[Unit]
Description=Node Exporter
After=network.target

[Service]
User=root
ExecStart=/usr/local/bin/node_exporter \
    --web.listen-address=127.0.0.1:9100
Restart=always

[Install]
WantedBy=multi-user.target
EOF

# Step 6: Copy alert rules
log_info "Copying alert rules..."
cp /opt/himari/prometheus/alert_rules.yml /opt/prometheus/ 2>/dev/null || \
    echo "Alert rules will need to be copied manually"

# Step 7: Start services
log_info "Starting monitoring services..."
systemctl daemon-reload
systemctl enable prometheus node_exporter
systemctl start prometheus node_exporter

# Wait for startup
sleep 5

# Step 8: Verify installation
log_info "Verifying installation..."
if curl -s http://localhost:9090/-/healthy > /dev/null; then
    log_info "Prometheus is running!"
else
    log_warn "Prometheus may not be running correctly"
fi

if curl -s http://localhost:9100/metrics > /dev/null; then
    log_info "Node Exporter is running!"
else
    log_warn "Node Exporter may not be running correctly"
fi

echo ""
echo "=========================================="
echo "Monitoring Setup Complete!"
echo "=========================================="
echo ""
echo "Services running:"
echo "  Prometheus: http://localhost:9090 (via SSH tunnel)"
echo "  Node Exporter: http://localhost:9100/metrics"
echo ""
echo "To set up Grafana Cloud (free tier):"
echo "  1. Sign up at grafana.com/products/cloud"
echo "  2. Create a Grafana Cloud stack"
echo "  3. Go to Connections > Prometheus"
echo "  4. Copy the remote_write configuration"
echo "  5. Add to /opt/prometheus/prometheus.yml"
echo "  6. Restart: systemctl restart prometheus"
echo ""
