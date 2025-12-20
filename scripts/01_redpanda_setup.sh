#!/bin/bash
# HIMARI Opus1 - Redpanda Message Broker Setup
# Target: Hetzner CPX21 (4 vCPU, 8GB RAM, 80GB NVMe)
# Cost: ~$15/month

set -e

echo "=========================================="
echo "HIMARI Opus1 - Redpanda Setup"
echo "=========================================="

# Configuration - UPDATE THESE VALUES
PRIVATE_IP="${PRIVATE_IP:-$(hostname -I | awk '{print $1}')}"
REDPANDA_VERSION="latest"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    log_error "Please run as root"
    exit 1
fi

# Step 1: Update system
log_info "Updating system packages..."
apt-get update && apt-get upgrade -y

# Step 2: Install prerequisites
log_info "Installing prerequisites..."
apt-get install -y curl gnupg2 ca-certificates lsb-release

# Step 3: Install Redpanda
log_info "Installing Redpanda..."
curl -1sLf 'https://dl.redpanda.com/nzc4FFFFF/redpanda/cfg/setup/bash.deb.sh' | bash
apt-get install -y redpanda

# Step 4: Configure Redpanda for single-node production
log_info "Configuring Redpanda..."
rpk redpanda config bootstrap --self $PRIVATE_IP --ips $PRIVATE_IP
rpk redpanda config set redpanda.empty_seed_starts_cluster false

# Step 5: Set memory limits (leave 2GB for OS)
rpk redpanda config set redpanda.developer_mode false
rpk redpanda config set rpk.tune_network true
rpk redpanda config set rpk.tune_disk_scheduler true
rpk redpanda config set rpk.tune_disk_nomerges true
rpk redpanda config set rpk.tune_disk_write_cache true

# Step 6: Create production configuration
log_info "Creating production configuration..."
cat > /etc/redpanda/redpanda.yaml << 'EOF'
# HIMARI Opus1 - Redpanda Production Configuration
redpanda:
  data_directory: /var/lib/redpanda/data
  
  # Memory configuration (6GB for Redpanda, 2GB for OS)
  memory:
    enable_memory_locking: true
    reserved_memory: 2G
  
  # Network configuration
  rpc_server:
    address: 0.0.0.0
    port: 33145
  
  kafka_api:
    - address: 0.0.0.0
      port: 9092
      name: internal
    - address: 0.0.0.0
      port: 9093
      name: external
      authentication_method: sasl
  
  admin:
    - address: 127.0.0.1  # Only localhost for admin
      port: 9644
  
  # Performance tuning
  group_topic_partitions: 16
  default_topic_partitions: 12
  default_topic_replications: 1  # Single node, no replication
  
  # Retention settings
  log_retention_ms: 604800000      # 7 days
  log_segment_size: 134217728      # 128MB segments

# Enable SASL authentication
rpk:
  kafka_api:
    sasl:
      user: himari-producer
      type: SCRAM-SHA-256
  
  # Tuning
  tune_network: true
  tune_disk_scheduler: true
  tune_disk_nomerges: true
  tune_disk_write_cache: true

# Monitoring
pandaproxy: {}
schema_registry: {}
EOF

# Step 7: Run system tuning
log_info "Running system tuning..."
rpk redpanda tune all || log_warn "Some tuning options may have failed (non-critical)"

# Step 8: Enable and start Redpanda
log_info "Starting Redpanda service..."
systemctl enable redpanda
systemctl start redpanda

# Wait for startup
log_info "Waiting for Redpanda to start..."
sleep 10

# Step 9: Verify installation
log_info "Verifying installation..."
if rpk cluster info; then
    log_info "Redpanda cluster is healthy!"
else
    log_error "Redpanda cluster health check failed"
    exit 1
fi

echo ""
echo "=========================================="
echo "Redpanda Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Run ./02_redpanda_topics.sh to create topics"
echo "2. Run ./03_redpanda_auth.sh to set up authentication"
echo ""
echo "Useful commands:"
echo "  rpk cluster info          - Check cluster status"
echo "  rpk topic list            - List topics"
echo "  systemctl status redpanda - Check service status"
echo ""
