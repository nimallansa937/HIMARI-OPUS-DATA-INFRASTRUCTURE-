#!/bin/bash
# HIMARI Opus1 - Security Hardening
# Firewall, secrets management, TLS, and SSH hardening

set -e

echo "=========================================="
echo "HIMARI Opus1 - Security Hardening"
echo "=========================================="

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    log_error "Please run as root"
    exit 1
fi

# Configuration
PRIVATE_NETWORK="${PRIVATE_NETWORK:-10.0.0.0/24}"

echo ""
log_info "Step 1: Configuring UFW Firewall..."
echo "=========================================="

# Install UFW
apt-get install -y ufw

# Default policies
ufw default deny incoming
ufw default allow outgoing

# Allow SSH (with rate limiting)
ufw limit ssh

# Allow internal cluster communication (replace with your private IPs)
ufw allow from $PRIVATE_NETWORK to any port 9092 comment 'Kafka/Redpanda'
ufw allow from $PRIVATE_NETWORK to any port 9093 comment 'Kafka/Redpanda SASL'
ufw allow from $PRIVATE_NETWORK to any port 6123 comment 'Flink RPC'
ufw allow from $PRIVATE_NETWORK to any port 5432 comment 'PostgreSQL'
ufw allow from $PRIVATE_NETWORK to any port 7687 comment 'Neo4j Bolt'

# Enable firewall (non-interactive)
echo "y" | ufw enable

# Show status
ufw status verbose

echo ""
log_info "Step 2: Installing SOPS for Secrets Management..."
echo "=========================================="

# Install SOPS
wget https://github.com/getsops/sops/releases/download/v3.8.1/sops-v3.8.1.linux.amd64 -O /usr/local/bin/sops
chmod +x /usr/local/bin/sops

# Install age for encryption
apt-get install -y age

# Generate age key pair
mkdir -p /root/.config/sops/age
if [ ! -f /root/.config/sops/age/keys.txt ]; then
    age-keygen -o /root/.config/sops/age/keys.txt
    log_info "Age key pair generated"
else
    log_warn "Age key already exists, skipping"
fi

# Create secrets template
mkdir -p /opt/himari/secrets
cat > /opt/himari/secrets/secrets.yaml << 'EOF'
# HIMARI Opus1 - Secrets Configuration
# Encrypt with: sops -e -i secrets.yaml
# Decrypt with: sops -d secrets.yaml

kafka:
  user: himari-producer
  password: CHANGE_ME_PRODUCER_PASSWORD

redis:
  password: CHANGE_ME_REDIS_PASSWORD

postgres:
  user: himari
  password: CHANGE_ME_POSTGRES_PASSWORD

neo4j:
  user: neo4j
  password: CHANGE_ME_NEO4J_PASSWORD

grafana_cloud:
  user_id: ""
  api_key: ""
EOF

log_warn "Update /opt/himari/secrets/secrets.yaml with real passwords"
log_info "Then encrypt with: SOPS_AGE_RECIPIENTS=\$(age-keygen -y /root/.config/sops/age/keys.txt) sops -e -i /opt/himari/secrets/secrets.yaml"

echo ""
log_info "Step 3: Generating TLS Certificates..."
echo "=========================================="

# Create certificates directory
mkdir -p /opt/himari/certs
cd /opt/himari/certs

# Generate CA
openssl genrsa -out ca.key 4096
openssl req -new -x509 -days 3650 -key ca.key -out ca.crt \
    -subj "/CN=HIMARI Internal CA"

# Generate server certificate
openssl genrsa -out server.key 2048
openssl req -new -key server.key -out server.csr \
    -subj "/CN=himari-cluster"

# Sign with CA
openssl x509 -req -days 365 -in server.csr -CA ca.crt -CAkey ca.key \
    -CAcreateserial -out server.crt

# Set permissions
chmod 600 *.key
chmod 644 *.crt

log_info "TLS certificates generated in /opt/himari/certs/"

echo ""
log_info "Step 4: Hardening SSH Configuration..."
echo "=========================================="

# Backup original sshd_config
cp /etc/ssh/sshd_config /etc/ssh/sshd_config.backup

# Apply hardening
cat >> /etc/ssh/sshd_config << 'EOF'

# HIMARI Security Hardening
# Disable password authentication
PasswordAuthentication no
ChallengeResponseAuthentication no

# Disable root login
PermitRootLogin prohibit-password

# Use strong ciphers only
Ciphers aes256-gcm@openssh.com,chacha20-poly1305@openssh.com
MACs hmac-sha2-512-etm@openssh.com,hmac-sha2-256-etm@openssh.com

# Idle timeout
ClientAliveInterval 300
ClientAliveCountMax 2

# Limit login attempts
MaxAuthTries 3
EOF

# Test configuration before restart
if sshd -t; then
    log_info "SSH configuration valid, restarting..."
    systemctl restart sshd
else
    log_error "SSH configuration invalid, restoring backup"
    cp /etc/ssh/sshd_config.backup /etc/ssh/sshd_config
fi

echo ""
log_info "Step 5: Setting up fail2ban..."
echo "=========================================="

apt-get install -y fail2ban

cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
EOF

systemctl enable fail2ban
systemctl restart fail2ban

echo ""
echo "=========================================="
echo "Security Hardening Complete!"
echo "=========================================="
echo ""
echo "Summary:"
echo "  ✓ UFW firewall configured"
echo "  ✓ SOPS installed for secrets management"
echo "  ✓ TLS certificates generated"
echo "  ✓ SSH hardened"
echo "  ✓ fail2ban installed"
echo ""
log_warn "IMPORTANT: Make sure you have SSH key access before logging out!"
echo ""
echo "Next steps:"
echo "  1. Update /opt/himari/secrets/secrets.yaml with real passwords"
echo "  2. Encrypt secrets: sops -e -i /opt/himari/secrets/secrets.yaml"
echo "  3. Test SSH access from another terminal before disconnecting"
echo ""
