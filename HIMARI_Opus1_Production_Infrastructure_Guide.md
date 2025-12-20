> **HIMARI** **OPUS** **1** \| Production Infrastructure Guide
>
> **HIMARI** **OPUS** **1** *Hierarchical* *Intelligent* *Multi-Agent*
> *Resilient* *Infrastructure*
>
> **PRODUCTION-GRADE** **DATA** **INFRASTRUCTURE** **DEPLOYMENT**
> **GUIDE**
>
> Enterprise-Grade Crypto Cascade Defense System
>
> Optimized Infrastructure at \$200/month Budget
>
> **TARGET** **SPECIFICATIONS**

||
||
||
||
||
||
||
||

> Version 2.0 \| Production Ready
>
> Page 1 of 42 \| Confidential
>
> **HIMARI** **OPUS** **1** \| Production Infrastructure Guide

**Table** **of** **Contents**

Table of Contents
.............................................................................................................................2
Executive
Summary..........................................................................................................................4
Architecture
Philosophy.................................................................................................................4
Budget
Allocation..........................................................................................................................4
Part I: Production
Architecture..........................................................................................................5
System Flow
Diagram...................................................................................................................5
Component
Interactions................................................................................................................5
Part II: Redpanda Message
Broker...................................................................................................7
Server
Provisioning.......................................................................................................................7
Initial Server Setup
....................................................................................................................7
Production Configuration
...........................................................................................................7
Topic
Configuration.......................................................................................................................8
Authentication
Setup.....................................................................................................................9
Part III: Apache Flink Stream
Processing........................................................................................10
Server
Provisioning.....................................................................................................................10
Installation...............................................................................................................................10
Memory Configuration (Critical)
...............................................................................................10
Checkpoint Configuration (Distributed
Storage).......................................................................11
Quality Validation Operator
(Python)...........................................................................................12
Main Pipeline
Execution...........................................................................................................17
Part IV: Redis Feature
Store...........................................................................................................19
Self-Hosted Redis
Configuration.................................................................................................19
Feature Store Sink (Flink
Integration)..........................................................................................20
Part V: TimescaleDB Analytics
.......................................................................................................22
Server
Provisioning.....................................................................................................................22
Installation...............................................................................................................................22
Database
Schema...................................................................................................................22
Continuous Aggregates (8x Query
Speedup)...........................................................................24
TimescaleDB Sink (Flink Integration)
..........................................................................................25
Part VI: Neo4j Knowledge
Graph....................................................................................................27
Deployment
Options....................................................................................................................27
Graph Schema
Initialization.........................................................................................................27
Causal Event Queries
.................................................................................................................28
Part VII: Monitoring and
Observability.............................................................................................30
Prometheus Setup
......................................................................................................................30
Node Exporter (System
Metrics)..................................................................................................31
Grafana Cloud Integration (Free
Tier)..........................................................................................31
Critical
Alerts...............................................................................................................................32
Part VIII: Security
Hardening...........................................................................................................33
Firewall
Configuration..................................................................................................................33

> Page 2 of 42 \| Confidential
>
> **HIMARI** **OPUS** **1** \| Production Infrastructure Guide

Secrets
Management..................................................................................................................33
TLS/SSL
Configuration................................................................................................................34
SSH
Hardening...........................................................................................................................34
Part IX: Disaster
Recovery..............................................................................................................36
Recovery Objectives
...................................................................................................................36
Backup
Strategy..........................................................................................................................36
Failover
Procedure......................................................................................................................37
Part X: Verification and
Testing.......................................................................................................38
Integration Test
Suite..................................................................................................................38
Pre-Production
Checklist.............................................................................................................40
Appendix: Alternative Platform
Options...........................................................................................41
Compute
Alternatives..................................................................................................................41
Message Broker
Alternatives.......................................................................................................41
Database
Alternatives.................................................................................................................41
Object Storage
Alternatives.........................................................................................................41

> Page 3 of 42 \| Confidential
>
> **HIMARI** **OPUS** **1** \| Production Infrastructure Guide

**Executive** **Summary**

This document provides a production-grade implementation guide for the
HIMARI Opus 1 data infrastructure layer. It addresses critical issues
identified in initial designs and provides battle-tested configurations
that achieve enterprise reliability within a \$200/month budget
constraint.

> ✓ **Key** **Improvements** **in** **This** **Guide**
>
> This revised guide eliminates single points of failure, fixes memory
> provisioning issues, optimizes cross-provider latency, corrects code
> errors, implements security hardening, and adds comprehensive
> monitoring.

**Architecture** **Philosophy**

The infrastructure follows three core principles that guide every design
decision:

**Resilience** **First:** Every component has a failover path. State is
persisted to distributed storage. No single server failure can take down
the system.

**Latency** **Aware:** Components are co-located within the same data
center to minimize network hops. Cross-provider architectures are
avoided when possible.

**Cost** **Conscious:** Every dollar spent is justified by measurable
reliability or performance improvement. Self-hosting is preferred over
managed services when operational overhead is manageable.

**Budget** **Allocation**

The following table shows the recommended budget allocation across
infrastructure components, optimized for maximum reliability within the
\$200/month constraint:

||
||
||
||
||
||
||
||
||
||
||
||
||

> Page 4 of 42 \| Confidential
>
> **HIMARI** **OPUS** **1** \| Production Infrastructure Guide

**Part** **I:** **Production** **Architecture**

The production architecture consolidates components within a single
cloud provider's data center to eliminate cross-provider latency while
maintaining clear separation of concerns through containerization.

**System** **Flow** **Diagram**

Data flows through the system in a structured pipeline, with each stage
adding value while maintaining fault tolerance:

> ┌─────────────────────────────────────────────────────────────────────┐
> │ MARKET DATA SOURCES (CEX APIs) │ │ Binance · Kraken · Bybit ·
> Deribit · Coinbase │
> └─────────────────────────────┬───────────────────────────────────────┘
>
> │ ▼
>
> ┌─────────────────────────────────────────────────────────────────────┐
> │ REDPANDA (Event Broker) │ │ ┌──────────────┐ ┌──────────────┐
> ┌──────────────┐ │ │ │raw_market\_ │ │quality\_ │ │causal\_ │ │ │
> │data (12 part)│ │scores (6 p) │ │events (3 p) │ │ │ └──────────────┘
> └──────────────┘ └──────────────┘ │ │ Hetzner CPX21 · 4 vCPU · 8GB RAM
> │
> └─────────────────────────────┬───────────────────────────────────────┘
>
> │ ▼
>
> ┌─────────────────────────────────────────────────────────────────────┐
> │ APACHE FLINK (Stream Processor) │ │ ┌──────────────┐
> ┌──────────────┐ ┌──────────────┐ │ │ │Quality │ │Feature │ │Causal
> Event │ │ │ │Validation │ │Computation │ │Detection │ │ │
> └──────────────┘ └──────────────┘ └──────────────┘ │ │ Checkpoints →
> S3-Compatible Storage (distributed) │ │ Hetzner CPX41 · 8 vCPU · 16GB
> RAM │
> └───────┬─────────────────┬─────────────────┬─────────────────────────┘
>
> │ │ │ ▼ ▼ ▼
>
> ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ │ REDIS │ │
> TIMESCALEDB │ │ NEO4J │ │ (Features) │ │ (Analytics) │ │ (Graph) │ │
> \<10ms │ │ \<100ms │ │ Causal │ │ serving │ │ queries │ │ chains │
> └───────────────┘ └───────────────┘ └───────────────┘
>
> │ │ │ └─────────────────┴─────────────────┘ │ ▼
>
> ┌─────────────────────────────────────────────────────────────────────┐
> │ HIMARI COGNITIVE LAYERS │ │ Layer 1-6: Multi-Agent Coordination │
> └─────────────────────────────────────────────────────────────────────┘

**Component** **Interactions**

**Redpanda** **to** **Flink:** Low-latency streaming with sub-20ms
delivery when co-located. Exactly-once semantics guaranteed through
Kafka protocol. Flink consumes in real-time, processes, and outputs to
multiple sinks.

**Flink** **to** **Redis:** Feature store synchronization with sub-10ms
latency target. Flink computes features every 1-5 seconds and writes
latest values to Redis for online serving. Trading strategies read
directly from Redis.

> Page 5 of 42 \| Confidential
>
> **HIMARI** **OPUS** **1** \| Production Infrastructure Guide

**Flink** **to** **TimescaleDB:** Warm storage for analytics. Flink
batches writes every 10 seconds. TimescaleDB stores 30-90 day history
with continuous aggregates providing 8x query speedup for OHLCV data.

**Flink** **to** **Object** **Storage:** Cold storage archival and
checkpoint persistence. Daily Parquet snapshots with 10:1 compression.
Checkpoints written to distributed storage enable recovery on any node.

**Flink** **to** **Neo4j:** Event-driven graph updates. Flink detects
causal events (whale transfers, liquidation cascades) and updates the
knowledge graph in real-time to provide context for cognitive layers.

