# neo4j_sink.py
# HIMARI Opus1 - Neo4j Causal Event Sink
# Writes cascade events, whale transfers, and price movements to knowledge graph

import json
import logging
from typing import Dict, Any, List

from neo4j import GraphDatabase
from pyflink.datastream.functions import SinkFunction

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Neo4jEventSink(SinkFunction):
    """
    Write causal events to Neo4j knowledge graph with batching.
    Uses connection pooling and transaction batching for performance.
    """
    
    def __init__(
        self,
        uri: str = 'bolt://localhost:7687',
        user: str = 'neo4j',
        password: str = '',
        batch_size: int = 50,
        max_transaction_retry_time: float = 30.0
    ):
        self.uri = uri
        self.user = user
        self.password = password
        self.batch_size = batch_size
        self.max_transaction_retry_time = max_transaction_retry_time
        self.buffer: List[Dict[str, Any]] = []
        self.driver = None
    
    def open(self, runtime_context):
        """Initialize Neo4j driver with connection pool."""
        self.driver = GraphDatabase.driver(
            self.uri,
            auth=(self.user, self.password),
            max_connection_pool_size=10,
            connection_acquisition_timeout=30.0,
            max_transaction_retry_time=self.max_transaction_retry_time
        )
        
        # Verify connectivity
        self.driver.verify_connectivity()
        logger.info(f"Connected to Neo4j at {self.uri}")
    
    def invoke(self, value: str, context):
        """Buffer events and batch-write to Neo4j."""
        try:
            event = json.loads(value)
            self.buffer.append(event)
            
            if len(self.buffer) >= self.batch_size:
                self._flush_buffer()
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse event: {e}")
        except Exception as e:
            logger.error(f"Neo4j sink error: {e}")
    
    def _flush_buffer(self):
        """Flush buffer to Neo4j using batched transactions."""
        if not self.buffer or not self.driver:
            return
        
        try:
            with self.driver.session() as session:
                # Group events by type for efficient batch processing
                cascade_events = []
                whale_transfers = []
                price_movements = []
                quality_events = []
                
                for event in self.buffer:
                    event_type = event.get('event_type', event.get('type', 'quality'))
                    
                    if event_type == 'cascade':
                        cascade_events.append(event)
                    elif event_type == 'whale_transfer':
                        whale_transfers.append(event)
                    elif event_type == 'price_movement':
                        price_movements.append(event)
                    else:
                        quality_events.append(event)
                
                # Process each event type in batch
                if cascade_events:
                    session.execute_write(self._create_cascade_events, cascade_events)
                
                if whale_transfers:
                    session.execute_write(self._create_whale_transfers, whale_transfers)
                
                if price_movements:
                    session.execute_write(self._create_price_movements, price_movements)
                
                if quality_events:
                    session.execute_write(self._create_quality_events, quality_events)
            
            logger.debug(f"Flushed {len(self.buffer)} events to Neo4j")
            self.buffer.clear()
            
        except Exception as e:
            logger.error(f"Neo4j batch write error: {e}")
            # Keep buffer for retry on next flush
    
    @staticmethod
    def _create_cascade_events(tx, events: List[Dict]):
        """Create CascadeEvent nodes and relationships."""
        query = """
        UNWIND $events AS event
        MERGE (c:CascadeEvent {id: event.id})
        SET c.timestamp = datetime(event.timestamp),
            c.severity = event.severity,
            c.affected_pairs = event.affected_pairs,
            c.spread_velocity = event.spread_velocity,
            c.max_drawdown = event.max_drawdown,
            c.created_at = datetime()
        
        WITH c, event
        MATCH (origin:Exchange {name: event.origin_exchange})
        MERGE (c)-[:ORIGINATED_FROM]->(origin)
        
        WITH c, event
        UNWIND event.affected_pairs AS pair_symbol
        MATCH (p:Pair {symbol: pair_symbol})
        MERGE (c)-[:AFFECTED]->(p)
        """
        tx.run(query, events=events)
    
    @staticmethod
    def _create_whale_transfers(tx, events: List[Dict]):
        """Create WhaleTransfer nodes and relationships."""
        query = """
        UNWIND $events AS event
        MERGE (w:WhaleTransfer {tx_hash: event.tx_hash})
        SET w.timestamp = datetime(event.timestamp),
            w.amount = event.amount,
            w.amount_usd = event.amount_usd,
            w.asset = event.asset,
            w.from_exchange = event.from_exchange,
            w.to_exchange = event.to_exchange,
            w.created_at = datetime()
        
        WITH w, event
        MATCH (a:Asset {symbol: event.asset})
        MERGE (w)-[:TRANSFERRED]->(a)
        
        WITH w, event
        WHERE event.from_exchange IS NOT NULL
        MATCH (from_ex:Exchange {name: event.from_exchange})
        MERGE (w)-[:FROM_EXCHANGE]->(from_ex)
        
        WITH w, event
        WHERE event.to_exchange IS NOT NULL
        MATCH (to_ex:Exchange {name: event.to_exchange})
        MERGE (w)-[:TO_EXCHANGE]->(to_ex)
        """
        tx.run(query, events=events)
    
    @staticmethod
    def _create_price_movements(tx, events: List[Dict]):
        """Create PriceMovement nodes linked to pairs and exchanges."""
        query = """
        UNWIND $events AS event
        CREATE (pm:PriceMovement {
            id: event.id,
            timestamp: datetime(event.timestamp),
            symbol: event.symbol,
            exchange: event.exchange,
            price_change_pct: event.price_change_pct,
            volume_change_pct: event.volume_change_pct,
            direction: event.direction,
            magnitude: event.magnitude,
            created_at: datetime()
        })
        
        WITH pm, event
        MATCH (p:Pair {symbol: event.symbol})
        MERGE (pm)-[:ON_PAIR]->(p)
        
        WITH pm, event
        MATCH (ex:Exchange {name: event.exchange})
        MERGE (pm)-[:ON_EXCHANGE]->(ex)
        """
        tx.run(query, events=events)
    
    @staticmethod
    def _create_quality_events(tx, events: List[Dict]):
        """Create QualityEvent nodes for data quality tracking."""
        query = """
        UNWIND $events AS event
        CREATE (q:QualityEvent {
            timestamp: datetime(event.processed_at),
            symbol: event.symbol,
            quality_score: event.quality_score,
            issues: event.issues,
            issue_count: event.issue_count,
            created_at: datetime()
        })
        
        WITH q, event
        WHERE event.quality_score < 0.7
        MATCH (p:Pair) WHERE p.symbol CONTAINS event.symbol
        MERGE (q)-[:LOW_QUALITY_ON]->(p)
        """
        tx.run(query, events=events)
    
    def close(self):
        """Flush remaining buffer and close driver."""
        if self.buffer:
            self._flush_buffer()
        
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")


