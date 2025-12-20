# HIMARI Opus 1 Data Infrastructure

**Production-grade crypto cascade defense data layer at $50/month.**

A real-time market data processing system designed for cryptocurrency trading, featuring quality validation, feature computation, and multi-store persistence.

---

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.10+
- 8GB RAM minimum

### 5-Minute Setup

```bash
# 1. Clone the repository
git clone https://github.com/nimallansa937/HIMARI-OPUS-DATA-INFRASTRUCTURE-.git
cd HIMARI-OPUS-DATA-INFRASTRUCTURE-

# 2. Copy environment template
cp .env.example .env
# Edit .env with your passwords

# 3. Start all services
docker-compose up -d

# 4. Install Python dependencies
pip install -r requirements.txt

# 5. Initialize database schema
psql -h localhost -U himari -d himari_analytics -f sql/schema.sql

# 6. Initialize Neo4j graph
cypher-shell -u neo4j -p your-password < neo4j/graph_schema.cypher

# 7. Run the pipeline
python src/flink/flink_quality_pipeline.py
```

---

## 📐 Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Data Sources                                 │
│    Binance • Kraken • Bybit • Deribit • Coinbase WebSockets         │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Redpanda (Kafka)                                 │
│              raw_market_data → quality_scores                        │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Apache Flink Pipeline                             │
│   ┌──────────────┐  ┌────────────────────┐  ┌──────────────────┐    │
│   │ Parse JSON   │→ │ Quality Validation │→ │ Feature Compute  │    │
│   │              │  │   (30+ checks)     │  │                  │    │
│   └──────────────┘  └────────────────────┘  └────────┬─────────┘    │
└──────────────────────────────────────────────────────┼──────────────┘
                                                       │
                 ┌─────────────────┬───────────────────┼───────────────┐
                 │                 │                   │               │
                 ▼                 ▼                   ▼               ▼
          ┌───────────┐     ┌───────────┐      ┌───────────┐    ┌───────────┐
          │   Redis   │     │TimescaleDB│      │   Neo4j   │    │Prometheus │
          │  (Online) │     │  (Warm)   │      │  (Graph)  │    │(Metrics)  │
          │  <10ms    │     │ Analytics │      │  Causal   │    │           │
          └───────────┘     └───────────┘      └───────────┘    └───────────┘
```

---

## 📁 Project Structure

```
HIMARI OPUS/
├── src/flink/                    # Stream processing pipelines
│   ├── flink_quality_pipeline.py # Main quality validation (30+ checks)
│   ├── redis_sink.py             # Feature store writer
│   ├── timescale_sink.py         # Analytics store writer
│   └── neo4j_sink.py             # Causal event graph writer
├── scripts/                      # Deployment automation
│   ├── 01_redpanda_setup.sh     # Kafka alternative setup
│   ├── 05_redis_setup.sh        # Feature store setup
│   ├── 06_timescale_setup.sh    # Analytics DB setup
│   ├── 08_neo4j_setup.sh        # Graph DB setup
│   └── ...
├── sql/schema.sql               # TimescaleDB hypertables
├── neo4j/graph_schema.cypher    # Knowledge graph schema
├── prometheus/                   # Monitoring configuration
├── tests/                        # Test suite
│   ├── test_integration.py      # Full system tests
│   └── test_quality_validation.py # Unit tests
├── docker-compose.yml           # One-command local deployment
├── requirements.txt             # Python dependencies
└── HIMARI_Opus1_Production_Infrastructure_Guide.pdf  # Full 42-page guide
```

---

## 🧩 Components

| Component | Purpose | Port | SLA |
|-----------|---------|------|-----|
| **Redpanda** | Message broker (Kafka replacement) | 9092 | <5ms latency |
| **Apache Flink** | Stream processing | 8081 | 30+ quality checks |
| **Redis** | Online feature store | 6379 | <10ms serving |
| **TimescaleDB** | Warm analytics store | 5432 | 5min OHLCV aggregates |
| **Neo4j** | Causal event graph | 7687 | Cascade detection |
| **Prometheus** | Metrics & monitoring | 9090 | Real-time dashboards |

---

## 🔍 Quality Validation Checks

The pipeline validates market data with 30+ quality checks:

| Category | Checks |
|----------|--------|
| **Schema** | Positive price, non-negative volume, valid exchange |
| **Temporal** | Ordering, duplicates, gap detection |
| **Statistical** | Price deviation, EMA anomalies, volume spikes |
| **Precision** | Decimal precision limits |
| **Freshness** | Latency, stale data, future timestamps |

Quality scores range from 0.0 (bad) to 1.0 (perfect).

---

## 🛠️ Development

### Running Tests

```bash
# Unit tests (no infrastructure needed)
pytest tests/test_quality_validation.py -v

# Integration tests (requires Docker Compose)
docker-compose up -d
pytest tests/test_integration.py -v
```

### Adding New Exchange

1. Add exchange name to `VALID_EXCHANGES` in `flink_quality_pipeline.py`
2. Add exchange node to `neo4j/graph_schema.cypher`
3. Update integration tests

---

## 📊 Monitoring

Access dashboards at:

- **Prometheus**: <http://localhost:9090>
- **Neo4j Browser**: <http://localhost:7474>
- **Redpanda Console**: <http://localhost:8080>

---

## 💰 Cost Breakdown (Production)

| Resource | Hetzner Server | Monthly Cost |
|----------|----------------|--------------|
| Redpanda | CPX21 (4 vCPU, 8GB) | €10.60 |
| Flink | CPX41 (8 vCPU, 16GB) | €25.80 |
| TimescaleDB + Redis | CPX11 (2 vCPU, 4GB) | €5.90 |
| Neo4j | CPX11 (2 vCPU, 4GB) | €5.90 |
| **Total** | | **~€48/month** |

---

## 📚 Documentation

For detailed deployment instructions, see:

- [Production Infrastructure Guide (PDF)](./HIMARI_Opus1_Production_Infrastructure_Guide.pdf)
- [Production Infrastructure Guide (Markdown)](./HIMARI_Opus1_Production_Infrastructure_Guide.md)

---

## 📄 License

MIT License - see LICENSE file for details.

---

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Run tests: `pytest tests/ -v`
4. Submit a pull request

---

Built with ❤️ for crypto cascade defense