> ⚠**Critical** **Design** **Decision:** **Co-location**
>
> All components MUST be deployed within the same data center to achieve
> latency targets. Cross-provider architectures (e.g., Redpanda Cloud +
> DigitalOcean + Hetzner) add 20-50ms per network hop and will miss
> sub-50ms end-to-end targets.
>
> Page 6 of 42 \| Confidential
>
> **HIMARI** **OPUS** **1** \| Production Infrastructure Guide
>
> **Part** **II:** **Redpanda** **Message** **Broker**
>
> Redpanda provides Kafka-compatible message streaming with lower
> operational overhead. For cost-optimized deployments, self-hosting
> Redpanda on a dedicated VPS provides better value than managed cloud
> services.
>
> **Server** **Provisioning**
>
> Provision a Hetzner CPX21 server (or equivalent) with the following
> specifications:

||
||
||
||
||
||
||
||
||

> **Initial** **Server** **Setup**
>
> \# SSH into the server
>
> ssh root@\<redpanda-server-ip\>
>
> \# Update system and install prerequisites apt-get update && apt-get
> upgrade -y
>
> apt-get install -y curl gnupg2 ca-certificates lsb-release
>
> \# Install Redpanda
>
> curl -1sLf
> 'https://dl.redpanda.com/nzc4FFFFF/redpanda/cfg/setup/bash.deb.sh' \|
> sudo -E bash
>
> apt-get install -y redpanda
>
> \# Configure Redpanda for single-node production
>
> rpk redpanda config bootstrap --self \<private-ip\> --ips
> \<private-ip\> rpk redpanda config set
> redpanda.empty_seed_starts_cluster false
>
> \# Set memory limits (leave 2GB for OS)
>
> rpk redpanda config set redpanda.developer_mode false rpk redpanda
> config set rpk.tune_network true
>
> rpk redpanda config set rpk.tune_disk_scheduler true rpk redpanda
> config set rpk.tune_disk_nomerges true rpk redpanda config set
> rpk.tune_disk_write_cache true
>
> **Production** **Configuration**
>
> Edit /etc/redpanda/redpanda.yaml with these production settings:
>
> \# /etc/redpanda/redpanda.yaml redpanda:
>
> data_directory: /var/lib/redpanda/data
>
> \# Memory configuration (6GB for Redpanda, 2GB for OS) memory:
>
> enable_memory_locking: true reserved_memory: 2G
>
> \# Network configuration
>
> Page 7 of 42 \| Confidential
>
> **HIMARI** **OPUS** **1** \| Production Infrastructure Guide
>
> rpc_server: address: 0.0.0.0 port: 33145
>
> kafka_api:
>
> \- address: 0.0.0.0 port: 9092 name: internal
>
> \- address: 0.0.0.0 port: 9093 name: external
>
> authentication_method: sasl
>
> admin:
>
> \- address: 127.0.0.1 \# Only localhost for admin port: 9644
>
> \# Performance tuning group_topic_partitions: 16
> default_topic_partitions: 12
>
> default_topic_replications: 1 \# Single node, no replication
>
> \# Retention settings log_retention_ms: 604800000 log_segment_size:
> 134217728

\# 7 days

\# 128MB segments

> \# Enable SASL authentication rpk:
>
> kafka_api: sasl:
>
> user: himari-producer type: SCRAM-SHA-256

**Topic** **Configuration**

Create the required topics with appropriate partition counts for
parallelism:

> \# Start Redpanda service systemctl enable redpanda systemctl start
> redpanda
>
> \# Wait for startup sleep 10
>
> \# Create topics with production settings rpk topic create
> raw_market_data \\
>
> --partitions 12 \\
>
> --config retention.ms=604800000 \\ --config compression.type=snappy \\
> --config cleanup.policy=delete
>
> rpk topic create quality_scores \\ --partitions 6 \\
>
> --config retention.ms=1209600000 \\ --config compression.type=snappy
>
> rpk topic create causal_events \\ --partitions 3 \\
>
> --config retention.ms=2592000000 \\ --config compression.type=snappy
>
> rpk topic create features_computed \\ --partitions 6 \\
>
> --config retention.ms=7776000000 \\
>
> Page 8 of 42 \| Confidential
>
> **HIMARI** **OPUS** **1** \| Production Infrastructure Guide

||
||
||
||

**Authentication** **Setup**

> \# Create SASL users for authentication rpk acl user create
> himari-producer \\
>
> --password '\<strong-password-here\>' \\ --mechanism SCRAM-SHA-256
>
> rpk acl user create himari-consumer \\ --password
> '\<strong-password-here\>' \\ --mechanism SCRAM-SHA-256
>
> \# Grant permissions
>
> rpk acl create --allow-principal User:himari-producer \\ --operation
> write --topic '\*'
>
> rpk acl create --allow-principal User:himari-consumer \\ --operation
> read --topic '\*' --group '\*'
>
> \# Test authentication
>
> rpk topic produce raw_market_data \\ --brokers localhost:9093 \\
>
> --sasl-mechanism SCRAM-SHA-256 \\ --user himari-producer \\
>
> --password '\<password\>'
>
> Page 9 of 42 \| Confidential
>
> **HIMARI** **OPUS** **1** \| Production Infrastructure Guide
>
> **Part** **III:** **Apache** **Flink** **Stream** **Processing**
>
> Apache Flink provides the stream processing backbone for quality
> validation, feature computation, and event detection. Proper memory
> configuration and checkpoint management are critical for production
> reliability.
>
> ⚠**Memory** **Configuration** **is** **Critical**
>
> The most common cause of Flink failures is memory misconfiguration.
> RocksDB state backend uses off-heap memory that must be accounted for
> separately from JVM heap. Always leave at least 4GB for the operating
> system and RocksDB.
>
> **Server** **Provisioning**
>
> Flink requires more memory than other components. Provision a Hetzner
> CPX41 (or equivalent):

||
||
||
||
||
||
||
||
||

> **Installation**
>
> \# SSH into the server
>
> ssh root@\<flink-server-ip\>
>
> \# Update system
>
> apt-get update && apt-get upgrade -y
>
> \# Install Java 17 (required for Flink 1.18+) apt-get install -y
> openjdk-17-jdk
>
> java -version \# Verify: openjdk version "17.0.x"
>
> \# Download Flink 1.18 (latest stable) cd /opt
>
> wget
> https://archive.apache.org/dist/flink/flink-1.18.1/flink-1.18.1-bin-scala_2.12.tgz
> tar -xzf flink-1.18.1-bin-scala_2.12.tgz
>
> mv flink-1.18.1 flink
>
> rm flink-1.18.1-bin-scala_2.12.tgz
>
> \# Create directories for state and logs mkdir -p
> /data/flink-checkpoints
>
> mkdir -p /data/flink-savepoints mkdir -p /var/log/flink
>
> chown -R root:root /data/flink-\*
>
> **Memory** **Configuration** **(Critical)**
>
> Edit /opt/flink/conf/flink-conf.yaml with carefully calculated memory
> settings:
>
> \# /opt/flink/conf/flink-conf.yaml
>
> \# ============================================================ \#
> MEMORY CONFIGURATION (16GB total RAM)
>
> Page 10 of 42 \| Confidential
>
> **HIMARI** **OPUS** **1** \| Production Infrastructure Guide
>
> \# ============================================================ \#
> Budget: 16GB total
>
> \# - OS + buffers: 2GB
>
> \# - RocksDB off-heap: 4GB \# - JobManager: 2GB
>
> \# - TaskManager: 8GB
>
> \# ============================================================
>
> jobmanager.memory.process.size: 2048m taskmanager.memory.process.size:
> 8192m
>
> \# TaskManager memory breakdown taskmanager.memory.managed.size: 2048m
> taskmanager.memory.network.fraction: 0.1
> taskmanager.memory.network.min: 256m taskmanager.memory.network.max:
> 1024m

\# For RocksDB state \# Network buffers

> \# JVM overhead (important for RocksDB)
> taskmanager.memory.jvm-overhead.min: 512m
> taskmanager.memory.jvm-overhead.max: 2048m
> taskmanager.memory.jvm-overhead.fraction: 0.1
>
> \# ============================================================ \#
> PARALLELISM
>
> \# ============================================================
> taskmanager.numberOfTaskSlots: 4 \# 4 parallel tasks
> parallelism.default: 4 \# Match slot count
>
> \# ============================================================ \#
> NETWORK
>
> \# ============================================================
> jobmanager.rpc.address: 0.0.0.0
>
> jobmanager.rpc.port: 6123 taskmanager.rpc.port: 6124
>
> \# REST API (localhost only for security) rest.port: 8081
>
> rest.bind-address: 127.0.0.1 \# NOT 0.0.0.0!

**Checkpoint** **Configuration** **(Distributed** **Storage)**

||
||
||
||
||

