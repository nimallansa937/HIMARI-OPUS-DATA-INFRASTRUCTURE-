#!/bin/bash
# Quick Redpanda fix
systemctl stop redpanda
rm -rf /var/lib/redpanda/data/*
cat > /etc/redpanda/redpanda.yaml << 'EOF'
redpanda:
  data_directory: /var/lib/redpanda/data
  node_id: 0
  seed_servers: []
  rpc_server:
    address: 0.0.0.0
    port: 33145
  kafka_api:
    - address: 0.0.0.0
      port: 9092
  admin:
    - address: 0.0.0.0
      port: 9644
  developer_mode: true
rpk:
  overprovisioned: true
EOF
systemctl start redpanda
sleep 10
rpk cluster info
rpk topic create raw_market_data --partitions 6
rpk topic create quality_scores --partitions 3
rpk topic list
