#!/bin/bash
# HIMARI Opus1 - Redis Feature Store Setup
# Deploys self-hosted Redis on Flink server for sub-10ms feature serving

set -e

echo "=========================================="
echo "HIMARI Opus1 - Redis Feature Store Setup"
echo "=========================================="

# Configuration - UPDATE THIS PASSWORD!
REDIS_PASSWORD="${REDIS_PASSWORD:-$(openssl rand -base64 24)}"

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

# Step 1: Install Redis
log_info "Installing Redis..."
apt-get update
apt-get install -y redis-server

# Step 2: Create Redis configuration
log_info "Creating Redis configuration..."
cat > /etc/redis/redis.conf << EOF
# HIMARI Opus1 - Redis Production Configuration

# Network
bind 127.0.0.1
port 6379
protected-mode yes
requirepass ${REDIS_PASSWORD}

# Memory (2GB max, leave room for Flink)
maxmemory 2gb
maxmemory-policy volatile-lru

# Persistence (AOF for durability)
appendonly yes
appendfsync everysec
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb

# RDB snapshots
save 900 100
save 300 1000
save 60 10000
dbfilename dump.rdb
dir /var/lib/redis

# Performance
tcp-keepalive 300
timeout 0
tcp-backlog 511

# Logging
loglevel notice
logfile /var/log/redis/redis-server.log

# Security
rename-command FLUSHDB ""
rename-command FLUSHALL ""
rename-command DEBUG ""
rename-command CONFIG "HIMARI_CONFIG"
EOF

# Step 3: Create log directory
mkdir -p /var/log/redis
chown redis:redis /var/log/redis

# Step 4: Optimize system for Redis
log_info "Optimizing system settings..."
echo 'vm.overcommit_memory = 1' >> /etc/sysctl.conf
echo 'net.core.somaxconn = 65535' >> /etc/sysctl.conf
sysctl -p

# Disable transparent huge pages
echo never > /sys/kernel/mm/transparent_hugepage/enabled || true
echo never > /sys/kernel/mm/transparent_hugepage/defrag || true

# Step 5: Enable and start Redis
log_info "Starting Redis service..."
systemctl enable redis-server
systemctl restart redis-server

# Wait for startup
sleep 3

# Step 6: Verify installation
log_info "Verifying Redis installation..."
if redis-cli -a "$REDIS_PASSWORD" ping | grep -q "PONG"; then
    log_info "Redis is running and responding!"
else
    log_warn "Redis may not be running correctly"
fi

# Show Redis info
redis-cli -a "$REDIS_PASSWORD" info server 2>/dev/null | grep -E "redis_version|uptime_in_seconds"

echo ""
echo "=========================================="
echo "Redis Setup Complete!"
echo "=========================================="
echo ""
log_warn "SAVE THIS PASSWORD SECURELY!"
echo ""
echo "Redis Password: $REDIS_PASSWORD"
echo ""
echo "Connection info:"
echo "  Host: 127.0.0.1"
echo "  Port: 6379"
echo ""
echo "Test connection:"
echo "  redis-cli -a '<password>' ping"
echo ""
echo "Monitor Redis:"
echo "  redis-cli -a '<password>' monitor"
echo ""
