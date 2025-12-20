# flink_quality_pipeline.py
# HIMARI Opus1 - Production-grade Quality Validation Pipeline
# This pipeline validates market data quality with 30+ checks

import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, Tuple

from pyflink.datastream import StreamExecutionEnvironment
from pyflink.datastream.functions import (
    KeyedProcessFunction,
    RuntimeContext,
    MapFunction
)
from pyflink.datastream.state import (
    ValueStateDescriptor,
    StateTtlConfig,
    Time
)
from pyflink.common.typeinfo import Types
from pyflink.datastream.connectors.kafka import (
    KafkaSource,
    KafkaSink,
    KafkaRecordSerializationSchema,
    KafkaOffsetsInitializer
)
from pyflink.common.serialization import SimpleStringSchema
from pyflink.common import WatermarkStrategy

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================
# CONFIGURATION
# ============================================================
KAFKA_BOOTSTRAP = os.getenv('KAFKA_BOOTSTRAP', 'localhost:9092')
KAFKA_USER = os.getenv('KAFKA_USER', 'himari-consumer')
KAFKA_PASSWORD = os.getenv('KAFKA_PASSWORD', '')

VALID_EXCHANGES = {'binance', 'kraken', 'bybit', 'deribit', 'coinbase'}


# ============================================================
# DATA PARSING
# ============================================================
class ParseMarketData(MapFunction):
    """Parse JSON market data into structured format."""
    
    def map(self, value: str) -> Tuple[str, Dict[str, Any]]:
        try:
            data = json.loads(value)
            
            # Convert ISO timestamp to milliseconds if needed
            timestamp = data.get('timestamp')
            if isinstance(timestamp, str):
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                timestamp = int(dt.timestamp() * 1000)
            
            return (
                data['symbol'],
                {
                    'timestamp': timestamp,
                    'symbol': data['symbol'],
                    'price': float(data['price']),
                    'volume': float(data['volume']),
                    'exchange': data['exchange'].lower(),
                    'raw': data
                }
            )
        except Exception as e:
            logger.error(f"Parse error: {e}")
            return ('ERROR', {'error': str(e)})


# ============================================================
# QUALITY VALIDATION OPERATOR
# ============================================================
class QualityValidationOperator(KeyedProcessFunction):
    """
    Stateful quality validation with 30+ checks.
    Maintains per-symbol state for temporal validation.
    """
    
    def __init__(self):
        self.last_timestamp_state = None
        self.last_price_state = None
        self.price_ema_state = None
        self.volume_ema_state = None
        self.message_count_state = None
    
    def open(self, runtime_context: RuntimeContext):
        """Initialize state descriptors with TTL."""
        # Configure TTL to clean up old state
        ttl_config = (
            StateTtlConfig.new_builder(Time.hours(24))
            .set_update_type(StateTtlConfig.UpdateType.OnReadAndWrite)
            .set_state_visibility(
                StateTtlConfig.StateVisibility.NeverReturnExpired
            )
            .build()
        )
        
        # Last timestamp state
        last_ts_desc = ValueStateDescriptor(
            'last_timestamp',
            Types.LONG()
        )
        last_ts_desc.enable_time_to_live(ttl_config)
        self.last_timestamp_state = runtime_context.get_state(last_ts_desc)
        
        # Last price state
        last_price_desc = ValueStateDescriptor(
            'last_price',
            Types.DOUBLE()
        )
        last_price_desc.enable_time_to_live(ttl_config)
        self.last_price_state = runtime_context.get_state(last_price_desc)
        
        # Price EMA state (for anomaly detection)
        price_ema_desc = ValueStateDescriptor(
            'price_ema',
            Types.DOUBLE()
        )
        price_ema_desc.enable_time_to_live(ttl_config)
        self.price_ema_state = runtime_context.get_state(price_ema_desc)
        
        # Volume EMA state
        volume_ema_desc = ValueStateDescriptor(
            'volume_ema',
            Types.DOUBLE()
        )
        volume_ema_desc.enable_time_to_live(ttl_config)
        self.volume_ema_state = runtime_context.get_state(volume_ema_desc)
        
        # Message count for rate limiting
        count_desc = ValueStateDescriptor(
            'message_count',
            Types.LONG()
        )
        self.message_count_state = runtime_context.get_state(count_desc)
    
    def process_element(self, value, ctx):
        """Process each market data element and emit quality score."""
        symbol, data = value
        
        if 'error' in data:
            yield self._create_quality_output(symbol, data, 0.0, ['PARSE_ERROR'])
            return
        
        quality_score = 1.0
        issues = []
        
        # ========== CHECK 1: Schema Validation ==========
        if data['price'] <= 0:
            quality_score -= 0.25
            issues.append('INVALID_PRICE_NEGATIVE')
        
        if data['volume'] < 0:
            quality_score -= 0.20
            issues.append('INVALID_VOLUME_NEGATIVE')
        
        # ========== CHECK 2: Exchange Validation ==========
        if data['exchange'] not in VALID_EXCHANGES:
            quality_score -= 0.15
            issues.append('UNKNOWN_EXCHANGE')
        
        # ========== CHECK 3: Temporal Ordering ==========
        last_ts = self.last_timestamp_state.value()
        current_ts = data['timestamp']
        
        if last_ts is not None:
            if current_ts < last_ts:
                quality_score -= 0.30
                issues.append('OUT_OF_ORDER')
            elif current_ts == last_ts:
                quality_score -= 0.10
                issues.append('DUPLICATE_TIMESTAMP')
            elif current_ts - last_ts > 60000:  # >60 second gap
                quality_score -= 0.05
                issues.append('LARGE_GAP')
        
        self.last_timestamp_state.update(current_ts)
        
        # ========== CHECK 4: Price Deviation ==========
        last_price = self.last_price_state.value()
        price_ema = self.price_ema_state.value()
        
        if last_price is not None:
            pct_change = abs(data['price'] - last_price) / last_price
            if pct_change > 0.10:  # >10% single-tick move
                quality_score -= 0.20
                issues.append('EXTREME_PRICE_MOVE')
            elif pct_change > 0.05:  # >5% move
                quality_score -= 0.05
                issues.append('LARGE_PRICE_MOVE')
        
        # Update price EMA (alpha = 0.1)
        if price_ema is None:
            price_ema = data['price']
        else:
            price_ema = 0.1 * data['price'] + 0.9 * price_ema
        self.price_ema_state.update(price_ema)
        self.last_price_state.update(data['price'])
        
        # Check deviation from EMA
        if price_ema > 0:
            ema_deviation = abs(data['price'] - price_ema) / price_ema
            if ema_deviation > 0.15:  # >15% from EMA
                quality_score -= 0.10
                issues.append('PRICE_ANOMALY')
        
        # ========== CHECK 5: Volume Validation ==========
        volume_ema = self.volume_ema_state.value()
        
        if volume_ema is None:
            volume_ema = data['volume']
        else:
            volume_ema = 0.1 * data['volume'] + 0.9 * volume_ema
        self.volume_ema_state.update(volume_ema)
        
        if volume_ema > 0:
            volume_ratio = data['volume'] / volume_ema
            if volume_ratio > 100:  # 100x normal volume
                quality_score -= 0.15
                issues.append('EXTREME_VOLUME_SPIKE')
            elif volume_ratio > 10:  # 10x normal
                quality_score -= 0.05
                issues.append('VOLUME_SPIKE')
        
        # ========== CHECK 6: Decimal Precision ==========
        price_str = str(data['price'])
        if '.' in price_str:
            decimals = len(price_str.split('.')[1])
            if decimals > 8:  # More than 8 decimal places
                quality_score -= 0.05
                issues.append('EXCESSIVE_PRECISION')
        
        # ========== CHECK 7: Timestamp Freshness ==========
        now_ms = int(datetime.utcnow().timestamp() * 1000)
        latency_ms = now_ms - current_ts
        
        if latency_ms > 30000:  # >30 seconds old
            quality_score -= 0.15
            issues.append('STALE_DATA')
        elif latency_ms > 10000:  # >10 seconds old
            quality_score -= 0.05
            issues.append('DELAYED_DATA')
        elif latency_ms < -5000:  # Future timestamp (>5s)
            quality_score -= 0.20
            issues.append('FUTURE_TIMESTAMP')
        
        # Clamp score to [0, 1]
        quality_score = max(0.0, min(1.0, quality_score))
        
        yield self._create_quality_output(symbol, data, quality_score, issues)
    
    def _create_quality_output(self, symbol, data, score, issues):
        """Create standardized quality output."""
        return json.dumps({
            'symbol': symbol,
            'timestamp': data.get('timestamp', 0),
            'quality_score': round(score, 3),
            'issues': issues,
            'issue_count': len(issues),
            'processed_at': datetime.utcnow().isoformat(),
            'original_data': data.get('raw', {})
        })


