#!/bin/bash
# HIMARI Opus1 - Apache Flink Stream Processing Setup
# Target: Hetzner CPX41 (8 vCPU, 16GB RAM, 160GB NVMe)
# Cost: ~$30/month

set -e

echo "=========================================="
echo "HIMARI Opus1 - Apache Flink Setup"
echo "=========================================="

# Configuration
FLINK_VERSION="1.18.1"
SCALA_VERSION="2.12"
JAVA_VERSION="17"

# Colors
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

# Step 2: Install Java 17
log_info "Installing Java ${JAVA_VERSION}..."
apt-get install -y openjdk-${JAVA_VERSION}-jdk

# Verify Java
java -version
if [ $? -ne 0 ]; then
    log_error "Java installation failed"
    exit 1
fi

# Step 3: Download and install Flink
log_info "Downloading Flink ${FLINK_VERSION}..."
cd /opt
wget https://archive.apache.org/dist/flink/flink-${FLINK_VERSION}/flink-${FLINK_VERSION}-bin-scala_${SCALA_VERSION}.tgz
tar -xzf flink-${FLINK_VERSION}-bin-scala_${SCALA_VERSION}.tgz
mv flink-${FLINK_VERSION} flink
rm flink-${FLINK_VERSION}-bin-scala_${SCALA_VERSION}.tgz

# Step 4: Create directories
log_info "Creating Flink directories..."
mkdir -p /data/flink-checkpoints
mkdir -p /data/flink-savepoints
mkdir -p /var/log/flink
chown -R root:root /data/flink-*

# Step 5: Create production configuration
log_info "Creating Flink configuration..."
cat > /opt/flink/conf/flink-conf.yaml << 'EOF'
# HIMARI Opus1 - Flink Production Configuration
# Target: 16GB total RAM

# ============================================================
# MEMORY CONFIGURATION (16GB total RAM)
# ============================================================
# Budget: 16GB total
# - OS + buffers: 2GB
# - RocksDB off-heap: 4GB
# - JobManager: 2GB
# - TaskManager: 8GB
# ============================================================

jobmanager.memory.process.size: 2048m
taskmanager.memory.process.size: 8192m

# TaskManager memory breakdown
taskmanager.memory.managed.size: 2048m        # For RocksDB state
taskmanager.memory.network.fraction: 0.1       # Network buffers
taskmanager.memory.network.min: 256m
taskmanager.memory.network.max: 1024m

# JVM overhead (important for RocksDB)
taskmanager.memory.jvm-overhead.min: 512m
taskmanager.memory.jvm-overhead.max: 2048m
taskmanager.memory.jvm-overhead.fraction: 0.1

# ============================================================
# PARALLELISM
# ============================================================
taskmanager.numberOfTaskSlots: 4               # 4 parallel tasks
parallelism.default: 4                         # Match slot count

# ============================================================
# NETWORK
# ============================================================
jobmanager.rpc.address: 0.0.0.0
jobmanager.rpc.port: 6123
taskmanager.rpc.port: 6124

# REST API (localhost only for security)
rest.port: 8081
rest.bind-address: 127.0.0.1                   # NOT 0.0.0.0!

# ============================================================
# STATE BACKEND (RocksDB)
# ============================================================
state.backend: rocksdb
state.backend.rocksdb.localdir: /data/flink-rocksdb
state.backend.rocksdb.memory.managed: true

# ============================================================
# CHECKPOINT SETTINGS
# ============================================================
execution.checkpointing.mode: EXACTLY_ONCE
execution.checkpointing.interval: 30000        # Every 30 seconds
execution.checkpointing.min-pause: 10000       # 10s between checkpoints
execution.checkpointing.timeout: 120000        # 2 minute timeout
execution.checkpointing.max-concurrent-checkpoints: 1

# Checkpoint storage
state.checkpoint-storage: filesystem
state.checkpoints.dir: file:///data/flink-checkpoints
state.savepoints.dir: file:///data/flink-savepoints
state.checkpoints.num-retained: 3              # Keep last 3

# ============================================================
# RESTART STRATEGY
# ============================================================
restart-strategy: fixed-delay
restart-strategy.fixed-delay.attempts: 5
restart-strategy.fixed-delay.delay: 30s

# ============================================================
# METRICS (for monitoring)
# ============================================================
metrics.reporter.prometheus.factory.class: org.apache.flink.metrics.prometheus.PrometheusReporterFactory
metrics.reporter.prometheus.port: 9249

# ============================================================
# LOGGING
# ============================================================
env.log.dir: /var/log/flink
EOF

# Step 6: Create RocksDB directory
mkdir -p /data/flink-rocksdb
chown -R root:root /data/flink-rocksdb

# Step 7: Download Kafka connector
log_info "Downloading Kafka connector..."
cd /opt/flink/lib
wget https://repo1.maven.org/maven2/org/apache/flink/flink-sql-connector-kafka/3.0.2-1.18/flink-sql-connector-kafka-3.0.2-1.18.jar

# Step 8: Install Python for PyFlink
log_info "Installing Python for PyFlink..."
apt-get install -y python3 python3-pip python3-venv

# Create virtual environment
python3 -m venv /opt/flink/python-env
source /opt/flink/python-env/bin/activate
pip install --upgrade pip
pip install apache-flink==1.18.1
pip install redis psycopg2-binary neo4j kafka-python
deactivate

# Step 9: Create systemd service for JobManager
log_info "Creating Flink systemd services..."
cat > /etc/systemd/system/flink-jobmanager.service << 'EOF'
[Unit]
Description=Apache Flink JobManager
After=network.target

[Service]
Type=forking
User=root
ExecStart=/opt/flink/bin/jobmanager.sh start
ExecStop=/opt/flink/bin/jobmanager.sh stop
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

# Create systemd service for TaskManager
cat > /etc/systemd/system/flink-taskmanager.service << 'EOF'
[Unit]
Description=Apache Flink TaskManager
After=network.target flink-jobmanager.service

[Service]
Type=forking
User=root
ExecStart=/opt/flink/bin/taskmanager.sh start
ExecStop=/opt/flink/bin/taskmanager.sh stop
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

# Step 10: Enable and start services
log_info "Starting Flink services..."
systemctl daemon-reload
systemctl enable flink-jobmanager
systemctl enable flink-taskmanager
systemctl start flink-jobmanager
sleep 5
systemctl start flink-taskmanager

# Wait for startup
log_info "Waiting for Flink to start..."
sleep 10

# Step 11: Verify installation
log_info "Verifying Flink installation..."
if curl -s http://localhost:8081/overview > /dev/null; then
    log_info "Flink is running!"
    curl -s http://localhost:8081/overview | python3 -m json.tool
else
    log_warn "Flink REST API not responding yet (may need more time)"
fi

echo ""
echo "=========================================="
echo "Flink Setup Complete!"
echo "=========================================="
echo ""
echo "Useful commands:"
echo "  /opt/flink/bin/flink list              - List running jobs"
echo "  /opt/flink/bin/flink run <jar>         - Submit a job"
echo "  systemctl status flink-jobmanager      - Check JobManager"
echo "  systemctl status flink-taskmanager     - Check TaskManager"
echo ""
echo "Web UI (via SSH tunnel):"
echo "  ssh -L 8081:localhost:8081 <user>@<server>"
echo "  Open: http://localhost:8081"
echo ""