> Page 11 of 42 \| Confidential
>
> **HIMARI** **OPUS** **1** \| Production Infrastructure Guide
>
> \# CHECKPOINT SETTINGS
>
> \# ============================================================
> execution.checkpointing.mode: EXACTLY_ONCE
> execution.checkpointing.interval: 30000 \# Every 30 seconds
> execution.checkpointing.min-pause: 10000 \# 10s between checkpoints
> execution.checkpointing.timeout: 120000 \# 2 minute timeout
> execution.checkpointing.max-concurrent-checkpoints: 1
>
> \# Checkpoint storage state.checkpoint-storage: filesystem
>
> state.checkpoints.num-retained: 3 \# Keep last 3
>
> \# ============================================================ \#
> RESTART STRATEGY
>
> \# ============================================================
> restart-strategy: fixed-delay
>
> restart-strategy.fixed-delay.attempts: 5
> restart-strategy.fixed-delay.delay: 30s
>
> \# ============================================================ \#
> METRICS (for monitoring)
>
> \# ============================================================
> metrics.reporter.prometheus.factory.class:
> org.apache.flink.metrics.prometheus.PrometheusReporterFactory
> metrics.reporter.prometheus.port: 9249

**Quality** **Validation** **Operator** **(Python)**

The following Python code implements the quality validation pipeline
with corrected state management and proper imports:

> \# flink_quality_pipeline.py
>
> \# Production-grade quality validation for HIMARI Opus 1
>
> import os import json import math import logging
>
> from datetime import datetime
>
> from typing import Dict, Any, List, Tuple
>
> from pyflink.datastream import StreamExecutionEnvironment from
> pyflink.datastream.functions import (
>
> KeyedProcessFunction, RuntimeContext, MapFunction
>
> )
>
> from pyflink.datastream.state import ( ValueStateDescriptor,
> StateTtlConfig,
>
> Time )
>
> from pyflink.common.typeinfo import Types
>
> from pyflink.datastream.connectors.kafka import ( KafkaSource,
>
> KafkaSink, KafkaRecordSerializationSchema
>
> )
>
> from pyflink.common.serialization import SimpleStringSchema from
> pyflink.common import WatermarkStrategy
>
> \# Configure logging logging.basicConfig(level=logging.INFO) logger =
> logging.getLogger(\_\_name\_\_)
>
> Page 12 of 42 \| Confidential
>
> **HIMARI** **OPUS** **1** \| Production Infrastructure Guide

\# ============================================================ \#
CONFIGURATION

\# ============================================================
KAFKA_BOOTSTRAP = os.getenv('KAFKA_BOOTSTRAP', 'redpanda:9092')
KAFKA_USER = os.getenv('KAFKA_USER', 'himari-consumer') KAFKA_PASSWORD =
os.getenv('KAFKA_PASSWORD', '')

VALID_EXCHANGES = {'binance', 'kraken', 'bybit', 'deribit', 'coinbase'}

\# ============================================================ \# DATA
PARSING

\# ============================================================ class
ParseMarketData(MapFunction):

> """Parse JSON market data into structured format."""
>
> def map(self, value: str) -\> Tuple\[str, Dict\[str, Any\]\]: try:
>
> data = json.loads(value)
>
> \# Convert ISO timestamp to milliseconds if needed timestamp =
> data.get('timestamp')
>
> if isinstance(timestamp, str):
>
> dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
> timestamp = int(dt.timestamp() \* 1000)
>
> return ( data\['symbol'\], {
>
> 'timestamp': timestamp, 'symbol': data\['symbol'\], 'price':
> float(data\['price'\]), 'volume': float(data\['volume'\]),
>
> 'exchange': data\['exchange'\].lower(), 'raw': data
>
> } )
>
> except Exception as e: logger.error(f"Parse error: {e}") return
> ('ERROR', {'error': str(e)})
>
> Page 13 of 42 \| Confidential
>
> **HIMARI** **OPUS** **1** \| Production Infrastructure Guide

\# ============================================================ \#
QUALITY VALIDATION OPERATOR

\# ============================================================ class
QualityValidationOperator(KeyedProcessFunction):

> """
>
> Stateful quality validation with 30+ checks. Maintains per-symbol
> state for temporal validation. """
>
> def \_\_init\_\_(self): self.last_timestamp_state = None
> self.last_price_state = None self.price_ema_state = None
> self.volume_ema_state = None self.message_count_state = None
>
> def open(self, runtime_context: RuntimeContext): """Initialize state
> descriptors with TTL.""" \# Configure TTL to clean up old state
> ttl_config = (
>
> StateTtlConfig.new_builder(Time.hours(24))
> .set_update_type(StateTtlConfig.UpdateType.OnReadAndWrite)
> .set_state_visibility(
>
> StateTtlConfig.StateVisibility.NeverReturnExpired )
>
> .build() )
>
> \# Last timestamp state
>
> last_ts_desc = ValueStateDescriptor( 'last_timestamp',
>
> Types.LONG() )
>
> last_ts_desc.enable_time_to_live(ttl_config) self.last_timestamp_state
> = runtime_context.get_state(last_ts_desc)
>
> \# Last price state
>
> last_price_desc = ValueStateDescriptor( 'last_price',
>
> Types.DOUBLE() )
>
> last_price_desc.enable_time_to_live(ttl_config) self.last_price_state
> = runtime_context.get_state(last_price_desc)
>
> \# Price EMA state (for anomaly detection) price_ema_desc =
> ValueStateDescriptor(
>
> 'price_ema', Types.DOUBLE()
>
> ) price_ema_desc.enable_time_to_live(ttl_config)
>
> self.price_ema_state = runtime_context.get_state(price_ema_desc)
>
> \# Volume EMA state
>
> volume_ema_desc = ValueStateDescriptor( 'volume_ema',
>
> Types.DOUBLE() )
>
> volume_ema_desc.enable_time_to_live(ttl_config) self.volume_ema_state
> = runtime_context.get_state(volume_ema_desc)
>
> \# Message count for rate limiting count_desc = ValueStateDescriptor(
>
> 'message_count', Types.LONG()
>
> )
>
> self.message_count_state = runtime_context.get_state(count_desc)
>
> Page 14 of 42 \| Confidential
>
> **HIMARI** **OPUS** **1** \| Production Infrastructure Guide
>
> def process_element(self, value, ctx):
>
> """Process each market data element and emit quality score.""" symbol,
> data = value
>
> if 'error' in data:
>
> yield self.\_create_quality_output(symbol, data, 0.0,
> \['PARSE_ERROR'\]) return
>
> quality_score = 1.0 issues = \[\]
>
> \# ========== CHECK 1: Schema Validation ========== if data\['price'\]
> \<= 0:
>
> quality_score -= 0.25 issues.append('INVALID_PRICE_NEGATIVE')
>
> if data\['volume'\] \< 0: quality_score -= 0.20
>
> issues.append('INVALID_VOLUME_NEGATIVE')
>
> \# ========== CHECK 2: Exchange Validation ========== if
> data\['exchange'\] not in VALID_EXCHANGES:
>
> quality_score -= 0.15 issues.append('UNKNOWN_EXCHANGE')
>
> \# ========== CHECK 3: Temporal Ordering ========== last_ts =
> self.last_timestamp_state.value() current_ts = data\['timestamp'\]
>
> if last_ts is not None:
>
> if current_ts \< last_ts: quality_score -= 0.30
> issues.append('OUT_OF_ORDER')
>
> elif current_ts == last_ts: quality_score -= 0.10
> issues.append('DUPLICATE_TIMESTAMP')
>
> elif current_ts - last_ts \> 60000: \# \>60 second gap quality_score
> -= 0.05 issues.append('LARGE_GAP')
>
> self.last_timestamp_state.update(current_ts)
>
> Page 15 of 42 \| Confidential
>
> **HIMARI** **OPUS** **1** \| Production Infrastructure Guide
>
> \# ========== CHECK 4: Price Deviation ========== last_price =
> self.last_price_state.value() price_ema = self.price_ema_state.value()
>
> if last_price is not None:
>
> pct_change = abs(data\['price'\] - last_price) / last_price if
> pct_change \> 0.10: \# \>10% single-tick move
>
> quality_score -= 0.20 issues.append('EXTREME_PRICE_MOVE')
>
> elif pct_change \> 0.05: \# \>5% move quality_score -= 0.05
> issues.append('LARGE_PRICE_MOVE')
>
> \# Update price EMA (alpha = 0.1) if price_ema is None:
>
> price_ema = data\['price'\] else:
>
> price_ema = 0.1 \* data\['price'\] + 0.9 \* price_ema
> self.price_ema_state.update(price_ema)
> self.last_price_state.update(data\['price'\])
>
> \# Check deviation from EMA if price_ema \> 0:
>
> ema_deviation = abs(data\['price'\] - price_ema) / price_ema if
> ema_deviation \> 0.15: \# \>15% from EMA
>
> quality_score -= 0.10 issues.append('PRICE_ANOMALY')
>
> \# ========== CHECK 5: Volume Validation ========== volume_ema =
> self.volume_ema_state.value()
>
> if volume_ema is None: volume_ema = data\['volume'\]
>
> else:
>
> volume_ema = 0.1 \* data\['volume'\] + 0.9 \* volume_ema
> self.volume_ema_state.update(volume_ema)
>
> if volume_ema \> 0:
>
> volume_ratio = data\['volume'\] / volume_ema if volume_ratio \> 100:
> \# 100x normal volume
>
> quality_score -= 0.15 issues.append('EXTREME_VOLUME_SPIKE')
>
> elif volume_ratio \> 10: \# 10x normal quality_score -= 0.05
> issues.append('VOLUME_SPIKE')
>
> \# ========== CHECK 6: Decimal Precision ========== price_str =
> str(data\['price'\])
>
> if '.' in price_str:
>
> decimals = len(price_str.split('.')\[1\])
>
> if decimals \> 8: \# More than 8 decimal places quality_score -= 0.05
> issues.append('EXCESSIVE_PRECISION')
>
> \# ========== CHECK 7: Timestamp Freshness ========== now_ms =
> int(datetime.utcnow().timestamp() \* 1000) latency_ms = now_ms -
> current_ts
>
> if latency_ms \> 30000: \# \>30 seconds old quality_score -= 0.15
> issues.append('STALE_DATA')
>
> elif latency_ms \> 10000: \# \>10 seconds old quality_score -= 0.05
> issues.append('DELAYED_DATA')
>
> elif latency_ms \< -5000: \# Future timestamp (\>5s) quality_score -=
> 0.20
>
> Page 16 of 42 \| Confidential
>
> **HIMARI** **OPUS** **1** \| Production Infrastructure Guide
>
> issues.append('FUTURE_TIMESTAMP')
>
> \# Clamp score to \[0, 1\]
>
> quality_score = max(0.0, min(1.0, quality_score))
>
> yield self.\_create_quality_output(symbol, data, quality_score,
> issues)
>
> def \_create_quality_output(self, symbol, data, score, issues):
> """Create standardized quality output."""
>
> return json.dumps({ 'symbol': symbol,
>
> 'timestamp': data.get('timestamp', 0), 'quality_score': round(score,
> 3), 'issues': issues,
>
> 'issue_count': len(issues),
>
> 'processed_at': datetime.utcnow().isoformat(), 'original_data':
> data.get('raw', {})
>
> })

