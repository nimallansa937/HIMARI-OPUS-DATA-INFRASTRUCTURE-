#!/bin/bash
# HIMARI Opus1 - Automated Backup Script
# Run via cron every 6 hours: 0 */6 * * * /opt/himari/scripts/backup.sh

set -e

echo "=========================================="
echo "HIMARI Opus1 - Backup"
echo "$(date)"
echo "=========================================="

# Configuration
BACKUP_DIR="/data/backups/$(date +%Y%m%d_%H%M%S)"
S3_BUCKET="${S3_BUCKET:-s3://himari-backups}"
POSTGRES_USER="${POSTGRES_USER:-himari}"
POSTGRES_DB="${POSTGRES_DB:-himari_analytics}"
REDIS_PASSWORD="${REDIS_PASSWORD:-}"
RETENTION_DAYS=3

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Create backup directory
mkdir -p $BACKUP_DIR

# 1. Backup TimescaleDB
log_info "Backing up TimescaleDB..."
if pg_dump -h localhost -U $POSTGRES_USER -d $POSTGRES_DB \
    --format=custom --compress=9 \
    > $BACKUP_DIR/timescaledb.dump 2>/dev/null; then
    log_info "TimescaleDB backup complete: $(ls -lh $BACKUP_DIR/timescaledb.dump | awk '{print $5}')"
else
    log_error "TimescaleDB backup failed"
fi

# 2. Backup Redis (RDB snapshot)
log_info "Backing up Redis..."
if [ -n "$REDIS_PASSWORD" ]; then
    redis-cli -a "$REDIS_PASSWORD" BGSAVE 2>/dev/null
else
    redis-cli BGSAVE 2>/dev/null
fi
sleep 5  # Wait for snapshot
if cp /var/lib/redis/dump.rdb $BACKUP_DIR/redis.rdb 2>/dev/null; then
    log_info "Redis backup complete: $(ls -lh $BACKUP_DIR/redis.rdb | awk '{print $5}')"
else
    log_warn "Redis backup failed or not available"
fi

# 3. Backup Neo4j
log_info "Backing up Neo4j..."
if docker exec neo4j-himari neo4j-admin database dump neo4j \
    --to-path=/backups/ 2>/dev/null; then
    docker cp neo4j-himari:/backups/neo4j.dump $BACKUP_DIR/
    log_info "Neo4j backup complete"
else
    log_warn "Neo4j backup failed or not available"
fi

# 4. Backup configurations
log_info "Backing up configurations..."
tar -czf $BACKUP_DIR/configs.tar.gz \
    /opt/flink/conf/ \
    /etc/redpanda/ \
    /etc/redis/ \
    /opt/prometheus/ \
    /opt/himari/secrets/ \
    2>/dev/null || log_warn "Some config files may be missing"

log_info "Config backup complete: $(ls -lh $BACKUP_DIR/configs.tar.gz | awk '{print $5}')"

# 5. Backup Flink savepoints
log_info "Backing up Flink savepoints..."
if [ -d /data/flink-savepoints ] && [ "$(ls -A /data/flink-savepoints 2>/dev/null)" ]; then
    tar -czf $BACKUP_DIR/flink-savepoints.tar.gz /data/flink-savepoints/
    log_info "Flink savepoints backup complete"
else
    log_warn "No Flink savepoints to backup"
fi

# 6. Upload to S3 (if AWS CLI is configured)
if command -v aws &> /dev/null; then
    log_info "Uploading to S3..."
    if aws s3 sync $BACKUP_DIR $S3_BUCKET/$(basename $BACKUP_DIR)/ \
        --storage-class STANDARD_IA 2>/dev/null; then
        log_info "S3 upload complete"
    else
        log_warn "S3 upload failed"
    fi
else
    log_warn "AWS CLI not installed, skipping S3 upload"
fi

# 7. Cleanup old local backups
log_info "Cleaning up old backups..."
find /data/backups -type d -mtime +$RETENTION_DAYS -exec rm -rf {} + 2>/dev/null || true

# Summary
echo ""
echo "=========================================="
echo "Backup Complete!"
echo "=========================================="
echo ""
echo "Backup location: $BACKUP_DIR"
echo ""
ls -lh $BACKUP_DIR/
echo ""
echo "Total size: $(du -sh $BACKUP_DIR | cut -f1)"
echo ""