class Neo4jEventReader:
    """
    Read causal events and relationships from Neo4j knowledge graph.
    Provides graph traversal queries for cascade detection and analysis.
    """
    
    def __init__(
        self,
        uri: str = 'bolt://localhost:7687',
        user: str = 'neo4j',
        password: str = ''
    ):
        self.driver = GraphDatabase.driver(
            uri,
            auth=(user, password)
        )
    
    def get_recent_cascades(
        self,
        hours: int = 24,
        min_severity: float = 0.5
    ) -> List[Dict[str, Any]]:
        """Get recent cascade events with affected pairs."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (c:CascadeEvent)-[:AFFECTED]->(p:Pair)
                WHERE c.timestamp > datetime() - duration({hours: $hours})
                  AND c.severity >= $min_severity
                RETURN c.id AS id,
                       c.timestamp AS timestamp,
                       c.severity AS severity,
                       c.spread_velocity AS spread_velocity,
                       c.max_drawdown AS max_drawdown,
                       collect(p.symbol) AS affected_pairs
                ORDER BY c.timestamp DESC
            """, hours=hours, min_severity=min_severity)
            
            return [dict(record) for record in result]
    
    def get_whale_activity(
        self,
        asset: str,
        hours: int = 24,
        min_amount_usd: float = 100000
    ) -> List[Dict[str, Any]]:
        """Get whale transfers for a specific asset."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (w:WhaleTransfer)-[:TRANSFERRED]->(a:Asset {symbol: $asset})
                WHERE w.timestamp > datetime() - duration({hours: $hours})
                  AND w.amount_usd >= $min_amount_usd
                OPTIONAL MATCH (w)-[:FROM_EXCHANGE]->(from_ex:Exchange)
                OPTIONAL MATCH (w)-[:TO_EXCHANGE]->(to_ex:Exchange)
                RETURN w.tx_hash AS tx_hash,
                       w.timestamp AS timestamp,
                       w.amount AS amount,
                       w.amount_usd AS amount_usd,
                       from_ex.name AS from_exchange,
                       to_ex.name AS to_exchange
                ORDER BY w.timestamp DESC
            """, asset=asset, hours=hours, min_amount_usd=min_amount_usd)
            
            return [dict(record) for record in result]
    
    def get_exchange_cascade_exposure(
        self,
        exchange_name: str,
        days: int = 7
    ) -> Dict[str, Any]:
        """Get cascade exposure analysis for an exchange."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (ex:Exchange {name: $exchange_name})<-[:ORIGINATED_FROM]-(c:CascadeEvent)
                WHERE c.timestamp > datetime() - duration({days: $days})
                WITH count(c) AS originated_count,
                     avg(c.severity) AS avg_severity,
                     max(c.max_drawdown) AS max_drawdown
                
                MATCH (ex:Exchange {name: $exchange_name})<-[:LISTS]-(p:Pair)<-[:AFFECTED]-(c2:CascadeEvent)
                WHERE c2.timestamp > datetime() - duration({days: $days})
                RETURN originated_count,
                       avg_severity,
                       max_drawdown,
                       count(DISTINCT c2) AS affected_by_count
            """, exchange_name=exchange_name, days=days)
            
            record = result.single()
            return dict(record) if record else {}
    
    def find_cascade_path(
        self,
        from_exchange: str,
        to_exchange: str,
        max_hops: int = 3
    ) -> List[Dict[str, Any]]:
        """Find cascade propagation paths between exchanges."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH path = (from_ex:Exchange {name: $from_exchange})
                    <-[:ORIGINATED_FROM]-(c:CascadeEvent)
                    -[:AFFECTED]->(:Pair)
                    <-[:LISTS]-(to_ex:Exchange {name: $to_exchange})
                WHERE length(path) <= $max_hops * 2
                RETURN c.id AS cascade_id,
                       c.timestamp AS timestamp,
                       c.severity AS severity,
                       [n IN nodes(path) | labels(n)[0] + ':' + coalesce(n.name, n.symbol, n.id)] AS path
                ORDER BY c.timestamp DESC
                LIMIT 10
            """, from_exchange=from_exchange, to_exchange=to_exchange, max_hops=max_hops)
            
            return [dict(record) for record in result]
    
    def get_quality_trends(
        self,
        symbol: str,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """Get quality score trends for a symbol."""
        with self.driver.session() as session:
            result = session.run("""
                MATCH (q:QualityEvent {symbol: $symbol})
                WHERE q.timestamp > datetime() - duration({hours: $hours})
                RETURN q.timestamp AS timestamp,
                       q.quality_score AS quality_score,
                       q.issues AS issues
                ORDER BY q.timestamp DESC
            """, symbol=symbol, hours=hours)
            
            return [dict(record) for record in result]
    
    def close(self):
        """Close the driver."""
        self.driver.close()