**Main** **Pipeline** **Execution**

> \# ============================================================ \#
> MAIN PIPELINE
>
> \# ============================================================ def
> create_pipeline():
>
> """Create and configure the Flink pipeline."""
>
> \# Create execution environment
>
> env = StreamExecutionEnvironment.get_execution_environment()
> env.set_parallelism(4)
>
> \# Enable checkpointing env.enable_checkpointing(30000) \# 30 seconds
> config = env.get_checkpoint_config()
> config.set_checkpointing_mode('EXACTLY_ONCE')
> config.set_min_pause_between_checkpoints(10000)
> config.set_checkpoint_timeout(120000)
>
> \# Create Kafka source
>
> source = KafkaSource.builder() \\
> .set_bootstrap_servers(KAFKA_BOOTSTRAP) \\
> .set_topics('raw_market_data') \\
> .set_group_id('himari-quality-processor') \\
>
> .set_starting_offsets(KafkaOffsetsInitializer.earliest()) \\
> .set_value_only_deserializer(SimpleStringSchema()) \\
> .set_property('security.protocol', 'SASL_PLAINTEXT') \\
> .set_property('sasl.mechanism', 'SCRAM-SHA-256') \\
> .set_property('sasl.jaas.config',
>
> f'org.apache.kafka.common.security.scram.ScramLoginModule ' f'required
> username="{KAFKA_USER}" password="{KAFKA_PASSWORD}";') \\
>
> .build()
>
> \# Create Kafka sink
>
> sink = KafkaSink.builder() \\ .set_bootstrap_servers(KAFKA_BOOTSTRAP)
> \\ .set_record_serializer(
>
> KafkaRecordSerializationSchema.builder() .set_topic('quality_scores')
> .set_value_serialization_schema(SimpleStringSchema()) .build()
>
> ) \\
>
> .set_property('security.protocol', 'SASL_PLAINTEXT') \\
> .set_property('sasl.mechanism', 'SCRAM-SHA-256') \\ .build()
>
> Page 17 of 42 \| Confidential
>
> **HIMARI** **OPUS** **1** \| Production Infrastructure Guide
>
> \# Build pipeline
>
> stream = env.from_source( source,
>
> WatermarkStrategy.no_watermarks(), 'kafka-source'
>
> )
>
> stream \\ .map(ParseMarketData()) \\ .key_by(lambda x: x\[0\]) \\
>
> .process(QualityValidationOperator()) \\ .sink_to(sink)
>
> return env

if \_\_name\_\_ == '\_\_main\_\_': env = create_pipeline()

> env.execute('HIMARI Quality Validation Pipeline')
>
> Page 18 of 42 \| Confidential
>
> **HIMARI** **OPUS** **1** \| Production Infrastructure Guide

**Part** **IV:** **Redis** **Feature** **Store**

Redis provides sub-10ms feature serving for real-time trading
strategies. For cost-optimized deployments, self-hosting Redis on the
Flink server eliminates network latency and reduces costs.

> ⚠**Memory** **Sizing**
>
> A 512MB managed Redis instance is insufficient for production
> workloads. Self-hosting allows allocation of 2-4GB for Redis, which
> provides headroom for feature caching without eviction pressure.

**Self-Hosted** **Redis** **Configuration**

Deploy Redis on the Flink server to eliminate network latency between
feature computation and storage:

> \# Install Redis on the Flink server apt-get install -y redis-server
>
> \# Configure Redis for production cat \> /etc/redis/redis.conf \<\<
> 'EOF' \# Network
>
> bind 127.0.0.1 port 6379 protected-mode yes
>
> requirepass \<strong-redis-password\>
>
> \# Memory (2GB max, leave room for Flink) maxmemory 2gb
>
> maxmemory-policy volatile-lru
>
> \# Persistence (AOF for durability) appendonly yes
>
> appendfsync everysec
>
> auto-aof-rewrite-percentage 100 auto-aof-rewrite-min-size 64mb
>
> \# Performance tcp-keepalive 300 timeout 0
>
> tcp-backlog 511
>
> \# Logging loglevel notice
>
> logfile /var/log/redis/redis-server.log
>
> \# Snapshotting (backup every 15 minutes if 100+ changes) save 900 100
>
> save 300 1000 save 60 10000
>
> dbfilename dump.rdb dir /var/lib/redis EOF
>
> \# Optimize system for Redis
>
> echo 'vm.overcommit_memory = 1' \>\> /etc/sysctl.conf echo
> 'net.core.somaxconn = 65535' \>\> /etc/sysctl.conf sysctl -p
>
> \# Start Redis
>
> systemctl enable redis-server systemctl restart redis-server
>
> Page 19 of 42 \| Confidential
>
> **HIMARI** **OPUS** **1** \| Production Infrastructure Guide
>
> \# Verify
>
> redis-cli -a '\<password\>' ping \# Should return PONG

**Feature** **Store** **Sink** **(Flink** **Integration)**

> \# redis_sink.py
>
> \# High-performance Redis sink for Flink feature materialization
>
> import redis import json
>
> from datetime import datetime from typing import Dict, Any
>
> from pyflink.datastream.functions import SinkFunction
>
> class RedisFeatureSink(SinkFunction): """
>
> Write computed features to Redis with optimized batching. Uses
> connection pooling and pipelining for performance. """
>
> def \_\_init\_\_(self, host: str = '127.0.0.1', port: int = 6379,
> password: str = '', db: int = 0, batch_size: int = 100):
>
> self.host = host self.port = port self.password = password self.db =
> db
>
> self.batch_size = batch_size self.buffer = \[\]
>
> self.pool = None self.client = None
>
> def open(self, runtime_context): """Initialize Redis connection
> pool.""" self.pool = redis.ConnectionPool(
>
> host=self.host, port=self.port, password=self.password, db=self.db,
> max_connections=10, decode_responses=True, socket_timeout=5.0,
> socket_connect_timeout=5.0
>
> )
>
> self.client = redis.Redis(connection_pool=self.pool)
>
> \# Verify connection self.client.ping()
>
> def invoke(self, value: str, context):
>
> """Buffer and batch-write features to Redis."""
> self.buffer.append(value)
>
> if len(self.buffer) \>= self.batch_size: self.\_flush_buffer()
>
> def \_flush_buffer(self):
>
> """Flush buffer to Redis using pipeline.""" if not self.buffer:
>
> return
>
> try:
>
> pipe = self.client.pipeline()
>
> Page 20 of 42 \| Confidential
>
> **HIMARI** **OPUS** **1** \| Production Infrastructure Guide
>
> for item in self.buffer: data = json.loads(item) symbol =
> data\['symbol'\]
>
> timestamp = data\['timestamp'\]
>
> \# Latest feature (always overwritten) latest_key =
> f"features:{symbol}:latest"
>
> pipe.set(latest_key, item, ex=3600) \# 1 hour TTL
>
> \# Time-indexed for lookups (sorted set) history_key =
> f"features:{symbol}:history" pipe.zadd(history_key, {item: timestamp})
>
> \# Trim history to last 1000 entries pipe.zremrangebyrank(history_key,
> 0, -1001)
>
> pipe.execute() self.buffer.clear()
>
> except redis.RedisError as e:
>
> \# Log error but don't crash - will retry on next batch print(f"Redis
> write error: {e}")
>
> def close(self):
>
> """Flush remaining buffer and close connections."""
> self.\_flush_buffer()
>
> if self.pool: self.pool.disconnect()
>
> Page 21 of 42 \| Confidential
>
> **HIMARI** **OPUS** **1** \| Production Infrastructure Guide
>
> **Part** **V:** **TimescaleDB** **Analytics**
>
> TimescaleDB extends PostgreSQL with time-series optimizations
> including automatic partitioning (hypertables), continuous aggregates,
> and compression. These features provide 8-10x query speedup for
> analytical workloads.
>
> **Server** **Provisioning**
>
> Deploy TimescaleDB on a dedicated VPS for isolation. A small instance
> is sufficient for analytics workloads:

