-- HIMARI Opus1 - TimescaleDB Schema
-- Creates hypertables, continuous aggregates, and retention policies

-- Connect to database first:
-- psql -U himari -d himari_analytics

-- ============================================================
-- MARKET DATA HYPERTABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS market_data (
    timestamp       TIMESTAMPTZ NOT NULL,
    symbol          TEXT NOT NULL,
    exchange        TEXT NOT NULL,
    price           DOUBLE PRECISION NOT NULL,
    volume          DOUBLE PRECISION NOT NULL,
    quality_score   REAL NOT NULL,
    issues          TEXT[],
    
    -- Constraints
    CONSTRAINT valid_price CHECK (price > 0),
    CONSTRAINT valid_volume CHECK (volume >= 0),
    CONSTRAINT valid_score CHECK (quality_score >= 0 AND quality_score <= 1)
);

-- Convert to hypertable (auto-partitioned by time)
SELECT create_hypertable(
    'market_data',
    'timestamp',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_market_symbol_time 
    ON market_data (symbol, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_market_exchange_time 
    ON market_data (exchange, timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_market_quality 
    ON market_data (quality_score)
    WHERE quality_score < 0.7;  -- Partial index for bad data


-- ============================================================
-- 5-MINUTE OHLCV CONTINUOUS AGGREGATE
-- ============================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS ohlcv_5min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('5 minutes', timestamp) AS bucket,
    symbol,
    exchange,
    FIRST(price, timestamp) AS open,
    MAX(price) AS high,
    MIN(price) AS low,
    LAST(price, timestamp) AS close,
    SUM(volume) AS volume,
    COUNT(*) AS trade_count,
    AVG(quality_score) AS avg_quality,
    -- Additional analytics
    STDDEV(price) AS price_stddev,
    MAX(price) - MIN(price) AS price_range
FROM market_data
GROUP BY bucket, symbol, exchange
WITH NO DATA;

-- Auto-refresh policy (run every minute, process last 2 hours)
SELECT add_continuous_aggregate_policy(
    'ohlcv_5min',
    start_offset => INTERVAL '2 hours',
    end_offset => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute',
    if_not_exists => TRUE
);


-- ============================================================
-- 1-HOUR OHLCV AGGREGATE
-- ============================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS ohlcv_1hour
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', timestamp) AS bucket,
    symbol,
    exchange,
    FIRST(price, timestamp) AS open,
    MAX(price) AS high,
    MIN(price) AS low,
    LAST(price, timestamp) AS close,
    SUM(volume) AS volume,
    COUNT(*) AS trade_count,
    AVG(quality_score) AS avg_quality
FROM market_data
GROUP BY bucket, symbol, exchange
WITH NO DATA;

SELECT add_continuous_aggregate_policy(
    'ohlcv_1hour',
    start_offset => INTERVAL '3 hours',
    end_offset => INTERVAL '1 hour',
    schedule_interval => INTERVAL '30 minutes',
    if_not_exists => TRUE
);


-- ============================================================
-- 1-DAY OHLCV AGGREGATE
-- ============================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS ohlcv_1day
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', timestamp) AS bucket,
    symbol,
    exchange,
    FIRST(price, timestamp) AS open,
    MAX(price) AS high,
    MIN(price) AS low,
    LAST(price, timestamp) AS close,
    SUM(volume) AS volume,
    COUNT(*) AS trade_count,
    AVG(quality_score) AS avg_quality
FROM market_data
GROUP BY bucket, symbol, exchange
WITH NO DATA;

SELECT add_continuous_aggregate_policy(
    'ohlcv_1day',
    start_offset => INTERVAL '2 days',
    end_offset => INTERVAL '1 day',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists => TRUE
);


-- ============================================================
-- COMPRESSION (for data older than 90 days)
-- ============================================================
ALTER TABLE market_data SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol, exchange',
    timescaledb.compress_orderby = 'timestamp DESC'
);

SELECT add_compression_policy(
    'market_data',
    compress_after => INTERVAL '90 days',
    if_not_exists => TRUE
);


-- ============================================================
-- RETENTION POLICY (delete data older than 1 year)
-- ============================================================
SELECT add_retention_policy(
    'market_data',
    drop_after => INTERVAL '365 days',
    if_not_exists => TRUE
);


-- ============================================================
-- QUALITY METRICS TABLE
-- ============================================================
CREATE TABLE IF NOT EXISTS quality_metrics (
    timestamp       TIMESTAMPTZ NOT NULL,
    symbol          TEXT NOT NULL,
    exchange        TEXT NOT NULL,
    
    -- Quality metrics
    total_messages  BIGINT,
    valid_messages  BIGINT,
    avg_quality     REAL,
    min_quality     REAL,
    
    -- Issue breakdown
    parse_errors    INTEGER,
    stale_data      INTEGER,
    price_anomalies INTEGER,
    volume_spikes   INTEGER
);

SELECT create_hypertable(
    'quality_metrics',
    'timestamp',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists => TRUE
);


-- ============================================================
-- USEFUL QUERIES
-- ============================================================
-- Example: Get latest OHLCV for all symbols
-- SELECT * FROM ohlcv_5min 
-- WHERE bucket > NOW() - INTERVAL '1 hour'
-- ORDER BY bucket DESC, symbol;

-- Example: Get quality issues summary
-- SELECT symbol, 
--        COUNT(*) as total,
--        AVG(quality_score) as avg_quality,
--        array_agg(DISTINCT unnest(issues)) as unique_issues
-- FROM market_data
-- WHERE timestamp > NOW() - INTERVAL '1 hour'
-- GROUP BY symbol;

-- Verify setup
SELECT 'market_data' as table_name, 
       pg_size_pretty(hypertable_size('market_data')) as size,
       (SELECT COUNT(*) FROM timescaledb_information.chunks 
        WHERE hypertable_name = 'market_data') as chunks;
