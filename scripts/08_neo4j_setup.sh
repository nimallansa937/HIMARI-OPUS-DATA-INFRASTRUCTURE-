#!/bin/bash
# HIMARI Opus1 - Neo4j Knowledge Graph Setup
# Deploys Neo4j via Docker on the Flink server

set -e

echo "=========================================="
echo "HIMARI Opus1 - Neo4j Knowledge Graph Setup"
echo "=========================================="

# Configuration - UPDATE THIS PASSWORD!
NEO4J_PASSWORD="${NEO4J_PASSWORD:-$(openssl rand -base64 16)}"

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

# Step 1: Install Docker if not present
if ! command -v docker &> /dev/null; then
    log_info "Installing Docker..."
    apt-get update
    apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release
    
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
    
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
        tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io
    
    systemctl enable docker
    systemctl start docker
else
    log_info "Docker already installed"
fi

# Step 2: Create Neo4j data directories
log_info "Creating Neo4j directories..."
mkdir -p /data/neo4j/data
mkdir -p /data/neo4j/logs
mkdir -p /data/neo4j/import
mkdir -p /data/neo4j/plugins
mkdir -p /data/neo4j/backups

# Step 3: Pull and run Neo4j container
log_info "Starting Neo4j container..."
docker pull neo4j:5-community

# Stop existing container if any
docker stop neo4j-himari 2>/dev/null || true
docker rm neo4j-himari 2>/dev/null || true

# Run Neo4j with optimized settings
docker run -d \
    --name neo4j-himari \
    --restart unless-stopped \
    -p 127.0.0.1:7474:7474 \
    -p 127.0.0.1:7687:7687 \
    -v /data/neo4j/data:/data \
    -v /data/neo4j/logs:/logs \
    -v /data/neo4j/import:/var/lib/neo4j/import \
    -v /data/neo4j/plugins:/plugins \
    -v /data/neo4j/backups:/backups \
    -e NEO4J_AUTH=neo4j/${NEO4J_PASSWORD} \
    -e NEO4J_server_memory_heap_initial__size=1G \
    -e NEO4J_server_memory_heap_max__size=2G \
    -e NEO4J_server_memory_pagecache_size=1G \
    -e NEO4J_PLUGINS='["apoc"]' \
    neo4j:5-community

# Wait for startup
log_info "Waiting for Neo4j to start..."
sleep 30

# Step 4: Verify Neo4j is running
log_info "Verifying Neo4j..."
if docker exec neo4j-himari cypher-shell -u neo4j -p "$NEO4J_PASSWORD" "RETURN 1" > /dev/null 2>&1; then
    log_info "Neo4j is running and accessible!"
else
    log_warn "Neo4j may still be starting up. Wait a moment and try again."
fi

echo ""
echo "=========================================="
echo "Neo4j Setup Complete!"
echo "=========================================="
echo ""
log_warn "SAVE THIS PASSWORD SECURELY!"
echo ""
echo "Neo4j Credentials:"
echo "  Username: neo4j"
echo "  Password: $NEO4J_PASSWORD"
echo ""
echo "Connection info:"
echo "  Bolt: bolt://localhost:7687"
echo "  HTTP: http://localhost:7474 (via SSH tunnel)"
echo ""
echo "Access Web UI (via SSH tunnel):"
echo "  ssh -L 7474:localhost:7474 -L 7687:localhost:7687 <user>@<server>"
echo "  Open: http://localhost:7474"
echo ""
echo "Next step: Run the graph schema initialization"
echo "  docker exec -i neo4j-himari cypher-shell -u neo4j -p '<password>' < neo4j/graph_schema.cypher"
echo ""
