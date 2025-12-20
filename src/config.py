# HIMARI Opus1 - Configuration File
# Centralized configuration for exchanges, thresholds, and pipeline settings

import os
from dataclasses import dataclass, field
from typing import Set, Dict
import yaml


@dataclass
class ExchangeConfig:
    """Configuration for supported exchanges."""
    # Valid exchanges for quality validation
    valid_exchanges: Set[str] = field(default_factory=lambda: {
        'binance', 'kraken', 'bybit', 'deribit', 'coinbase', 
        'okx', 'huobi', 'kucoin', 'gate', 'bitfinex'
    })
    
    # Exchange-specific latency thresholds (ms)
    latency_thresholds: Dict[str, int] = field(default_factory=lambda: {
        'binance': 100,
        'kraken': 200,
        'bybit': 150,
        'deribit': 100,
        'coinbase': 150,
        'okx': 150,
        'huobi': 200,
        'kucoin': 200,
        'gate': 250,
        'bitfinex': 150,
    })


@dataclass
class QualityConfig:
    """Quality validation thresholds."""
    # Price validation
    max_price_deviation_pct: float = 0.10  # 10% single-tick move = extreme
    large_price_move_pct: float = 0.05     # 5% = notable move
    ema_deviation_threshold: float = 0.15  # 15% from EMA = anomaly
    
    # Volume validation
    extreme_volume_spike: float = 100.0    # 100x normal volume
    large_volume_spike: float = 10.0       # 10x normal volume
    
    # Temporal validation
    stale_data_threshold_ms: int = 30000   # 30 seconds
    delayed_data_threshold_ms: int = 10000  # 10 seconds
    future_timestamp_threshold_ms: int = 5000  # 5 seconds into future
    large_gap_threshold_ms: int = 60000    # 60 second gap
    
    # Precision
    max_decimal_places: int = 8
    
    # Scoring penalties
    penalties: Dict[str, float] = field(default_factory=lambda: {
        'INVALID_PRICE_NEGATIVE': 0.25,
        'INVALID_VOLUME_NEGATIVE': 0.20,
        'UNKNOWN_EXCHANGE': 0.15,
        'OUT_OF_ORDER': 0.30,
        'DUPLICATE_TIMESTAMP': 0.10,
        'LARGE_GAP': 0.05,
        'EXTREME_PRICE_MOVE': 0.20,
        'LARGE_PRICE_MOVE': 0.05,
        'PRICE_ANOMALY': 0.10,
        'EXTREME_VOLUME_SPIKE': 0.15,
        'VOLUME_SPIKE': 0.05,
        'EXCESSIVE_PRECISION': 0.05,
        'STALE_DATA': 0.15,
        'DELAYED_DATA': 0.05,
        'FUTURE_TIMESTAMP': 0.20,
    })


@dataclass
class FlinkConfig:
    """Flink pipeline configuration."""
    # Parallelism
    parallelism: int = 4
    
    # Checkpointing
    checkpoint_interval_ms: int = 30000  # 30 seconds
    min_pause_between_checkpoints_ms: int = 10000
    checkpoint_timeout_ms: int = 120000
    
    # State TTL
    state_ttl_hours: int = 24
    
    # Kafka/Redpanda
    kafka_bootstrap: str = os.getenv('KAFKA_BOOTSTRAP', 'localhost:9092')
    kafka_group_id: str = os.getenv('KAFKA_GROUP_ID', 'himari-quality-processor')
    
    # Topics
    input_topic: str = 'raw_market_data'
    output_topic: str = 'quality_scores'
    
    # Checkpoint storage (use S3 for production)
    checkpoint_storage: str = os.getenv(
        'FLINK_CHECKPOINT_STORAGE',
        'file:///tmp/flink-checkpoints'
    )
    
    # S3 checkpoint configuration (for production)
    s3_checkpoint_bucket: str = os.getenv('S3_CHECKPOINT_BUCKET', '')
    s3_access_key: str = os.getenv('AWS_ACCESS_KEY_ID', '')
    s3_secret_key: str = os.getenv('AWS_SECRET_ACCESS_KEY', '')


@dataclass
class RedisConfig:
    """Redis sink configuration."""
    host: str = os.getenv('REDIS_HOST', 'localhost')
    port: int = int(os.getenv('REDIS_PORT', '6379'))
    password: str = os.getenv('REDIS_PASSWORD', '')
    db: int = int(os.getenv('REDIS_DB', '0'))
    
    # Performance
    batch_size: int = 100
    max_connections: int = 10
    socket_timeout: float = 5.0
    
    # TTL
    feature_ttl_seconds: int = 3600  # 1 hour
    history_max_entries: int = 1000


@dataclass 
class TimescaleConfig:
    """TimescaleDB sink configuration."""
    host: str = os.getenv('TIMESCALE_HOST', 'localhost')
    port: int = int(os.getenv('TIMESCALE_PORT', '5432'))
    database: str = os.getenv('TIMESCALE_DB', 'himari_analytics')
    user: str = os.getenv('TIMESCALE_USER', 'himari')
    password: str = os.getenv('TIMESCALE_PASSWORD', '')
    
    # Performance
    batch_size: int = 500
    min_connections: int = 2
    max_connections: int = 10
    connect_timeout: int = 10


@dataclass
class Neo4jConfig:
    """Neo4j sink configuration."""
    uri: str = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    user: str = os.getenv('NEO4J_USER', 'neo4j')
    password: str = os.getenv('NEO4J_PASSWORD', '')
    
    # Performance
    batch_size: int = 50
    max_pool_size: int = 10
    max_transaction_retry_time: float = 30.0


@dataclass
class HimariConfig:
    """Main configuration container."""
    exchanges: ExchangeConfig = field(default_factory=ExchangeConfig)
    quality: QualityConfig = field(default_factory=QualityConfig)
    flink: FlinkConfig = field(default_factory=FlinkConfig)
    redis: RedisConfig = field(default_factory=RedisConfig)
    timescale: TimescaleConfig = field(default_factory=TimescaleConfig)
    neo4j: Neo4jConfig = field(default_factory=Neo4jConfig)
    
    @classmethod
    def from_yaml(cls, path: str) -> 'HimariConfig':
        """Load configuration from YAML file."""
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        
        config = cls()
        
        if 'exchanges' in data:
            if 'valid_exchanges' in data['exchanges']:
                config.exchanges.valid_exchanges = set(data['exchanges']['valid_exchanges'])
            if 'latency_thresholds' in data['exchanges']:
                config.exchanges.latency_thresholds.update(data['exchanges']['latency_thresholds'])
        
        if 'quality' in data:
            for key, value in data['quality'].items():
                if hasattr(config.quality, key):
                    setattr(config.quality, key, value)
        
        return config
    
    def get_valid_exchanges(self) -> Set[str]:
        """Get the set of valid exchanges."""
        return self.exchanges.valid_exchanges
    
    def is_valid_exchange(self, exchange: str) -> bool:
        """Check if an exchange is valid."""
        return exchange.lower() in self.exchanges.valid_exchanges
    
    def get_penalty(self, issue: str) -> float:
        """Get quality penalty for an issue type."""
        return self.quality.penalties.get(issue, 0.0)


# Global config instance (can be overridden)
_config: HimariConfig = None


def get_config() -> HimariConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = HimariConfig()
    return _config


def load_config(path: str = None) -> HimariConfig:
    """Load configuration from file or environment."""
    global _config
    
    if path and os.path.exists(path):
        _config = HimariConfig.from_yaml(path)
    else:
        _config = HimariConfig()
    
    return _config