||
||
||
||
||
||
||

> **Installation**
>
> \# Install PostgreSQL 16 + TimescaleDB
>
> apt-get install -y gnupg postgresql-common apt-transport-https
> lsb-release
>
> \# Add TimescaleDB repository
>
> echo "deb https://packagecloud.io/timescale/timescaledb/ubuntu/
> \$(lsb_release -c -s) main" \| \\
>
> tee /etc/apt/sources.list.d/timescaledb.list
>
> wget --quiet -O - https://packagecloud.io/timescale/timescaledb/gpgkey
> \| apt-key add -
>
> \# Install
>
> apt-get update
>
> apt-get install -y timescaledb-2-postgresql-16
>
> \# Run tuning script timescaledb-tune --yes
>
> \# Restart PostgreSQL systemctl restart postgresql
>
> \# Enable TimescaleDB extension
>
> sudo -u postgres psql -c "CREATE EXTENSION IF NOT EXISTS timescaledb
> CASCADE;"
>
> **Database** **Schema**
>
> -- Connect to PostgreSQL -- sudo -u postgres psql
>
> -- Create HIMARI database
>
> CREATE DATABASE himari_analytics; \c himari_analytics
>
> -- Enable TimescaleDB
>
> CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;
>
> -- ============================================================ --
> MARKET DATA HYPERTABLE
>
> -- ============================================================ CREATE
> TABLE market_data (
>
> timestamp TIMESTAMPTZ NOT NULL,
>
> Page 22 of 42 \| Confidential
>
> **HIMARI** **OPUS** **1** \| Production Infrastructure Guide
>
> symbol exchange price volume
>
> quality_score issues

TEXT NOT NULL, TEXT NOT NULL,

DOUBLE PRECISION NOT NULL, DOUBLE PRECISION NOT NULL, REAL NOT NULL,

TEXT\[\],

> -- Constraints
>
> CONSTRAINT valid_price CHECK (price \> 0),

CONSTRAINT valid_score CHECK (quality_score \>= 0 AND quality_score
\<= 1) );

-- Convert to hypertable (auto-partitioned by time) SELECT
create_hypertable(

> 'market_data', 'timestamp',
>
> chunk_time_interval =\> INTERVAL '1 day', if_not_exists =\> TRUE

);

-- Create indexes for common queries

CREATE INDEX idx_market_symbol_time ON market_data (symbol, timestamp
DESC); CREATE INDEX idx_market_exchange_time ON market_data (exchange,
timestamp DESC); CREATE INDEX idx_market_quality ON market_data
(quality_score)

> WHERE quality_score \< 0.7; -- Partial index for bad data
>
> Page 23 of 42 \| Confidential
>
> **HIMARI** **OPUS** **1** \| Production Infrastructure Guide

**Continuous** **Aggregates** **(8x** **Query** **Speedup)**

> -- ============================================================ --
> 5-MINUTE OHLCV CONTINUOUS AGGREGATE
>
> -- ============================================================ CREATE
> MATERIALIZED VIEW ohlcv_5min
>
> WITH (timescaledb.continuous) AS SELECT
>
> time_bucket('5 minutes', timestamp) AS bucket, symbol,
>
> exchange,
>
> FIRST(price, timestamp) AS open, MAX(price) AS high,
>
> MIN(price) AS low,
>
> LAST(price, timestamp) AS close, SUM(volume) AS volume,
>
> COUNT(\*) AS trade_count, AVG(quality_score) AS avg_quality, --
> Additional analytics STDDEV(price) AS price_stddev,
>
> MAX(price) - MIN(price) AS price_range FROM market_data
>
> GROUP BY bucket, symbol, exchange WITH NO DATA;
>
> -- Auto-refresh policy (run every minute, process last 2 hours) SELECT
> add_continuous_aggregate_policy(
>
> 'ohlcv_5min',
>
> start_offset =\> INTERVAL '2 hours', end_offset =\> INTERVAL '1
> minute', schedule_interval =\> INTERVAL '1 minute'
>
> );
>
> -- ============================================================ --
> 1-HOUR OHLCV AGGREGATE
>
> -- ============================================================ CREATE
> MATERIALIZED VIEW ohlcv_1hour
>
> WITH (timescaledb.continuous) AS SELECT
>
> time_bucket('1 hour', timestamp) AS bucket, symbol,
>
> exchange,
>
> FIRST(price, timestamp) AS open, MAX(price) AS high,
>
> MIN(price) AS low,
>
> LAST(price, timestamp) AS close, SUM(volume) AS volume,
>
> COUNT(\*) AS trade_count, AVG(quality_score) AS avg_quality
>
> FROM market_data
>
> GROUP BY bucket, symbol, exchange WITH NO DATA;
>
> SELECT add_continuous_aggregate_policy( 'ohlcv_1hour',
>
> start_offset =\> INTERVAL '3 hours', end_offset =\> INTERVAL '1 hour',
> schedule_interval =\> INTERVAL '30 minutes'
>
> );
>
> -- ============================================================ --
> COMPRESSION (for data older than 90 days)
>
> -- ============================================================ ALTER
> TABLE market_data SET (
>
> timescaledb.compress, timescaledb.compress_segmentby = 'symbol,
> exchange', timescaledb.compress_orderby = 'timestamp DESC'
>
> Page 24 of 42 \| Confidential
>
> **HIMARI** **OPUS** **1** \| Production Infrastructure Guide
>
> );
>
> SELECT add_compression_policy( 'market_data',
>
> compress_after =\> INTERVAL '90 days' );
>
> -- ============================================================ --
> RETENTION POLICY (delete data older than 1 year)
>
> -- ============================================================ SELECT
> add_retention_policy(
>
> 'market_data',
>
> drop_after =\> INTERVAL '365 days' );

**TimescaleDB** **Sink** **(Flink** **Integration)**

> \# timescale_sink.py
>
> \# Batch-optimized TimescaleDB sink for analytics
>
> import psycopg2
>
> from psycopg2 import pool
>
> from psycopg2.extras import execute_values import json
>
> from datetime import datetime from typing import List
>
> from pyflink.datastream.functions import SinkFunction
>
> class TimescaleDBSink(SinkFunction): """
>
> Write features to TimescaleDB with batched inserts.
>
> Uses connection pooling and execute_values for performance. """
>
> def \_\_init\_\_(self, host: str, database: str, user: str,
>
> password: str, port: int = 5432, batch_size: int = 500): self.host =
> host
>
> self.database = database self.user = user self.password = password
> self.port = port self.batch_size = batch_size self.buffer:
> List\[tuple\] = \[\] self.conn_pool = None
>
> def open(self, runtime_context): """Initialize connection pool."""
>
> self.conn_pool = pool.ThreadedConnectionPool( minconn=2,
>
> maxconn=10, host=self.host, port=self.port, database=self.database,
> user=self.user, password=self.password, connect_timeout=10
>
> )
>
> def invoke(self, value: str, context):
>
> """Buffer records and batch-insert to TimescaleDB.""" try:
>
> data = json.loads(value)
>
> \# Convert to tuple for batch insert
>
> Page 25 of 42 \| Confidential
>
> **HIMARI** **OPUS** **1** \| Production Infrastructure Guide
>
> record = (
>
> datetime.fromtimestamp(data\['timestamp'\] / 1000.0),
> data\['symbol'\],
>
> data.get('exchange', 'unknown'), data.get('price', 0.0),
> data.get('volume', 0.0), data.get('quality_score', 1.0),
> data.get('issues', \[\])
>
> ) self.buffer.append(record)
>
> if len(self.buffer) \>= self.batch_size: self.\_flush_buffer()
>
> except Exception as e: print(f"TimescaleDB sink error: {e}")
>
> def \_flush_buffer(self):
>
> """Batch insert to TimescaleDB using execute_values.""" if not
> self.buffer:
>
> return
>
> conn = None try:
>
> conn = self.conn_pool.getconn() cursor = conn.cursor()
>
> \# Batch insert with execute_values (10x faster than executemany)
> execute_values(
>
> cursor, """
>
> INSERT INTO market_data
>
> (timestamp, symbol, exchange, price, volume, quality_score, issues)
>
> VALUES %s
>
> ON CONFLICT DO NOTHING """,
>
> self.buffer,
>
> template="(%s, %s, %s, %s, %s, %s, %s)" )
>
> conn.commit() self.buffer.clear()
>
> except Exception as e: if conn:
>
> conn.rollback()
>
> print(f"TimescaleDB batch insert error: {e}")
>
> finally:
>
> if conn: self.conn_pool.putconn(conn)
>
> def close(self):
>
> """Flush remaining buffer and close pool.""" self.\_flush_buffer()
>
> if self.conn_pool: self.conn_pool.closeall()
>
> Page 26 of 42 \| Confidential
>
> **HIMARI** **OPUS** **1** \| Production Infrastructure Guide

