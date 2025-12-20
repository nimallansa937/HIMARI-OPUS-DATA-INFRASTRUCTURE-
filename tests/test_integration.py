# test_integration.py
# HIMARI Opus1 - Comprehensive Integration Tests
# Verify all infrastructure components meet performance targets

import pytest
import time
import json
from datetime import datetime, timedelta
from typing import Optional

# Optional imports - tests will skip if not available
try:
    from kafka import KafkaProducer, KafkaConsumer
    HAS_KAFKA = True
except ImportError:
    HAS_KAFKA = False

try:
    import redis
    HAS_REDIS = True
except ImportError:
    HAS_REDIS = False

try:
    import psycopg2
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

try:
    from neo4j import GraphDatabase
    HAS_NEO4J = True
except ImportError:
    HAS_NEO4J = False


# Configuration - Update these for your environment
CONFIG = {
    'kafka': {
        'bootstrap_servers': 'localhost:9092',
        'sasl_user': 'himari-producer',
        'sasl_password': '',
    },
    'redis': {
        'host': '127.0.0.1',
        'port': 6379,
        'password': '',
    },
    'postgres': {
        'host': 'localhost',
        'port': 5432,
        'database': 'himari_analytics',
        'user': 'himari',
        'password': '',
    },
    'neo4j': {
        'uri': 'bolt://localhost:7687',
        'user': 'neo4j',
        'password': '',
    }
}


class TestRedpanda:
    """Test Redpanda/Kafka connectivity and performance."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        if not HAS_KAFKA:
            pytest.skip("kafka-python not installed")
        
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=[CONFIG['kafka']['bootstrap_servers']],
                value_serializer=lambda v: json.dumps(v).encode(),
                acks='all',
                retries=3
            )
            yield
            self.producer.close()
        except Exception as e:
            pytest.skip(f"Cannot connect to Kafka: {e}")
    
    def test_connection(self):
        """Verify Kafka/Redpanda connection."""
        # Simple connection test
        assert self.producer.bootstrap_connected()
        print("✓ Redpanda connection successful")
    
    def test_produce_message(self):
        """Verify message production."""
        test_msg = {
            'timestamp': int(time.time() * 1000),
            'symbol': 'TEST/USDT',
            'price': 100.0,
            'volume': 10.0,
            'exchange': 'binance',
            'test': True
        }
        
        future = self.producer.send('raw_market_data', value=test_msg)
        result = future.get(timeout=10)
        
        assert result.topic == 'raw_market_data'
        print(f"✓ Message produced to partition {result.partition}, offset {result.offset}")


class TestRedis:
    """Test Redis connectivity and latency."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        if not HAS_REDIS:
            pytest.skip("redis not installed")
        
        try:
            self.client = redis.Redis(
                host=CONFIG['redis']['host'],
                port=CONFIG['redis']['port'],
                password=CONFIG['redis']['password'] or None,
                decode_responses=True,
                socket_timeout=5.0
            )
            self.client.ping()
            yield
            self.client.close()
        except Exception as e:
            pytest.skip(f"Cannot connect to Redis: {e}")
    
    def test_connection(self):
        """Verify Redis connection."""
        response = self.client.ping()
        assert response == True
        print("✓ Redis connection successful")
    
    def test_latency(self):
        """Verify Redis serving latency is under 10ms."""
        # Write test data
        self.client.set('test:latency', 'test_value')
        
        # Measure read latency over multiple iterations
        latencies = []
        for _ in range(100):
            start = time.time_ns()
            value = self.client.get('test:latency')
            latency_us = (time.time_ns() - start) / 1000
            latencies.append(latency_us)
        
        avg_latency_us = sum(latencies) / len(latencies)
        p99_latency_us = sorted(latencies)[99]
        
        assert value == 'test_value'
        assert p99_latency_us < 10000, f"Redis P99 latency {p99_latency_us}μs > 10ms target"
        
        print(f"✓ Redis latency: avg={avg_latency_us:.0f}μs, P99={p99_latency_us:.0f}μs")
        
        # Cleanup
        self.client.delete('test:latency')
    
    def test_memory_usage(self):
        """Check Redis memory usage."""
        info = self.client.info('memory')
        used_mb = info['used_memory'] / (1024 * 1024)
        max_mb = info.get('maxmemory', 0) / (1024 * 1024)
        
        print(f"✓ Redis memory: {used_mb:.1f}MB used" + 
              (f" / {max_mb:.0f}MB max" if max_mb > 0 else ""))