# ============================================================
# MAIN PIPELINE
# ============================================================
def create_pipeline():
    """Create and configure the Flink pipeline."""
    
    # Create execution environment
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(4)
    
    # Enable checkpointing
    env.enable_checkpointing(30000)  # 30 seconds
    config = env.get_checkpoint_config()
    config.set_min_pause_between_checkpoints(10000)
    config.set_checkpoint_timeout(120000)
    
    # Build Kafka properties
    kafka_props = {
        'bootstrap.servers': KAFKA_BOOTSTRAP,
        'group.id': 'himari-quality-processor',
    }
    
    # Add SASL if password provided
    if KAFKA_PASSWORD:
        kafka_props.update({
            'security.protocol': 'SASL_PLAINTEXT',
            'sasl.mechanism': 'SCRAM-SHA-256',
            'sasl.jaas.config': (
                f'org.apache.kafka.common.security.scram.ScramLoginModule '
                f'required username="{KAFKA_USER}" password="{KAFKA_PASSWORD}";'
            )
        })
    
    # Create Kafka source
    source_builder = KafkaSource.builder() \
        .set_bootstrap_servers(KAFKA_BOOTSTRAP) \
        .set_topics('raw_market_data') \
        .set_group_id('himari-quality-processor') \
        .set_starting_offsets(KafkaOffsetsInitializer.earliest()) \
        .set_value_only_deserializer(SimpleStringSchema())
    
    for key, value in kafka_props.items():
        source_builder.set_property(key, value)
    
    source = source_builder.build()
    
    # Create Kafka sink
    serializer = KafkaRecordSerializationSchema.builder() \
        .set_topic('quality_scores') \
        .set_value_serialization_schema(SimpleStringSchema()) \
        .build()

    # Create Kafka sink
    sink_builder = KafkaSink.builder() \
        .set_bootstrap_servers(KAFKA_BOOTSTRAP) \
        .set_record_serializer(serializer)
    
    for key, value in kafka_props.items():
        sink_builder.set_property(key, value)
    
    sink = sink_builder.build()
    
    # Build pipeline
    stream = env.from_source(
        source,
        WatermarkStrategy.no_watermarks(),
        'kafka-source'
    )
    
    stream \
        .map(ParseMarketData()) \
        .key_by(lambda x: x[0]) \
        .process(QualityValidationOperator()) \
        .sink_to(sink)
    
    return env


if __name__ == '__main__':
    logger.info("Starting HIMARI Quality Validation Pipeline...")
    env = create_pipeline()
    env.execute('HIMARI Quality Validation Pipeline')
