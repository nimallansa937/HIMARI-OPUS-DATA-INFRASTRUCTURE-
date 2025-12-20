# HIMARI OPUS 2 - Complete TODO List

**Status**: Phase 1 - MVP (Months 1-2)  
**Based on**: OPUS 1 Infrastructure + Market Data API Research  
**Cost Estimate**: $0-350/month (MVP to Production)  

---

## 🎯 OPUS 2 OBJECTIVES

### Primary Goals
- [ ] Extend OPUS 1 infrastructure for **L2/L3 market data ingestion**
- [ ] Implement **HIFA 4-stage framework** with real market data
- [ ] Build **backtesting system** with historical order book data
- [ ] Create **production trading pipeline** with live feeds
- [ ] Achieve **<100ms latency** for HIFA decision making

### Architecture Overview
```
FREE L2 Sources → Redpanda (Buffer) → Flink (HIFA Engine) 
→ Redis (Real-time) / TimescaleDB (Historical) → Trading Signals
```

---

## PHASE 1: DATA INGESTION (Weeks 1-4)

### 1.1 WebSocket Connectors - FREE Data Sources

#### Binance L2 Connector
- [ ] Create `src/connectors/binance_ws_connector.py`
  - [ ] Implement WebSocket connection to `wss://stream.binance.com:9443/ws/`
  - [ ] Parse depth update messages (`depthUpdate` events)
  - [ ] Extract bid/ask levels (configurable: 5, 10, 20, 100, 500)
  - [ ] Handle connection reconnection logic
  - [ ] Support multiple trading pairs (BTC/USDT, ETH/USDT, etc.)
  - [ ] Emit to Redpanda topic: `binance_l2_raw`
  - [ ] Test with 1000+ pairs simultaneously
  
- [ ] Create test file: `tests/test_binance_connector.py`
  - [ ] Mock WebSocket messages
  - [ ] Verify bid/ask extraction
  - [ ] Test reconnection scenarios

#### Coinbase L2+L3 Connector  
- [ ] Create `src/connectors/coinbase_ws_connector.py`
  - [ ] Implement Coinbase WebSocket protocol
  - [ ] Subscribe to `level2` channel (L2 data)
  - [ ] Subscribe to `full` channel (L3 order IDs)
  - [ ] Extract bid/ask changes from `l2update` messages
  - [ ] Track order IDs from `done` events (L3)
  - [ ] Support snapshot + incremental updates
  - [ ] Emit to Redpanda topics:
    - [ ] `coinbase_l2_raw` (Level 2)
    - [ ] `coinbase_l3_raw` (Level 3 with order IDs)

- [ ] Create test file: `tests/test_coinbase_connector.py`
  - [ ] Verify L2 and L3 message parsing
  - [ ] Test order book reconstruction

#### Kraken L2 Connector
- [ ] Create `src/connectors/kraken_ws_connector.py`
  - [ ] Implement Kraken WebSocket subscription
  - [ ] Subscribe to `book` channel with depth (5, 10, 25, 125)
  - [ ] Parse spread + book updates
  - [ ] Handle multiple currency pairs
  - [ ] Emit to Redpanda topic: `kraken_l2_raw`

#### Multi-Exchange Aggregator
- [ ] Create `src/connectors/multi_exchange_aggregator.py`
  - [ ] Orchestrate all three connectors
  - [ ] Unified message format for all exchanges
  - [ ] Error handling and circuit breakers
  - [ ] Logging and monitoring hooks

### 1.2 Redpanda Topic Setup

- [ ] Create Redpanda topic structure
  - [ ] Topic: `binance_l2_raw` (1000 partitions by symbol)
  - [ ] Topic: `coinbase_l2_raw` (200 partitions)
  - [ ] Topic: `coinbase_l3_raw` (200 partitions)
  - [ ] Topic: `kraken_l2_raw` (100 partitions)
  - [ ] Topic: `market_data_normalized` (1000 partitions)
  - [ ] Retention: 7 days for raw, 30 days for normalized
  - [ ] Replication factor: 3 (production)

- [ ] Update `docker-compose.yml` for Redpanda
  - [ ] Increase broker count to 3 nodes (prod config)
  - [ ] Configure tiered storage (optional)
  - [ ] Update `docker-compose.prod.yml`

### 1.3 Data Quality Validation (OPUS 1 Enhancement)

- [ ] Extend `src/flink/flink_quality_pipeline.py`
  - [ ] Add L2/L3 specific validators:
    - [ ] Bid < Ask check
    - [ ] Spread sanity checks (MAX_SPREAD threshold per pair)
    - [ ] Volume consistency checks
    - [ ] Duplicate order ID detection (L3)
    - [ ] Timestamp monotonicity
    - [ ] Exchange-specific anomalies
  - [ ] Create quality score metric (0-100)
  - [ ] Emit to `quality_scores` topic
  - [ ] Track by exchange and symbol