**Part** **VI:** **Neo4j** **Knowledge** **Graph**

Neo4j provides the causal knowledge graph for understanding market event
relationships. The graph stores entities (exchanges, assets, wallets)
and their causal connections (whale transfers, liquidation cascades).

**Deployment** **Options**

For budget-optimized deployments, deploy Neo4j on the Flink server using
Docker:

||
||
||
||

**Graph** **Schema** **Initialization**

> // Execute in Neo4j Browser or via cypher-shell // cypher-shell -u
> neo4j -p \<password\>
>
> // ============================================================ //
> CONSTRAINTS AND INDEXES
>
> // ============================================================ CREATE
> CONSTRAINT exchange_name IF NOT EXISTS
>
> FOR (e:Exchange) REQUIRE e.name IS UNIQUE;
>
> CREATE CONSTRAINT asset_symbol IF NOT EXISTS FOR (a:Asset) REQUIRE
> a.symbol IS UNIQUE;
>
> CREATE CONSTRAINT pair_symbol IF NOT EXISTS FOR (p:Pair) REQUIRE
> p.symbol IS UNIQUE;
>
> CREATE CONSTRAINT wallet_address IF NOT EXISTS FOR (w:Wallet) REQUIRE
> w.address IS UNIQUE;
>
> CREATE INDEX cascade_timestamp IF NOT EXISTS FOR (c:CascadeEvent) ON
> (c.timestamp);
>
> CREATE INDEX transfer_timestamp IF NOT EXISTS FOR (t:WhaleTransfer) ON
> (t.timestamp);
>
> Page 27 of 42 \| Confidential
>
> **HIMARI** **OPUS** **1** \| Production Infrastructure Guide
>
> // ============================================================ //
> INITIAL ENTITIES
>
> // ============================================================ //
> Exchanges
>
> MERGE (binance:Exchange {name: 'binance'})
>
> SET binance.id = 'EX_BINANCE', binance.created_at = datetime();
>
> MERGE (kraken:Exchange {name: 'kraken'})
>
> SET kraken.id = 'EX_KRAKEN', kraken.created_at = datetime();
>
> MERGE (bybit:Exchange {name: 'bybit'})
>
> SET bybit.id = 'EX_BYBIT', bybit.created_at = datetime();
>
> // Assets
>
> MERGE (btc:Asset {symbol: 'BTC'})
>
> SET btc.id = 'ASSET_BTC', btc.name = 'Bitcoin';
>
> MERGE (eth:Asset {symbol: 'ETH'})
>
> SET eth.id = 'ASSET_ETH', eth.name = 'Ethereum';
>
> MERGE (usdt:Asset {symbol: 'USDT'})
>
> SET usdt.id = 'ASSET_USDT', usdt.name = 'Tether';
>
> // Trading Pairs
>
> MERGE (btc_usdt:Pair {symbol: 'BTC/USDT'}) SET btc_usdt.id =
> 'PAIR_BTCUSDT';
>
> MERGE (eth_usdt:Pair {symbol: 'ETH/USDT'}) SET eth_usdt.id =
> 'PAIR_ETHUSDT';
>
> // Relationships
>
> MATCH (btc_usdt:Pair {symbol: 'BTC/USDT'}) MATCH (btc:Asset {symbol:
> 'BTC'})
>
> MATCH (usdt:Asset {symbol: 'USDT'}) MERGE
> (btc_usdt)-\[:BASE_ASSET\]-\>(btc) MERGE
> (btc_usdt)-\[:QUOTE_ASSET\]-\>(usdt);
>
> MATCH (binance:Exchange), (btc_usdt:Pair {symbol: 'BTC/USDT'}) MERGE
> (binance)-\[:LISTS\]-\>(btc_usdt);

**Causal** **Event** **Queries**

The following Cypher queries extract causal chains for cognitive layer
analysis:

> // Query 1: Find whale transfers preceding price drops
>
> MATCH
> (w:Wallet)-\[:TRANSFERRED\]-\>(t:WhaleTransfer)-\[:TO\]-\>(e:Exchange)
> WHERE t.timestamp \> datetime() - duration('P1D')
>
> AND t.amount \> 100 // BTC threshold WITH w, t, e
>
> MATCH (pm:PriceMovement)-\[:ON_PAIR\]-\>(:Pair {symbol: 'BTC/USDT'})
> WHERE pm.timestamp \> t.timestamp
>
> AND pm.timestamp \< t.timestamp + duration('PT1H') AND
> pm.change_percent \< -0.02 // 2% drop
>
> RETURN w.address AS whale,
>
> t.amount AS transfer_amount, t.timestamp AS transfer_time,
> pm.change_percent AS price_change, pm.timestamp AS price_time
>
> ORDER BY t.timestamp DESC LIMIT 20;
>
> // Query 2: Identify liquidation cascade patterns MATCH
> (c:CascadeEvent)-\[:ON_PAIR\]-\>(p:Pair) WHERE c.timestamp \>
> datetime() - duration('P7D')
>
> Page 28 of 42 \| Confidential
>
> **HIMARI** **OPUS** **1** \| Production Infrastructure Guide

AND c.severity IN \['high', 'critical'\] WITH c, p

MATCH (prev:CascadeEvent)-\[:ON_PAIR\]-\>(p) WHERE prev.timestamp \<
c.timestamp

AND prev.timestamp \> c.timestamp - duration('PT1H') RETURN p.symbol AS
pair,

> c.timestamp AS cascade_time, c.severity AS severity,
>
> c.total_liquidation_value AS liquidation_value, COUNT(prev) AS
> preceding_cascades

ORDER BY c.timestamp DESC;

// Query 3: Build causal chain for specific event MATCH path =
(trigger)-\[\*1..5\]-\>(effect:CascadeEvent) WHERE effect.id =
\$event_id

RETURN path;

> Page 29 of 42 \| Confidential
>
> **HIMARI** **OPUS** **1** \| Production Infrastructure Guide

**Part** **VII:** **Monitoring** **and** **Observability**

Production systems require comprehensive monitoring to detect issues
before they impact trading operations. This section covers a zero-cost
monitoring stack using Prometheus and Grafana Cloud Free Tier.

**Prometheus** **Setup**

> \# Install Prometheus on the Flink server cd /opt
>
> wget
> https://github.com/prometheus/prometheus/releases/download/v2.48.0/prometheus-2.48.0.linux-amd64.tar.gz
>
> tar -xzf prometheus-2.48.0.linux-amd64.tar.gz mv
> prometheus-2.48.0.linux-amd64 prometheus rm
> prometheus-2.48.0.linux-amd64.tar.gz
>
> \# Create configuration
>
> cat \> /opt/prometheus/prometheus.yml \<\< 'EOF' global:
>
> scrape_interval: 15s evaluation_interval: 15s
>
> scrape_configs:
>
> \# Prometheus self-monitoring - job_name: 'prometheus'
>
> static_configs:
>
> \- targets: \['localhost:9090'\]
>
> \# Flink metrics
>
> \- job_name: 'flink' static_configs:
>
> \- targets: \['localhost:9249'\] metrics_path: /metrics
>
> \# Redis metrics (requires redis_exporter) - job_name: 'redis'
>
> static_configs:
>
> \- targets: \['localhost:9121'\]
>
> \# Node metrics (system health) - job_name: 'node'
>
> static_configs:
>
> \- targets: \['localhost:9100'\]
>
> \# Redpanda metrics
>
> \- job_name: 'redpanda' static_configs:
>
> \- targets: \['\<redpanda-ip\>:9644'\] metrics_path: /public_metrics
>
> EOF
>
> \# Create systemd service
>
> cat \> /etc/systemd/system/prometheus.service \<\< 'EOF' \[Unit\]
>
> Description=Prometheus After=network.target
>
> \[Service\] User=root
>
> ExecStart=/opt/prometheus/prometheus \\
>
> --config.file=/opt/prometheus/prometheus.yml \\
> --storage.tsdb.path=/data/prometheus \\
>
> --storage.tsdb.retention.time=15d \\
>
> Page 30 of 42 \| Confidential
>
> **HIMARI** **OPUS** **1** \| Production Infrastructure Guide
>
> --web.listen-address=127.0.0.1:9090 Restart=always
>
> \[Install\]
>
> WantedBy=multi-user.target EOF
>
> mkdir -p /data/prometheus systemctl daemon-reload systemctl enable
> prometheus systemctl start prometheus

**Node** **Exporter** **(System** **Metrics)**

