# HIMARI OPUS - Modified Port Mappings

This deployment has been configured to run alongside your existing services without port conflicts.

## Modified Ports

| Service | Original Port | New Port | Access URL |
|---------|--------------|----------|------------|
| **Redpanda Kafka** | 19092 | 19092 | localhost:19092 (unchanged) |
| **Redpanda Console** | 8080 | 8081 | http://localhost:8081 |
| **Redis** | 6379 | 6381 | localhost:6381 |
| **TimescaleDB** | 5432 | 5433 | localhost:5433 |
| **Neo4j Browser** | 7474 | 7475 | http://localhost:7475 |
| **Neo4j Bolt** | 7687 | 7688 | bolt://localhost:7688 |
| **Prometheus** | 9090 | 9091 | http://localhost:9091 |
| **Grafana** | 3000 | 3002 | http://localhost:3002 |

## Container Names

To avoid conflicts, container names have been updated:
- `himari-redis` → `himari-opus-redis`
- `himari-timescale` → `himari-opus-timescale`
- `himari-neo4j` → `himari-opus-neo4j`
- `himari-prometheus` → `himari-opus-prometheus`
- `himari-grafana` → `himari-opus-grafana`

## Network & Volumes

- Network: `himari-opus-network` (separate from existing)
- Volumes: All prefixed with `himari-opus-*`

## Deployment Instructions

1. Navigate to the project directory:
```bash
cd "C:\Users\chari\OneDrive\Documents\HIMARI OPUS 2\Layer 0 Data infrastructure\HIMARI-OPUS-DATA-INFRASTRUCTURE--main"
```

2. Copy the environment template:
```bash
copy .env.example .env
```

3. Start all services:
```bash
docker-compose up -d
```

4. Check service status:
```bash
docker-compose ps
```

5. View logs:
```bash
docker-compose logs -f
```

## Connection Strings

When configuring your applications, use these updated connection strings:

**Redis:**
```
redis://localhost:6381
```

**TimescaleDB:**
```
postgresql://himari:himari-dev-password@localhost:5433/himari_analytics
```

**Neo4j:**
```
bolt://localhost:7688
User: neo4j
Password: himari-dev-password
```

**Redpanda (Kafka):**
```
localhost:19092
```

## Stopping Services

```bash
docker-compose down
```

To remove volumes as well:
```bash
docker-compose down -v
```
