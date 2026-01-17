"""
Simple consumer for end-to-end testing
Consumes from Kafka, caches in Redis, and persists to TimescaleDB
"""
import msgpack
from kafka import KafkaConsumer
import redis
import psycopg2
from datetime import datetime
import json

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
CONSUMER_GROUP = 'e2e-test-consumer'

def consume_and_process():
    """Consume messages and process them"""
    print("[RUN] Starting E2E Consumer")
    print("=" * 60)

    # Connect to Redis
    print("[*] Connecting to Redis...")
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)
    print("[+] Connected to Redis")

    # Connect to TimescaleDB
    print("[*] Connecting to TimescaleDB...")
    conn = psycopg2.connect(
        host=TIMESCALE_HOST,
        port=TIMESCALE_PORT,
        database=TIMESCALE_DB,
        user=TIMESCALE_USER,
        password=TIMESCALE_PASS
    )
    cursor = conn.cursor()
    print("[+] Connected to TimescaleDB")

    # Create Kafka consumer
    print(f"[*] Creating Kafka consumer for topic '{TEST_TOPIC}'...")
    consumer = KafkaConsumer(
        TEST_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        group_id=CONSUMER_GROUP,
        value_deserializer=lambda m: msgpack.unpackb(m, raw=False),
        auto_offset_reset='earliest',  # Read from beginning
        enable_auto_commit=True
    )
    print("[+] Kafka consumer created")

    print("\n[>>] Consuming messages (press Ctrl+C to stop)...")
    print("=" * 60)

    message_count = 0

    try:
        for message in consumer:
            data = message.value
            message_count += 1

            print(f"\n[{message_count}] Partition {message.partition}, Offset {message.offset}")

            # Cache in Redis
            sensor_id = data['sensor_id']
            redis_key = f"{sensor_id}"

            r.set(redis_key, msgpack.packb(data, use_bin_type=True), ex=3600)  # 1 hour TTL
            print(f"  [REDIS] Cached {redis_key}")

            # Persist to TimescaleDB
            try:
                cursor.execute("""
                    INSERT INTO test_metrics (timestamp, sensor_id, temperature, humidity, pressure, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (
                    data['timestamp'],
                    data['sensor_id'],
                    data['temperature'],
                    data['humidity'],
                    data['pressure'],
                    json.dumps(data['metadata'])
                ))
                conn.commit()
                print(f"  [TIMESCALE] Inserted {sensor_id} - T:{data['temperature']:.1f}C H:{data['humidity']:.1f}%")
            except Exception as e:
                print(f"  [ERROR] Failed to insert to TimescaleDB: {e}")
                conn.rollback()

            print(f"  [+] Processed message {message_count}")

    except KeyboardInterrupt:
        print(f"\n\n[*] Stopping consumer...")

    finally:
        consumer.close()
        cursor.close()
        conn.close()
        print(f"[OK] Consumed and processed {message_count} messages")

if __name__ == "__main__":
    consume_and_process()