> \# Install Node Exporter for system metrics cd /opt
>
> wget
> https://github.com/prometheus/node_exporter/releases/download/v1.7.0/node_exporter-1.7.0.linux-amd64.tar.gz
>
> tar -xzf node_exporter-1.7.0.linux-amd64.tar.gz
>
> mv node_exporter-1.7.0.linux-amd64/node_exporter /usr/local/bin/
>
> \# Create systemd service
>
> cat \> /etc/systemd/system/node_exporter.service \<\< 'EOF' \[Unit\]
>
> Description=Node Exporter After=network.target
>
> \[Service\] User=root
>
> ExecStart=/usr/local/bin/node_exporter \\
> --web.listen-address=127.0.0.1:9100
>
> Restart=always
>
> \[Install\]
>
> WantedBy=multi-user.target EOF
>
> systemctl daemon-reload systemctl enable node_exporter systemctl start
> node_exporter

**Grafana** **Cloud** **Integration** **(Free** **Tier)**

Grafana Cloud Free Tier provides 10,000 series, 14-day retention, and
hosted dashboards at no cost:

> 1\. Sign up at grafana.com/products/cloud (free tier) 2. Create a
> Grafana Cloud stack
>
> 3\. Go to Connections and select Prometheus 4. Copy the remote_write
> configuration
>
> 5\. Add to prometheus.yml and restart Prometheus
>
> \# Add to /opt/prometheus/prometheus.yml remote_write:
>
> \- url: https://prometheus-prod-XX-prod-XX.grafana.net/api/prom/push
> basic_auth:
>
> username: \<your-grafana-cloud-user-id\> password:
> \<your-grafana-cloud-api-key\>
>
> \# Restart Prometheus systemctl restart prometheus
>
> Page 31 of 42 \| Confidential
>
> **HIMARI** **OPUS** **1** \| Production Infrastructure Guide

**Critical** **Alerts**

Configure alerting rules for critical system health indicators:

> \# /opt/prometheus/alert_rules.yml groups:
>
> \- name: himari_critical rules:
>
> \# High memory usage
>
> \- alert: HighMemoryUsage
>
> expr: (1 - node_memory_MemAvailable_bytes /
> node_memory_MemTotal_bytes) \> 0.9 for: 5m
>
> labels:
>
> severity: critical annotations:
>
> summary: "Memory usage above 90%"
>
> \# Flink job failure
>
> \- alert: FlinkJobFailed
>
> expr: flink_jobmanager_job_numRunningJobs == 0 for: 2m
>
> labels:
>
> severity: critical annotations:
>
> summary: "No Flink jobs running"
>
> \# High checkpoint duration - alert: SlowCheckpoints
>
> expr: flink_jobmanager_job_lastCheckpointDuration \> 60000 for: 5m
>
> labels:
>
> severity: warning annotations:
>
> summary: "Checkpoint taking \>60 seconds"
>
> \# Redis memory pressure - alert: RedisMemoryHigh
>
> expr: redis_memory_used_bytes / redis_memory_max_bytes \> 0.85 for: 5m
>
> labels:
>
> severity: warning annotations:
>
> summary: "Redis memory above 85%"
>
> \# Kafka consumer lag
>
> \- alert: HighConsumerLag
>
> expr: kafka_consumergroup_lag \> 10000 for: 10m
>
> labels:
>
> severity: warning annotations:
>
> summary: "Kafka consumer lag \>10K messages"
>
> Page 32 of 42 \| Confidential
>
> **HIMARI** **OPUS** **1** \| Production Infrastructure Guide

**Part** **VIII:** **Security** **Hardening**

Production deployments handling financial data require comprehensive
security hardening. This section covers network isolation,
authentication, encryption, and secrets management.

> ⚠**Security** **is** **Non-Negotiable**
>
> Financial systems are high-value targets. Implement ALL security
> measures in this section before handling real trading data or
> connecting to production exchanges.

**Firewall** **Configuration**

> \# Install and configure UFW (Uncomplicated Firewall) apt-get install
> -y ufw
>
> \# Default policies
>
> ufw default deny incoming ufw default allow outgoing
>
> \# Allow SSH (with rate limiting) ufw limit ssh
>
> \# Allow internal cluster communication (replace with your private
> IPs) ufw allow from 10.0.0.0/24 to any port 9092 \# Kafka
>
> ufw allow from 10.0.0.0/24 to any port 6123 \# Flink RPC ufw allow
> from 10.0.0.0/24 to any port 5432 \# PostgreSQL
>
> \# Block all external access to services \# (Access via SSH tunnel
> only)
>
> \# Enable firewall ufw enable
>
> ufw status verbose

**Secrets** **Management**

Never store secrets in environment variables, shell history, or code.
Use encrypted secrets files:

> \# Install SOPS for encrypted secrets
>
> wget
> https://github.com/getsops/sops/releases/download/v3.8.1/sops-v3.8.1.linux.amd64
> mv sops-v3.8.1.linux.amd64 /usr/local/bin/sops
>
> chmod +x /usr/local/bin/sops
>
> \# Generate age key pair (modern replacement for GPG) apt-get install
> -y age
>
> age-keygen -o /root/.config/sops/age/keys.txt
>
> \# Create secrets file
>
> cat \> /opt/himari/secrets.yaml \<\< 'EOF' kafka:
>
> user: himari-producer password: \<your-kafka-password\>
>
> redis:
>
> password: \<your-redis-password\> postgres:
>
> user: himari
>
> password: \<your-postgres-password\> neo4j:
>
> user: neo4j
>
> password: \<your-neo4j-password\>
>
> Page 33 of 42 \| Confidential
>
> **HIMARI** **OPUS** **1** \| Production Infrastructure Guide
>
> EOF
>
> \# Encrypt with SOPS
>
> export SOPS_AGE_RECIPIENTS=\$(age-keygen -y
> /root/.config/sops/age/keys.txt) sops -e -i /opt/himari/secrets.yaml
>
> \# Verify encryption
>
> cat /opt/himari/secrets.yaml \# Should show encrypted values
>
> \# Decrypt at runtime
>
> sops -d /opt/himari/secrets.yaml

**TLS/SSL** **Configuration**

> \# Generate self-signed certificates for internal communication mkdir
> -p /opt/himari/certs
>
> cd /opt/himari/certs
>
> \# Generate CA
>
> openssl genrsa -out ca.key 4096
>
> openssl req -new -x509 -days 3650 -key ca.key -out ca.crt \\ -subj
> "/CN=HIMARI Internal CA"
>
> \# Generate server certificate openssl genrsa -out server.key 2048
>
> openssl req -new -key server.key -out server.csr \\ -subj
> "/CN=himari-cluster"
>
> \# Sign with CA
>
> openssl x509 -req -days 365 -in server.csr -CA ca.crt -CAkey ca.key \\
> -CAcreateserial -out server.crt
>
> \# Set permissions chmod 600 \*.key chmod 644 \*.crt
>
> \# Configure Redpanda TLS
>
> \# Add to /etc/redpanda/redpanda.yaml: \# kafka_api_tls:
>
> \# enabled: true
>
> \# cert_file: /opt/himari/certs/server.crt \# key_file:
> /opt/himari/certs/server.key

**SSH** **Hardening**

> \# /etc/ssh/sshd_config additions
>
> \# Disable password authentication PasswordAuthentication no
> ChallengeResponseAuthentication no
>
> \# Only allow specific users AllowUsers deploy admin
>
> \# Disable root login PermitRootLogin no
>
> \# Use strong ciphers only
>
> Ciphers aes256-gcm@openssh.com,chacha20-poly1305@openssh.com MACs
> hmac-sha2-512-etm@openssh.com,hmac-sha2-256-etm@openssh.com
>
> Page 34 of 42 \| Confidential
>
> **HIMARI** **OPUS** **1** \| Production Infrastructure Guide

\# Idle timeout ClientAliveInterval 300 ClientAliveCountMax 2

\# Restart SSH systemctl restart sshd

> Page 35 of 42 \| Confidential
>
> **HIMARI** **OPUS** **1** \| Production Infrastructure Guide
>
> **Part** **IX:** **Disaster** **Recovery**
>
> Achieving 99.99% availability requires comprehensive disaster recovery
> planning. This section covers backup strategies, failover procedures,
> and recovery time objectives.
>
> **Recovery** **Objectives**

||
||
||
||
||
||
||