- [ ] Create validation rules file: `config/validation_rules.yaml`
  - [ ] MAX_SPREAD thresholds by pair
  - [ ] MAX_VOLUME thresholds
  - [ ] MIN_CONFIDENCE levels
  - [ ] TIMEOUT settings per exchange

---

## PHASE 2: HIFA ENGINE INTEGRATION (Weeks 5-8)

### 2.1 Normalize Market Data

- [ ] Create `src/flink/normalizer.py`
  - [ ] Convert all exchanges to unified format:
    ```json
    {
      "timestamp": 1234567890000,
      "exchange": "binance",
      "symbol": "BTC/USDT",
      "bids": [["price", "quantity"], ...],
      "asks": [["price", "quantity"], ...],
      "sequence": 12345678,
      "quality_score": 95,
      "l3_data": {
        "order_ids": {"bid": [...], "ask": [...]}
      }
    }
    ```
  - [ ] Standardize symbol naming (e.g., BTC/USDT, BTCUSDT → unified)
  - [ ] Handle precision normalization
  - [ ] Emit to `market_data_normalized` topic

### 2.2 HIFA Stage 1: Signal Detection

- [ ] Create `src/flink/hifa_stage1.py` - Pattern Recognition
  - [ ] Implement order book imbalance detection
  - [ ] Detect large bid/ask walls
  - [ ] Identify rapid micro-moves
  - [ ] Track volume imbalance ratio
  - [ ] Output: `hifa_stage1_signals` topic
  - [ ] Latency target: <50ms

- [ ] Test with synthetic scenarios
  - [ ] Create `tests/test_hifa_stage1.py`
  - [ ] Simulate various order book patterns
  - [ ] Verify signal detection accuracy

### 2.3 HIFA Stage 2: Context Analysis

- [ ] Create `src/flink/hifa_stage2.py` - Multi-timeframe Analysis
  - [ ] Correlate signals across exchanges
  - [ ] Track 1s, 5s, 15s windows
  - [ ] Calculate order flow indicators
  - [ ] Detect execution patterns
  - [ ] Output: `hifa_stage2_context` topic
  - [ ] Latency target: <100ms

### 2.4 HIFA Stage 3: Risk Assessment

- [ ] Create `src/flink/hifa_stage3.py` - Risk Scoring
  - [ ] Calculate position risk
  - [ ] Assess liquidity risk
  - [ ] Evaluate counterparty risk (exchange health)
  - [ ] Estimate slippage
  - [ ] Output: `hifa_stage3_risk` topic with risk score

### 2.5 HIFA Stage 4: Execution Optimization

- [ ] Create `src/flink/hifa_stage4.py` - Optimal Execution
  - [ ] Route orders (best exchange for pair)
  - [ ] Order sizing based on available liquidity
  - [ ] Split order logic (TWAP/VWAP if needed)
  - [ ] Execute on optimal exchange
  - [ ] Output: `trading_signals_final` topic
  - [ ] Latency target: <150ms end-to-end

- [ ] Create `src/execution/order_router.py`
  - [ ] Implement exchange routing logic
  - [ ] Track execution quality metrics
  - [ ] Logging for audit trail

---

## PHASE 3: BACKTESTING SYSTEM (Weeks 9-12)

### 3.1 Historical Data Collection (Cost: $200-250/mo with Tardis.dev)

- [ ] Integrate Tardis.dev API
  - [ ] Create `src/backtest/tardis_connector.py`
  - [ ] Download L2 historical data for:
    - [ ] Binance SPOT (BTC/USDT, ETH/USDT, top 10 pairs)
    - [ ] Coinbase (BTC-USD, ETH-USD)
    - [ ] Kraken (XBT/USD, ETH/USD)
  - [ ] Date range: Last 6-12 months
  - [ ] Store in S3 or local disk: `data/historical/tardis/<exchange>/<symbol>/<date>.parquet`

- [ ] Create Tardis.dev client wrapper
  - [ ] Handle API rate limits
  - [ ] Batch download logic
  - [ ] Data validation on receipt
  - [ ] Cost estimation tool

### 3.2 Backtest Engine

- [ ] Create `src/backtest/backtest_engine.py`
  - [ ] Load historical L2 data from Parquet
  - [ ] Replay order book updates
  - [ ] Simulate HIFA 4-stage pipeline
  - [ ] Calculate PnL metrics:
    - [ ] Total return
    - [ ] Sharpe ratio
    - [ ] Max drawdown
    - [ ] Win rate
    - [ ] Avg trade duration
  - [ ] Support Monte Carlo sampling

- [ ] Create `src/backtest/performance_analyzer.py`
  - [ ] Generate detailed statistics
  - [ ] Create visualization plots (matplotlib/plotly)
  - [ ] Export reports to CSV/PDF

### 3.3 Backtesting Configuration

- [ ] Create `config/backtest_scenarios.yaml`
  - [ ] Define test parameters:
    - [ ] Symbol list
    - [ ] Date ranges
    - [ ] Initial capital
    - [ ] Max position size
    - [ ] Risk per trade
  - [ ] Pre-configured scenarios:
    - [ ] "Conservative" (low risk, 1% per trade)
    - [ ] "Aggressive" (high risk, 5% per trade)
    - [ ] "Balanced" (3% per trade)

