#!/bin/bash
# HIMARI Opus1 - Redpanda Authentication Setup
# Creates SASL users and ACLs

set -e

echo "=========================================="
echo "HIMARI Opus1 - Authentication Setup"
echo "=========================================="

# Configuration - UPDATE THESE PASSWORDS!
PRODUCER_PASSWORD="${PRODUCER_PASSWORD:-$(openssl rand -base64 24)}"
CONSUMER_PASSWORD="${CONSUMER_PASSWORD:-$(openssl rand -base64 24)}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

# Create producer user
log_info "Creating himari-producer user..."
rpk acl user create himari-producer \
    --password "$PRODUCER_PASSWORD" \
    --mechanism SCRAM-SHA-256

# Create consumer user
log_info "Creating himari-consumer user..."
rpk acl user create himari-consumer \
    --password "$CONSUMER_PASSWORD" \
    --mechanism SCRAM-SHA-256

# Grant producer permissions
log_info "Granting producer permissions..."
rpk acl create --allow-principal User:himari-producer \
    --operation write --topic '*'

rpk acl create --allow-principal User:himari-producer \
    --operation describe --topic '*'

# Grant consumer permissions
log_info "Granting consumer permissions..."
rpk acl create --allow-principal User:himari-consumer \
    --operation read --topic '*' --group '*'

rpk acl create --allow-principal User:himari-consumer \
    --operation describe --topic '*'

# List users
log_info "Listing SASL users..."
rpk acl user list

# List ACLs
log_info "Listing ACLs..."
rpk acl list

echo ""
echo "=========================================="
echo "Authentication Setup Complete!"
echo "=========================================="
echo ""
log_warn "SAVE THESE CREDENTIALS SECURELY!"
echo ""
echo "Producer Credentials:"
echo "  Username: himari-producer"
echo "  Password: $PRODUCER_PASSWORD"
echo ""
echo "Consumer Credentials:"
echo "  Username: himari-consumer"
echo "  Password: $CONSUMER_PASSWORD"
echo ""
echo "Test connection:"
echo "  rpk topic produce raw_market_data \\"
echo "    --brokers localhost:9093 \\"
echo "    --sasl-mechanism SCRAM-SHA-256 \\"
echo "    --user himari-producer \\"
echo "    --password '<password>'"
echo ""