> **Backup** **Strategy**
>
> \#!/bin/bash
>
> \# /opt/himari/scripts/backup.sh
>
> \# Automated backup script - run via cron every 6 hours
>
> set -e
>
> BACKUP_DIR="/data/backups/\$(date +%Y%m%d\_%H%M%S)"
> S3_BUCKET="s3://himari-backups"
>
> mkdir -p \$BACKUP_DIR
>
> \# 1. Backup TimescaleDB
>
> echo "Backing up TimescaleDB..."
>
> pg_dump -h localhost -U himari -d himari_analytics \\ --format=custom
> --compress=9 \\
>
> \> \$BACKUP_DIR/timescaledb.dump
>
> \# 2. Backup Redis (RDB snapshot) echo "Backing up Redis..." redis-cli
> -a '\<password\>' BGSAVE sleep 5 \# Wait for snapshot
>
> cp /var/lib/redis/dump.rdb \$BACKUP_DIR/redis.rdb
>
> \# 3. Backup Neo4j
>
> echo "Backing up Neo4j..."
>
> docker exec neo4j-himari neo4j-admin database dump neo4j \\
> --to-path=/backups/
>
> docker cp neo4j-himari:/backups/neo4j.dump \$BACKUP_DIR/
>
> \# 4. Backup configurations
>
> echo "Backing up configurations..." tar -czf
> \$BACKUP_DIR/configs.tar.gz \\
>
> /opt/flink/conf/ \\ /etc/redpanda/ \\ /etc/redis/ \\ /opt/prometheus/
>
> \# 5. Upload to S3
>
> echo "Uploading to S3..."
>
> aws s3 sync \$BACKUP_DIR \$S3_BUCKET/\$(basename \$BACKUP_DIR)/ \\
> --storage-class STANDARD_IA
>
> \# 6. Cleanup old local backups (keep 3 days)
>
> find /data/backups -type d -mtime +3 -exec rm -rf {} +
>
> Page 36 of 42 \| Confidential
>
> **HIMARI** **OPUS** **1** \| Production Infrastructure Guide
>
> echo "Backup completed: \$BACKUP_DIR"

**Failover** **Procedure**

In the event of primary region failure, execute the following recovery
steps:

**Step** **1:** **Detect** **Failure** (Automatic, \<1 minute)

> Prometheus alerting detects service unavailability. Alert fires to
> on-call via PagerDuty/OpsGenie.

**Step** **2:** **Assess** **Impact** (Manual, 2-5 minutes)

> Verify failure scope (single service vs. full region). Check if
> automatic recovery is possible.

**Step** **3:** **Activate** **DR** **Region** (5-10 minutes)

> Update DNS to point to DR region. Start services from latest
> checkpoint/backup.

**Step** **4:** **Verify** **Recovery** (5 minutes)

> Run smoke tests. Verify data integrity. Confirm latency targets are
> met.
>
> \#!/bin/bash
>
> \# /opt/himari/scripts/failover.sh \# Execute DR failover
>
> set -e
>
> DR_REGION="\<dr-server-ip\>" PRIMARY_REGION="\<primary-server-ip\>"
>
> echo "Starting failover to DR region..."
>
> \# 1. Stop attempting to connect to failed primary echo "Updating
> service discovery..."
>
> sed -i "s/\$PRIMARY_REGION/\$DR_REGION/g" /etc/hosts
>
> \# 2. Restore from latest checkpoint
>
> echo "Restoring Flink from checkpoint..."
>
> LATEST_CHECKPOINT=\$(aws s3 ls s3://himari-checkpoints/flink/ \| tail
> -1 \| awk '{print \$4}') /opt/flink/bin/flink run -s
> s3://himari-checkpoints/flink/\$LATEST_CHECKPOINT \\
>
> /opt/himari/jobs/quality_pipeline.jar
>
> \# 3. Verify services
>
> echo "Verifying services..."
>
> curl -f http://localhost:8081/jobs \|\| exit 1 redis-cli ping \|\|
> exit 1
>
> psql -h localhost -U himari -c "SELECT 1" \|\| exit 1
>
> echo "Failover complete. DR region active."
>
> Page 37 of 42 \| Confidential
>
> **HIMARI** **OPUS** **1** \| Production Infrastructure Guide

**Part** **X:** **Verification** **and** **Testing**

Before moving to production, verify all components meet performance
targets through comprehensive integration testing.

**Integration** **Test** **Suite**

> \# test_integration.py
>
> \# Comprehensive integration tests for HIMARI infrastructure
>
> import pytest import time import json
>
> from datetime import datetime
>
> from kafka import KafkaProducer, KafkaConsumer import redis
>
> import psycopg2
>
> from neo4j import GraphDatabase
>
> class TestInfrastructure:
>
> """Integration tests for all infrastructure components."""
>
> @pytest.fixture(autouse=True) def setup(self):
>
> """Initialize connections to all services.""" \# Kafka/Redpanda
>
> self.producer = KafkaProducer( bootstrap_servers=\['localhost:9092'\],
> value_serializer=lambda v: json.dumps(v).encode()
>
> )
>
> self.consumer = KafkaConsumer( 'quality_scores',
> bootstrap_servers=\['localhost:9092'\],
>
> value_deserializer=lambda m: json.loads(m.decode()),
> auto_offset_reset='latest', consumer_timeout_ms=30000
>
> )
>
> \# Redis
>
> self.redis = redis.Redis(host='localhost', port=6379,
> password='\<password\>', decode_responses=True)
>
> \# PostgreSQL/TimescaleDB self.pg = psycopg2.connect(
>
> host='localhost', database='himari_analytics', user='himari',
> password='\<password\>'
>
> )
>
> \# Neo4j
>
> self.neo4j = GraphDatabase.driver( 'bolt://localhost:7687',
> auth=('neo4j', '\<password\>')
>
> )
>
> yield
>
> \# Cleanup self.producer.close() self.consumer.close() self.pg.close()
> self.neo4j.close()
>
> def test_end_to_end_latency(self):
>
> """Verify end-to-end latency is under 50ms."""
>
> Page 38 of 42 \| Confidential
>
> **HIMARI** **OPUS** **1** \| Production Infrastructure Guide
>
> test_msg = {
>
> 'timestamp': int(time.time() \* 1000), 'symbol': 'TEST/USDT',
>
> 'price': 100.0, 'volume': 10.0, 'exchange': 'binance'
>
> }
>
> start = time.time() self.producer.send('raw_market_data',
> value=test_msg) self.producer.flush()
>
> \# Wait for processed message for msg in self.consumer:
>
> if msg.value.get('symbol') == 'TEST/USDT': latency_ms = (time.time() -
> start) \* 1000
>
> assert latency_ms \< 50, f"Latency {latency_ms}ms \> 50ms target"
> print(f"✓ End-to-end latency: {latency_ms:.1f}ms")
>
> break
>
> def test_redis_latency(self):
>
> """Verify Redis serving latency is under 10ms.""" \# Write test data
>
> self.redis.set('test:latency', 'test_value')
>
> \# Measure read latency start = time.time_ns()
>
> value = self.redis.get('test:latency') latency_us = (time.time_ns() -
> start) / 1000
>
> assert value == 'test_value'
>
> assert latency_us \< 10000, f"Redis latency {latency_us}μs \> 10ms"
> print(f"✓ Redis latency: {latency_us:.0f}μs")
>
> def test_timescaledb_aggregates(self):
>
> """Verify continuous aggregates are computing.""" cursor =
> self.pg.cursor()
>
> cursor.execute("""
>
> SELECT COUNT(\*) FROM ohlcv_5min
>
> WHERE bucket \> NOW() - INTERVAL '1 hour' """)
>
> count = cursor.fetchone()\[0\]
>
> assert count \> 0, "No recent continuous aggregate data" print(f"✓
> TimescaleDB aggregates: {count} recent buckets")
>
> def test_neo4j_connectivity(self): """Verify Neo4j graph is
> accessible.""" with self.neo4j.session() as session:
>
> result = session.run("MATCH (e:Exchange) RETURN COUNT(e) as count")
> count = result.single()\['count'\]
>
> assert count \> 0, "No exchanges in Neo4j" print(f"✓ Neo4j
> connectivity: {count} exchanges")
>
> def test_checkpoint_recovery(self):
>
> """Verify checkpoints are being written to S3.""" import boto3
>
> s3 = boto3.client('s3')
>
> response = s3.list_objects_v2( Bucket='himari-checkpoints',
> Prefix='flink/',
>
> MaxKeys=1 )
>
> Page 39 of 42 \| Confidential
>
> **HIMARI** **OPUS** **1** \| Production Infrastructure Guide
>
> assert response.get('KeyCount', 0) \> 0, "No checkpoints in S3"
> print("✓ Checkpoint recovery: checkpoints present in S3")
>
> if \_\_name\_\_ == '\_\_main\_\_': pytest.main(\[\_\_file\_\_, '-v',
> '--tb=short'\])
>
> **Pre-Production** **Checklist**
>
> Complete all items before deploying to production:

||
||
||
||
||
||
||
||
||
||
||
||
||
||
||
||
||
||
||
||
||
||
||
||
||
||
||

> Page 40 of 42 \| Confidential
>
> **HIMARI** **OPUS** **1** \| Production Infrastructure Guide
>
> **Appendix:** **Alternative** **Platform** **Options**
>
> The following alternative platforms can be substituted while
> maintaining the same budget constraint. Choose based on operational
> preferences and regional availability.
>
> **Compute** **Alternatives**

||
||
||
||
||
||
||
||

> **Message** **Broker** **Alternatives**

||
||
||
||
||
||
||
||
||

> **Database** **Alternatives**

||
||
||
||
||
||
||
||

> **Object** **Storage** **Alternatives**

||
||
||
||
||
||
||
||

> Page 41 of 42 \| Confidential
>
> **HIMARI** **OPUS** **1** \| Production Infrastructure Guide
>
> — End of Document —
>
> **HIMARI** **OPUS** **1** **Production** **Infrastructure** **Guide**
> \| Version 2.0
>
> Page 42 of 42 \| Confidential
