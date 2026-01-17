#!/bin/bash
# HIMARI Opus1 - Redpanda Topic Configuration
# Creates required topics with production settings

set -e

echo "=========================================="
echo "HIMARI Opus1 - Topic Configuration"
echo "=========================================="

# Colors
GREEN='\033[0;32m'
NC='\033[0m'
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }

# Create raw_market_data topic (12 partitions for high throughput)
log_info "Creating raw_market_data topic..."
rpk topic create raw_market_data \
    --partitions 12 \
    --config retention.ms=604800000 \
    --config compression.type=snappy \
    --config cleanup.policy=delete

# Create quality_scores topic (6 partitions)
log_info "Creating quality_scores topic..."
rpk topic create quality_scores \
    --partitions 6 \
    --config retention.ms=1209600000 \
    --config compression.type=snappy

# Create causal_events topic (3 partitions - lower volume)
log_info "Creating causal_events topic..."
rpk topic create causal_events \
    --partitions 3 \
    --config retention.ms=2592000000 \
    --config compression.type=snappy

# Create features_computed topic (6 partitions)
log_info "Creating features_computed topic..."
rpk topic create features_computed \
    --partitions 6 \
    --config retention.ms=7776000000 \
    --config compression.type=snappy

# List all topics
log_info "Listing all topics..."
rpk topic list

echo ""
echo "=========================================="
echo "Topic Configuration Complete!"
echo "=========================================="
echo ""
echo "Topic Summary:"
echo "┌─────────────────────┬────────────┬───────────┐"
echo "│ Topic               │ Partitions │ Retention │"
echo "├─────────────────────┼────────────┼───────────┤"
echo "│ raw_market_data     │ 12         │ 7 days    │"
echo "│ quality_scores      │ 6          │ 14 days   │"
echo "│ causal_events       │ 3          │ 30 days   │"
echo "│ features_computed   │ 6          │ 90 days   │"
echo "└─────────────────────┴────────────┴───────────┘"
echo ""
