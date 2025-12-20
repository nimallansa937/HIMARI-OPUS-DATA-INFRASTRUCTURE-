# timescale_sink.py
# HIMARI Opus1 - Batch-optimized TimescaleDB Sink
# Uses connection pooling and execute_values for 10x performance

import psycopg2
from psycopg2 import pool
from psycopg2.extras import execute_values
import json
from datetime import datetime
from typing import List, Tuple

from pyflink.datastream.functions import SinkFunction


class TimescaleDBSink(SinkFunction):
    """
    Write features to TimescaleDB with batched inserts.
    Uses connection pooling and execute_values for performance.
    """
    
    def __init__(
        self,
        host: str,
        database: str,
        user: str,
        password: str,
        port: int = 5432,
        batch_size: int = 500
    ):
        self.host = host
        self.database = database
        self.user = user
        self.password = password
        self.port = port
        self.batch_size = batch_size
        self.buffer: List[Tuple] = []
        self.conn_pool = None
    
    def open(self, runtime_context):
        """Initialize connection pool."""
        self.conn_pool = pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=10,
            host=self.host,
            port=self.port,
            database=self.database,
            user=self.user,
            password=self.password,
            connect_timeout=10
        )
    
    def invoke(self, value: str, context):
        """Buffer records and batch-insert to TimescaleDB."""
        try:
            data = json.loads(value)
            
            # Convert to tuple for batch insert
            record = (
                datetime.fromtimestamp(data['timestamp'] / 1000.0),
                data['symbol'],
                data.get('exchange', 'unknown'),
                data.get('price', 0.0),
                data.get('volume', 0.0),
                data.get('quality_score', 1.0),
                data.get('issues', [])
            )
            self.buffer.append(record)
            
            if len(self.buffer) >= self.batch_size:
                self._flush_buffer()
        
        except Exception as e:
            print(f"TimescaleDB sink error: {e}")
    
    def _flush_buffer(self):
        """Batch insert to TimescaleDB using execute_values."""
        if not self.buffer:
            return
        
        conn = None
        try:
            conn = self.conn_pool.getconn()
            cursor = conn.cursor()
            
            # Batch insert with execute_values (10x faster than executemany)
            execute_values(
                cursor,
                """
                INSERT INTO market_data
                (timestamp, symbol, exchange, price, volume, quality_score, issues)
                VALUES %s
                ON CONFLICT DO NOTHING
                """,
                self.buffer,
                template="(%s, %s, %s, %s, %s, %s, %s)"
            )
            
            conn.commit()
            self.buffer.clear()
        
        except Exception as e:
            if conn:
                conn.rollback()
            print(f"TimescaleDB batch insert error: {e}")
        
        finally:
            if conn:
                self.conn_pool.putconn(conn)
    
    def close(self):
        """Flush remaining buffer and close pool."""
        self._flush_buffer()
        if self.conn_pool:
            self.conn_pool.closeall()


class TimescaleDBReader:
    """
    Read analytics data from TimescaleDB.
    Provides access to raw data and continuous aggregates.
    """
    
    def __init__(
        self,
        host: str,
        database: str,
        user: str,
        password: str,
        port: int = 5432
    ):
        self.conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password
        )
    
    def get_ohlcv_5min(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime = None,
        exchange: str = None
    ) -> List[dict]:
        """Get 5-minute OHLCV data for a symbol."""
        if end_time is None:
            end_time = datetime.utcnow()
        
        cursor = self.conn.cursor()
        
        query = """
            SELECT bucket, symbol, exchange, 
                   open, high, low, close, volume,
                   trade_count, avg_quality
            FROM ohlcv_5min
            WHERE symbol = %s
              AND bucket >= %s
              AND bucket <= %s
        """
        params = [symbol, start_time, end_time]
        
        if exchange:
            query += " AND exchange = %s"
            params.append(exchange)
        
        query += " ORDER BY bucket DESC"
        
        cursor.execute(query, params)
        columns = [desc[0] for desc in cursor.description]
        
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def get_quality_summary(
        self,
        start_time: datetime,
        end_time: datetime = None
    ) -> List[dict]:
        """Get quality summary by symbol and exchange."""
        if end_time is None:
            end_time = datetime.utcnow()
        
        cursor = self.conn.cursor()
        
        cursor.execute("""
            SELECT 
                symbol,
                exchange,
                COUNT(*) as total_records,
                AVG(quality_score) as avg_quality,
                MIN(quality_score) as min_quality,
                COUNT(*) FILTER (WHERE quality_score < 0.7) as low_quality_count
            FROM market_data
            WHERE timestamp >= %s AND timestamp <= %s
            GROUP BY symbol, exchange
            ORDER BY avg_quality ASC
        """, (start_time, end_time))
        
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def close(self):
        """Close database connection."""
        self.conn.close()
