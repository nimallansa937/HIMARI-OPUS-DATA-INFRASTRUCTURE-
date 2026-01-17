"""
End-to-end latency test for HIMARI OPUS Layer 0
Measures the time from message production to database persistence
"""
import time
import msgpack
from kafka import KafkaProducer
import redis
import psycopg2
from datetime import datetime
import uuid

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

def measure_latency(num_samples=5):
    """Measure end-to-end latency"""
    print("[RUN] HIMARI OPUS Layer 0 - Latency Measurement")
    print("=" * 60)

    # Connect to services
    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP,
        value_serializer=lambda v: msgpack.packb(v, use_bin_type=True)
    )

    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=False)

    conn = psycopg2.connect(
        host=TIMESCALE_HOST,
        port=TIMESCALE_PORT,
        database=TIMESCALE_DB,
        user=TIMESCALE_USER,
        password=TIMESCALE_PASS
    )

    latencies = {
        'kafka_produce': [],
        'redis_availability': [],
        'timescale_persistence': []
    }

    print(f"\n[*] Measuring latency across {num_samples} samples...\n")

    for i in range(num_samples):
        test_id = str(uuid.uuid4())

        # Measure Kafka produce latency
        data = {
            'timestamp': datetime.utcnow().isoformat(),
            'sensor_id': f'latency_test_{test_id}',
            'temperature': 25.0,
            'humidity': 60.0,
            'pressure': 1013.25,
            'metadata': {
                'test_id': test_id,
                'batch': 'latency_test'
            }
        }

        start = time.time()
        future = producer.send(TEST_TOPIC, value=data)
        future.get(timeout=10)
        kafka_latency = (time.time() - start) * 1000

        latencies['kafka_produce'].append(kafka_latency)
        print(f"[{i+1}] Kafka produce: {kafka_latency:.2f}ms")

        # Wait for consumer to process
        time.sleep(2)

        # Check Redis availability
        start = time.time()
        cached = r.get(f"latency_test_{test_id}")
        redis_latency = (time.time() - start) * 1000

        if cached:
            latencies['redis_availability'].append(redis_latency)
            print(f"    Redis read: {redis_latency:.2f}ms [CACHED]")
        else:
            print(f"    Redis read: NOT FOUND (may need consumer running)")

        # Check TimescaleDB persistence
        cursor = conn.cursor()
        start = time.time()
        cursor.execute("""
            SELECT COUNT(*) FROM test_metrics
            WHERE sensor_id = %s
        """, (f'latency_test_{test_id}',))
        count = cursor.fetchone()[0]
        timescale_latency = (time.time() - start) * 1000

        if count > 0:
            latencies['timescale_persistence'].append(timescale_latency)
            print(f"    TimescaleDB query: {timescale_latency:.2f}ms [PERSISTED]\n")
        else:
            print(f"    TimescaleDB query: NOT FOUND (may need consumer running)\n")

        cursor.close()

    producer.close()
    conn.close()

    # Calculate statistics
    print("=" * 60)
    print("[STATS] LATENCY SUMMARY")
    print("=" * 60)

    for operation, values in latencies.items():
        if values:
            avg = sum(values) / len(values)
            min_val = min(values)
            max_val = max(values)
            print(f"\n{operation.replace('_', ' ').title()}:")
            print(f"  Average: {avg:.2f}ms")
            print(f"  Min: {min_val:.2f}ms")
            print(f"  Max: {max_val:.2f}ms")
            print(f"  Samples: {len(values)}/{num_samples}")
        else:
            print(f"\n{operation.replace('_', ' ').title()}: NO DATA")

    print("\n" + "=" * 60)
    print("[OK] Latency measurement complete!")

if __name__ == "__main__":
    measure_latency(5)