- [ ] Create backtesting CLI
  - [ ] Command: `python -m backtest --scenario conservative --symbol BTC/USDT`
  - [ ] Output: Results folder with plots and metrics

### 3.4 Walk-Forward Analysis

- [ ] Implement `src/backtest/walk_forward_analysis.py`
  - [ ] Split data: 60% train / 40% test
  - [ ] Retrain parameters monthly
  - [ ] Track parameter drift
  - [ ] Generate out-of-sample statistics

---

## PHASE 4: PRODUCTION SETUP (Weeks 13-16)

### 4.1 Real-time Monitoring Dashboard

- [ ] Create Prometheus metrics
  - [ ] Update `prometheus/prometheus.yml`
  - [ ] Add metrics:
    - [ ] `market_data_latency_ms` (by exchange)
    - [ ] `hifa_stage_latency_ms` (by stage)
    - [ ] `signal_count_total` (by type)
    - [ ] `execution_count_total` (by exchange)
    - [ ] `order_book_quality_score` (by symbol)
  - [ ] Scrape interval: 10s

- [ ] Create Grafana dashboard
  - [ ] Real-time data flow visualization
  - [ ] HIFA stage latencies
  - [ ] Signal generation rate
  - [ ] Exchange connectivity status
  - [ ] Error rate by component

### 4.2 Alerting System

- [ ] Set up alert rules `prometheus/alerts.yml`
  - [ ] Alert: Exchange connection down (>30s)
  - [ ] Alert: Data quality score <50
  - [ ] Alert: HIFA latency >200ms
  - [ ] Alert: Execution failure rate >5%
  - [ ] Alert: Disk space <10%

- [ ] Integration with notification channels
  - [ ] Slack notifications
  - [ ] Email alerts for critical issues
  - [ ] PagerDuty for on-call (optional)

### 4.3 Audit Logging

- [ ] Enhance logging system
  - [ ] Create `src/logging/audit_logger.py`
  - [ ] Log all trades to `logs/audit_trail/`
  - [ ] Include: timestamp, symbol, price, size, exchange, outcome
  - [ ] Immutable log format (append-only)
  - [ ] Retention: 1 year minimum

### 4.4 Production Deployment

- [ ] Update `docker-compose.prod.yml`
  - [ ] 3-node Redpanda cluster
  - [ ] 2+ Flink taskmanagers
  - [ ] Redis cluster with sentinel
  - [ ] TimescaleDB replication
  - [ ] Neo4j cluster (optional)
  - [ ] Prometheus + Grafana
  - [ ] ELK Stack for logging (optional)

- [ ] Create Kubernetes manifests (optional for cloud)
  - [ ] `k8s/namespace.yaml`
  - [ ] `k8s/redpanda-statefulset.yaml`
  - [ ] `k8s/flink-deployment.yaml`
  - [ ] `k8s/redis-deployment.yaml`
  - [ ] `k8s/prometheus-deployment.yaml`

### 4.5 Failover & High Availability

- [ ] Implement automatic failover
  - [ ] Redis Sentinel setup
  - [ ] Flink job state recovery
  - [ ] Redpanda cluster rebalancing
  - [ ] Database replication

- [ ] Create disaster recovery plan
  - [ ] Document in `docs/DISASTER_RECOVERY.md`
  - [ ] Backup strategies
  - [ ] Recovery time objectives (RTO)
  - [ ] Recovery point objectives (RPO)

---

## COST BREAKDOWN

### Phase 1-3 Costs (MVP + Backtesting)
| Component | Cost | Duration | Total |
|-----------|------|----------|-------|
| Binance L2 | $0 | Free | $0 |
| Coinbase L2/L3 | $0 | Free | $0 |
| Kraken L2 | $0 | Free | $0 |
| Tardis.dev | $250/mo | 3 months | $750 |
| AWS S3 | $50/mo | 3 months | $150 |
| **Total** | - | - | **$900** |

### Phase 4-6 Costs (Production)
| Component | Cost | Duration | Total |
|-----------|------|----------|-------|
| Data sources | $250/mo | Ongoing | $250/mo |
| Infrastructure | $200/mo | Ongoing | $200/mo |
| Monitoring | $50/mo | Ongoing | $50/mo |
| **Total Monthly** | - | - | **$500/mo** |

---

## SUCCESS METRICS

### Performance KPIs
- [ ] Data ingestion latency: <50ms
- [ ] HIFA pipeline latency: <150ms
- [ ] Signal accuracy: >70%
- [ ] System uptime: >99.9%
- [ ] Data quality: >90%

### Business KPIs
- [ ] Backtest Sharpe: >1.5
- [ ] Win rate: >55%
- [ ] Max drawdown: <15%

---

**Version**: 1.0  
**Status**: Ready for Phase 1 kickoff
