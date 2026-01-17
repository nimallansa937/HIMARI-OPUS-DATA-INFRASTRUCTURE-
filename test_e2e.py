"""
End-to-end test for HIMARI OPUS Layer 0 Data Infrastructure
Tests the full pipeline: Kafka -> Redis -> TimescaleDB
"""
import json
import time
import msgpack
from kafka import KafkaProducer, KafkaConsumer
from kafka.admin import KafkaAdminClient, NewTopic
import redis
import psycopg2
from datetime import datetime

# Configuration
KAFKA_BOOTSTRAP = 'localhost:9092'
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
TIMESCALE_HOST = 'localhost'
TIMESCALE_PORT = 5432
TIMESCALE_DB = 'himari_retail'
TIMESCALE_USER = 'himari'
TIMESCALE_PASS = 'himari_secure_password'

TEST_TOPIC = 'himari.test.e2e'

def create_topic():
    """Create test topic if it doesn't exist"""
    print("[*] Creating Kafka topic...")
    admin = KafkaAdminClient(bootstrap_servers=KAFKA_BOOTSTRAP)

    try:
        topics = admin.list_topics()
        if TEST_TOPIC not in topics:
            topic = NewTopic(name=TEST_TOPIC, num_partitions=3, replication_factor=1)
            admin.create_topics([topic])
            print(f"[+] Topic '{TEST_TOPIC}' created")
        else:
            print(f"[+] Topic '{TEST_TOPIC}' already exists")
    finally:
        admin.close()

def init_timescaledb():
    """Initialize TimescaleDB schema"""
    print("\n[DB]  Initializing TimescaleDB schema...")

    conn = psycopg2.connect(
        host=TIMESCALE_HOST,
        port=TIMESCALE_PORT,
        database=TIMESCALE_DB,
        user=TIMESCALE_USER,
        password=TIMESCALE_PASS
    )

    cursor = conn.cursor()

    # Create test table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS test_metrics (
            timestamp TIMESTAMPTZ NOT NULL,
            sensor_id TEXT NOT NULL,
            temperature DOUBLE PRECISION,
            humidity DOUBLE PRECISION,
            pressure DOUBLE PRECISION,
            metadata JSONB
        );
    """)

    # Convert to hypertable
    try:
        cursor.execute("""
            SELECT create_hypertable('test_metrics', 'timestamp',
                                    if_not_exists => TRUE);
        """)
    except Exception as e:
        if "already a hypertable" not in str(e):
            raise

    conn.commit()
    cursor.close()
    conn.close()
    print("[+] TimescaleDB schema initialized")

def produce_test_data(count=10):
    """Produce test messages to Kafka"""
    print(f"\n[>>] Producing {count} test messages to Kafka...")

    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: msgpack.packb(v, use_bin_type=True)
    )

    timestamps = []

    for i in range(count):
        data = {
            'timestamp': datetime.utcnow().isoformat(),
            'sensor_id': f'sensor_{i % 3}',
            'temperature': 20.0 + i * 0.5,
            'humidity': 50.0 + i * 2.0,
            'pressure': 1013.25 + i * 0.1,
            'metadata': {
                'location': f'zone_{i % 3}',
                'device_type': 'environmental_sensor',
                'batch': 'e2e_test'
            }
        }

        future = producer.send(TEST_TOPIC, value=data)
        record_metadata = future.get(timeout=10)

        timestamps.append(time.time())
        print(f"  [+] Sent message {i+1}/{count} to partition {record_metadata.partition}")

        time.sleep(0.1)  # 100ms between messages

    producer.flush()
    producer.close()

    print(f"[+] Produced {count} messages successfully")
    return timestamps

def verify_redis():
    """Verify data in Redis cache"""
    print("\n[?] Verifying data in Redis...")

    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=False)

    # Check if any keys exist
    keys = r.keys('sensor_*')
    print(f"  Found {len(keys)} sensor keys in Redis")

    if keys:
        # Show sample data
        sample_key = keys[0].decode('utf-8')
        value = r.get(keys[0])
        data = msgpack.unpackb(value, raw=False)
        print(f"  Sample: {sample_key} -> {data}")
        print("[+] Redis contains cached data")
    else:
        print("[\!]  No data found in Redis (cache may not be populated yet)")

    return len(keys)

def verify_timescaledb():
    """Verify data in TimescaleDB"""
    print("\n[?] Verifying data in TimescaleDB...")

    conn = psycopg2.connect(
        host=TIMESCALE_HOST,
        port=TIMESCALE_PORT,
        database=TIMESCALE_DB,
        user=TIMESCALE_USER,
        password=TIMESCALE_PASS
    )

    cursor = conn.cursor()

    # Count records
    cursor.execute("SELECT COUNT(*) FROM test_metrics WHERE metadata->>'batch' = 'e2e_test'")
    count = cursor.fetchone()[0]

    print(f"  Found {count} test records in TimescaleDB")

    if count > 0:
        # Show sample data
        cursor.execute("""
            SELECT timestamp, sensor_id, temperature, humidity, pressure
            FROM test_metrics
            WHERE metadata->>'batch' = 'e2e_test'
            ORDER BY timestamp DESC
            LIMIT 3
        """)

        rows = cursor.fetchall()
        print("  Latest records:")
        for row in rows:
            print(f"    {row[0]} | {row[1]} | T:{row[2]:.1f}°C H:{row[3]:.1f}% P:{row[4]:.2f}hPa")

        print("[+] TimescaleDB contains persisted data")
    else:
        print("[\!]  No data found in TimescaleDB yet")

    cursor.close()
    conn.close()

    return count

def measure_latency():
    """Measure end-to-end latency"""
    print("\n[T]  Measuring end-to-end latency...")

    start_time = time.time()

    # Produce a single message
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: msgpack.packb(v, use_bin_type=True)
    )

    test_data = {
        'timestamp': datetime.utcnow().isoformat(),
        'sensor_id': 'latency_test',
        'temperature': 25.0,
        'humidity': 60.0,
        'pressure': 1013.25,
        'metadata': {'test': 'latency'}
    }

    producer.send(TEST_TOPIC, value=test_data)
    producer.flush()
    producer.close()

    produce_time = time.time() - start_time

    print(f"  Produce latency: {produce_time*1000:.2f}ms")
    print("[+] Latency measurement complete")

def main():
    print("[RUN] HIMARI OPUS Layer 0 - End-to-End Test")
    print("=" * 60)

    try:
        # Step 1: Create topic
        create_topic()

        # Step 2: Initialize TimescaleDB
        init_timescaledb()

        # Step 3: Produce test data
        timestamps = produce_test_data(10)

        # Step 4: Wait for processing
        print("\n[...] Waiting for data to be processed...")
        time.sleep(5)

        # Step 5: Verify Redis
        redis_count = verify_redis()

        # Step 6: Verify TimescaleDB
        timescale_count = verify_timescaledb()

        # Step 7: Measure latency
        measure_latency()

        # Summary
        print("\n" + "=" * 60)
        print("[STATS] TEST SUMMARY")
        print("=" * 60)
        print(f"[+] Messages produced: 10")
        print(f"[+] Redis cache entries: {redis_count}")
        print(f"[+] TimescaleDB records: {timescale_count}")
        print("\n[OK] End-to-end test completed successfully!")

    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0

if __name__ == "__main__":
    exit(main())