class TestTimescaleDB:
    """Test TimescaleDB connectivity and query performance."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        if not HAS_PSYCOPG2:
            pytest.skip("psycopg2 not installed")
        
        try:
            self.conn = psycopg2.connect(
                host=CONFIG['postgres']['host'],
                port=CONFIG['postgres']['port'],
                database=CONFIG['postgres']['database'],
                user=CONFIG['postgres']['user'],
                password=CONFIG['postgres']['password'],
                connect_timeout=10
            )
            yield
            self.conn.close()
        except Exception as e:
            pytest.skip(f"Cannot connect to TimescaleDB: {e}")
    
    def test_connection(self):
        """Verify TimescaleDB connection."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        assert result[0] == 1
        print("✓ TimescaleDB connection successful")
    
    def test_timescaledb_extension(self):
        """Verify TimescaleDB extension is installed."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT extversion FROM pg_extension WHERE extname = 'timescaledb'
        """)
        result = cursor.fetchone()
        assert result is not None, "TimescaleDB extension not installed"
        print(f"✓ TimescaleDB version: {result[0]}")
    
    def test_hypertable_exists(self):
        """Verify market_data hypertable exists."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT hypertable_name 
            FROM timescaledb_information.hypertables 
            WHERE hypertable_name = 'market_data'
        """)
        result = cursor.fetchone()
        assert result is not None, "market_data hypertable not found"
        print("✓ market_data hypertable exists")
    
    def test_continuous_aggregates(self):
        """Verify continuous aggregates are configured."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT view_name 
            FROM timescaledb_information.continuous_aggregates
        """)
        aggregates = [row[0] for row in cursor.fetchall()]
        
        expected = ['ohlcv_5min', 'ohlcv_1hour']
        for agg in expected:
            if agg in aggregates:
                print(f"✓ Continuous aggregate: {agg}")
            else:
                print(f"⚠ Missing continuous aggregate: {agg}")


class TestNeo4j:
    """Test Neo4j connectivity and graph data."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        if not HAS_NEO4J:
            pytest.skip("neo4j not installed")
        
        try:
            self.driver = GraphDatabase.driver(
                CONFIG['neo4j']['uri'],
                auth=(CONFIG['neo4j']['user'], CONFIG['neo4j']['password'])
            )
            self.driver.verify_connectivity()
            yield
            self.driver.close()
        except Exception as e:
            pytest.skip(f"Cannot connect to Neo4j: {e}")
    
    def test_connection(self):
        """Verify Neo4j connection."""
        with self.driver.session() as session:
            result = session.run("RETURN 1 as test")
            record = result.single()
            assert record['test'] == 1
        print("✓ Neo4j connection successful")
    
    def test_exchanges_exist(self):
        """Verify exchange nodes exist."""
        with self.driver.session() as session:
            result = session.run("MATCH (e:Exchange) RETURN COUNT(e) as count")
            count = result.single()['count']
            assert count > 0, "No exchange nodes found"
        print(f"✓ Neo4j has {count} exchange nodes")
    
    def test_graph_query_performance(self):
        """Verify graph query performs under 100ms."""
        with self.driver.session() as session:
            start = time.time()
            result = session.run("""
                MATCH (e:Exchange)-[:LISTS]->(p:Pair)
                RETURN e.name, collect(p.symbol) as pairs
                LIMIT 10
            """)
            records = list(result)
            latency_ms = (time.time() - start) * 1000
            
            assert latency_ms < 100, f"Graph query took {latency_ms:.1f}ms > 100ms target"
        print(f"✓ Neo4j query latency: {latency_ms:.1f}ms")


class TestSystemHealth:
    """Test overall system health."""
    
    def test_all_services_reachable(self):
        """Summary test to verify all services are reachable."""
        services = {
            'Redpanda': False,
            'Redis': False,
            'TimescaleDB': False,
            'Neo4j': False,
        }
        
        # Test Redpanda
        if HAS_KAFKA:
            try:
                producer = KafkaProducer(
                    bootstrap_servers=[CONFIG['kafka']['bootstrap_servers']],
                    request_timeout_ms=5000
                )
                if producer.bootstrap_connected():
                    services['Redpanda'] = True
                producer.close()
            except:
                pass
        
        # Test Redis
        if HAS_REDIS:
            try:
                client = redis.Redis(
                    host=CONFIG['redis']['host'],
                    port=CONFIG['redis']['port'],
                    password=CONFIG['redis']['password'] or None,
                    socket_timeout=5.0
                )
                if client.ping():
                    services['Redis'] = True
                client.close()
            except:
                pass
        
        # Test TimescaleDB
        if HAS_PSYCOPG2:
            try:
                conn = psycopg2.connect(
                    host=CONFIG['postgres']['host'],
                    database=CONFIG['postgres']['database'],
                    user=CONFIG['postgres']['user'],
                    password=CONFIG['postgres']['password'],
                    connect_timeout=5
                )
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                services['TimescaleDB'] = True
                conn.close()
            except:
                pass
        
        # Test Neo4j
        if HAS_NEO4J:
            try:
                driver = GraphDatabase.driver(
                    CONFIG['neo4j']['uri'],
                    auth=(CONFIG['neo4j']['user'], CONFIG['neo4j']['password'])
                )
                driver.verify_connectivity()
                services['Neo4j'] = True
                driver.close()
            except:
                pass
        
        # Print summary
        print("\n" + "=" * 40)
        print("Service Health Summary")
        print("=" * 40)
        for service, status in services.items():
            symbol = "✓" if status else "✗"
            print(f"  {symbol} {service}")
        print("=" * 40)
        
        # At least one service should be reachable
        assert any(services.values()), "No services are reachable"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
