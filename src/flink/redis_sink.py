# redis_sink.py
# HIMARI Opus1 - High-performance Redis Sink for Flink
# Writes computed features to Redis with batching and pipelining

import redis
import json
from datetime import datetime
from typing import Dict, Any, List

from pyflink.datastream.functions import SinkFunction


class RedisFeatureSink(SinkFunction):
    """
    Write computed features to Redis with optimized batching.
    Uses connection pooling and pipelining for performance.
    """
    
    def __init__(
        self,
        host: str = '127.0.0.1',
        port: int = 6379,
        password: str = '',
        db: int = 0,
        batch_size: int = 100
    ):
        self.host = host
        self.port = port
        self.password = password
        self.db = db
        self.batch_size = batch_size
        self.buffer: List[str] = []
        self.pool = None
        self.client = None
    
    def open(self, runtime_context):
        """Initialize Redis connection pool."""
        self.pool = redis.ConnectionPool(
            host=self.host,
            port=self.port,
            password=self.password,
            db=self.db,
            max_connections=10,
            decode_responses=True,
            socket_timeout=5.0,
            socket_connect_timeout=5.0
        )
        self.client = redis.Redis(connection_pool=self.pool)
        
        # Verify connection
        self.client.ping()
    
    def invoke(self, value: str, context):
        """Buffer and batch-write features to Redis."""
        self.buffer.append(value)
        
        if len(self.buffer) >= self.batch_size:
            self._flush_buffer()
    
    def _flush_buffer(self):
        """Flush buffer to Redis using pipeline."""
        if not self.buffer:
            return
        
        try:
            pipe = self.client.pipeline()
            
            for item in self.buffer:
                data = json.loads(item)
                symbol = data['symbol']
                timestamp = data['timestamp']
                
                # Latest feature (always overwritten)
                latest_key = f"features:{symbol}:latest"
                pipe.set(latest_key, item, ex=3600)  # 1 hour TTL
                
                # Time-indexed for lookups (sorted set)
                history_key = f"features:{symbol}:history"
                pipe.zadd(history_key, {item: timestamp})
                
                # Trim history to last 1000 entries
                pipe.zremrangebyrank(history_key, 0, -1001)
            
            pipe.execute()
            self.buffer.clear()
        
        except redis.RedisError as e:
            # Log error but don't crash - will retry on next batch
            print(f"Redis write error: {e}")
    
    def close(self):
        """Flush remaining buffer and close connections."""
        self._flush_buffer()
        if self.pool:
            self.pool.disconnect()


class RedisFeatureReader:
    """
    Read features from Redis for trading strategies.
    Provides both latest and historical lookups.
    """
    
    def __init__(
        self,
        host: str = '127.0.0.1',
        port: int = 6379,
        password: str = '',
        db: int = 0
    ):
        self.pool = redis.ConnectionPool(
            host=host,
            port=port,
            password=password,
            db=db,
            max_connections=5,
            decode_responses=True,
            socket_timeout=5.0
        )
        self.client = redis.Redis(connection_pool=self.pool)
    
    def get_latest(self, symbol: str) -> Dict[str, Any]:
        """Get the latest feature for a symbol."""
        key = f"features:{symbol}:latest"
        data = self.client.get(key)
        if data:
            return json.loads(data)
        return None
    
    def get_history(
        self,
        symbol: str,
        start_time: int = None,
        end_time: int = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get historical features for a symbol within a time range."""
        key = f"features:{symbol}:history"
        
        if start_time is None:
            start_time = '-inf'
        if end_time is None:
            end_time = '+inf'
        
        items = self.client.zrangebyscore(
            key,
            start_time,
            end_time,
            start=0,
            num=limit,
            withscores=False
        )
        
        return [json.loads(item) for item in items]
    
    def get_multi_latest(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        """Get latest features for multiple symbols in one call."""
        pipe = self.client.pipeline()
        
        for symbol in symbols:
            pipe.get(f"features:{symbol}:latest")
        
        results = pipe.execute()
        
        return {
            symbol: json.loads(data) if data else None
            for symbol, data in zip(symbols, results)
        }
    
    def close(self):
        """Close connection pool."""
        self.pool.disconnect()
