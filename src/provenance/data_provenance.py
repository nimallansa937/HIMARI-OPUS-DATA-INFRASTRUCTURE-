"""
L0-1: Data Provenance Chain
===========================
Track the origin, transformation history, and quality score of every data point
entering the system. Enables debugging, audit trails, and automatic rejection
of corrupted data.

File: Layer 0 Data infrastructure/src/provenance/data_provenance.py
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum
import hashlib
import json
import time


class DataSourceType(Enum):
    """Enumeration of data source types."""
    BINANCE_WS = "binance_ws"
    BINANCE_REST = "binance_rest"
    KRAKEN_WS = "kraken_ws"
    COINBASE_WS = "coinbase_ws"
    SANTIMENT_API = "santiment_api"
    GLASSNODE_API = "glassnode_api"
    MORALIS_API = "moralis_api"
    ALCHEMY_API = "alchemy_api"
    REDIS_CACHE = "redis_cache"
    INTERNAL_CALC = "internal_calculation"
    UNKNOWN = "unknown"


@dataclass
class TransformationStep:
    """Single transformation applied to data."""
    transform_type: str  # e.g., "normalize", "interpolate", "smooth"
    timestamp: datetime
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.transform_type,
            "timestamp": self.timestamp.isoformat(),
            "parameters": self.parameters
        }


@dataclass
class ProvenanceRecord:
    """
    Complete provenance record for a data point.
    
    Tracks origin, transformations, and quality metrics.
    """
    # Origin information
    source_id: str  # e.g., "binance_ws_btcusdt"
    source_type: DataSourceType
    source_timestamp: datetime  # When data was generated at source
    receive_timestamp: datetime  # When HIMARI received the data
    
    # Data identity
    data_type: str  # e.g., "price", "volume", "funding_rate"
    symbol: str
    value: Any
    
    # Transformation chain
    transform_chain: List[TransformationStep] = field(default_factory=list)
    
    # Quality metrics
    quality_score: float = 1.0  # 0.0-1.0 confidence in data integrity
    staleness_ms: float = 0.0  # Age of data at time of use
    
    # Validation flags
    is_validated: bool = False
    validation_errors: List[str] = field(default_factory=list)
    
    @property
    def data_hash(self) -> str:
        """Generate unique hash for this data point."""
        content = f"{self.source_id}:{self.source_timestamp.isoformat()}:{self.value}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def add_transformation(self, transform_type: str, **params) -> None:
        """Record a transformation applied to this data."""
        step = TransformationStep(
            transform_type=transform_type,
            timestamp=datetime.now(),
            parameters=params
        )
        self.transform_chain.append(step)
    
    def calculate_staleness(self) -> float:
        """Calculate current staleness in milliseconds."""
        now = datetime.now()
        delta = (now - self.source_timestamp).total_seconds() * 1000
        self.staleness_ms = delta
        return delta
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize for storage/transmission."""
        return {
            "source_id": self.source_id,
            "source_type": self.source_type.value,
            "source_timestamp": self.source_timestamp.isoformat(),
            "receive_timestamp": self.receive_timestamp.isoformat(),
            "data_type": self.data_type,
            "symbol": self.symbol,
            "value": self.value,
            "transform_chain": [t.to_dict() for t in self.transform_chain],
            "quality_score": self.quality_score,
            "staleness_ms": self.staleness_ms,
            "data_hash": self.data_hash,
            "is_validated": self.is_validated,
            "validation_errors": self.validation_errors
        }


@dataclass
class SourceReliability:
    """Track historical reliability of a data source."""
    source_id: str
    uptime_ratio: float = 1.0  # Historical uptime
    avg_latency_ms: float = 0.0
    error_rate: float = 0.0
    known_issues: List[str] = field(default_factory=list)
    last_updated: datetime = field(default_factory=datetime.now)


class QualityScorer:
    """
    Calculate quality scores for incoming data.
    
    Quality Score Factors:
    - Source reliability (historical uptime, known issues)
    - Timestamp consistency (monotonic, no gaps)
    - Value plausibility (within N sigma of rolling mean)
    - Cross-source agreement (if multiple sources for same data)
    """
    
    def __init__(
        self,
        sigma_threshold: float = 3.0,
        max_gap_seconds: float = 10.0,
        reliability_weight: float = 0.3,
        timestamp_weight: float = 0.2,
        plausibility_weight: float = 0.3,
        cross_source_weight: float = 0.2
    ):
        self.sigma_threshold = sigma_threshold
        self.max_gap_seconds = max_gap_seconds
        
        # Weights for quality factors
        self.weights = {
            "reliability": reliability_weight,
            "timestamp": timestamp_weight,
            "plausibility": plausibility_weight,
            "cross_source": cross_source_weight
        }
        
        # State tracking
        self.source_reliability: Dict[str, SourceReliability] = {}
        self.value_history: Dict[str, List[float]] = {}
        self.last_timestamps: Dict[str, datetime] = {}
        self.history_window = 100
    
    def get_source_reliability(self, source_id: str) -> float:
        """Get reliability score for a source (0.0-1.0)."""
        if source_id not in self.source_reliability:
            # Default reliability for new sources
            return 0.8
        
        rel = self.source_reliability[source_id]
        # Combine uptime and error rate
        score = (rel.uptime_ratio * 0.6) + ((1 - rel.error_rate) * 0.4)
        return max(0.0, min(1.0, score))
    
    def check_timestamp_consistency(
        self, 
        source_id: str, 
        timestamp: datetime
    ) -> float:
        """Check if timestamp is consistent (monotonic, no large gaps)."""
        key = source_id
        
        if key not in self.last_timestamps:
            self.last_timestamps[key] = timestamp
            return 1.0
        
        last_ts = self.last_timestamps[key]
        delta = (timestamp - last_ts).total_seconds()
        
        # Check for regression (timestamp going backwards)
        if delta < -0.1:  # Allow 100ms jitter
            return 0.0
        
        # Check for large gaps
        if delta > self.max_gap_seconds:
            gap_penalty = min(1.0, delta / (self.max_gap_seconds * 5))
            return 1.0 - gap_penalty
        
        self.last_timestamps[key] = timestamp
        return 1.0
    
    def check_value_plausibility(
        self, 
        key: str, 
        value: float
    ) -> float:
        """Check if value is plausible (within N sigma of rolling mean)."""
        if key not in self.value_history:
            self.value_history[key] = []
        
        history = self.value_history[key]
        
        if len(history) < 10:
            history.append(value)
            return 1.0
        
        # Calculate rolling mean and std
        import statistics
        mean = statistics.mean(history)
        std = statistics.stdev(history) if len(history) > 1 else 1.0
        
        if std < 1e-10:
            std = abs(mean) * 0.01 if mean != 0 else 1.0
        
        # Calculate z-score
        z_score = abs(value - mean) / std
        
        # Update history
        history.append(value)
        if len(history) > self.history_window:
            history.pop(0)
        
        # Score based on z-score
        if z_score <= self.sigma_threshold:
            return 1.0
        elif z_score <= self.sigma_threshold * 2:
            return 0.5
        else:
            return 0.0
    
    def calculate_quality_score(
        self,
        record: ProvenanceRecord,
        cross_source_values: Optional[List[float]] = None
    ) -> float:
        """
        Calculate overall quality score for a data record.
        
        Returns score between 0.0 and 1.0.
        """
        scores = {}
        
        # 1. Source reliability
        scores["reliability"] = self.get_source_reliability(record.source_id)
        
        # 2. Timestamp consistency
        scores["timestamp"] = self.check_timestamp_consistency(
            record.source_id, 
            record.source_timestamp
        )
        
        # 3. Value plausibility (only for numeric values)
        key = f"{record.symbol}:{record.data_type}"
        if isinstance(record.value, (int, float)):
            scores["plausibility"] = self.check_value_plausibility(key, record.value)
        else:
            scores["plausibility"] = 1.0
        
        # 4. Cross-source agreement
        if cross_source_values and isinstance(record.value, (int, float)):
            # Check if value agrees with other sources
            import statistics
            other_mean = statistics.mean(cross_source_values)
            diff_pct = abs(record.value - other_mean) / abs(other_mean) if other_mean != 0 else 0
            scores["cross_source"] = max(0.0, 1.0 - diff_pct * 10)
        else:
            scores["cross_source"] = 1.0  # No cross-source check available
        
        # Weighted average
        total_score = sum(
            scores[k] * self.weights[k] 
            for k in scores
        )
        
        return max(0.0, min(1.0, total_score))


class DataProvenanceValidator:
    """
    Validate incoming data and attach provenance metadata.
    
    Configuration Parameters:
    - min_quality_threshold: Reject data below this score (default: 0.7)
    - staleness_warning_ms: Log warning if data older than this (default: 500)
    - staleness_reject_ms: Reject data older than this (default: 2000)
    - cross_source_required: Require 2+ sources to agree (default: false)
    """
    
    def __init__(
        self,
        min_quality_threshold: float = 0.7,
        staleness_warning_ms: float = 500,
        staleness_reject_ms: float = 2000,
        cross_source_required: bool = False
    ):
        self.min_quality_threshold = min_quality_threshold
        self.staleness_warning_ms = staleness_warning_ms
        self.staleness_reject_ms = staleness_reject_ms
        self.cross_source_required = cross_source_required
        
        self.quality_scorer = QualityScorer()
        
        # Metrics
        self.total_received = 0
        self.total_accepted = 0
        self.total_rejected = 0
        self.rejection_reasons: Dict[str, int] = {}
    
    def create_provenance(
        self,
        source_id: str,
        source_type: DataSourceType,
        source_timestamp: datetime,
        data_type: str,
        symbol: str,
        value: Any
    ) -> ProvenanceRecord:
        """Create a new provenance record for incoming data."""
        return ProvenanceRecord(
            source_id=source_id,
            source_type=source_type,
            source_timestamp=source_timestamp,
            receive_timestamp=datetime.now(),
            data_type=data_type,
            symbol=symbol,
            value=value
        )
    
    def validate(
        self,
        record: ProvenanceRecord,
        cross_source_values: Optional[List[float]] = None
    ) -> bool:
        """
        Validate a provenance record.
        
        Returns True if data passes all checks, False otherwise.
        """
        self.total_received += 1
        record.validation_errors = []
        
        # 1. Check staleness
        staleness = record.calculate_staleness()
        
        if staleness > self.staleness_reject_ms:
            record.validation_errors.append(
                f"Data too stale: {staleness:.0f}ms > {self.staleness_reject_ms}ms"
            )
            self._reject("staleness_exceeded")
            return False
        
        if staleness > self.staleness_warning_ms:
            # Log warning but don't reject
            pass
        
        # 2. Calculate quality score
        quality = self.quality_scorer.calculate_quality_score(
            record, 
            cross_source_values
        )
        record.quality_score = quality
        
        if quality < self.min_quality_threshold:
            record.validation_errors.append(
                f"Quality too low: {quality:.2f} < {self.min_quality_threshold}"
            )
            self._reject("quality_too_low")
            return False
        
        # 3. Cross-source requirement
        if self.cross_source_required and not cross_source_values:
            record.validation_errors.append("Cross-source validation required but missing")
            self._reject("cross_source_missing")
            return False
        
        # Passed all checks
        record.is_validated = True
        self.total_accepted += 1
        return True
    
    def _reject(self, reason: str) -> None:
        """Record a rejection."""
        self.total_rejected += 1
        self.rejection_reasons[reason] = self.rejection_reasons.get(reason, 0) + 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get validation statistics."""
        accept_rate = self.total_accepted / self.total_received if self.total_received > 0 else 0
        return {
            "total_received": self.total_received,
            "total_accepted": self.total_accepted,
            "total_rejected": self.total_rejected,
            "accept_rate": accept_rate,
            "rejection_reasons": self.rejection_reasons
        }


# Convenience function for quick provenance attachment
def attach_provenance(
    value: Any,
    source_id: str,
    symbol: str,
    data_type: str = "price",
    source_type: DataSourceType = DataSourceType.UNKNOWN
) -> ProvenanceRecord:
    """
    Quick helper to attach provenance to a data point.
    
    Example:
        price = 50000.0
        record = attach_provenance(price, "binance_ws_btcusdt", "BTCUSDT", "price")
    """
    return ProvenanceRecord(
        source_id=source_id,
        source_type=source_type,
        source_timestamp=datetime.now(),
        receive_timestamp=datetime.now(),
        data_type=data_type,
        symbol=symbol,
        value=value
    )


if __name__ == "__main__":
    # Quick test
    validator = DataProvenanceValidator()
    
    record = attach_provenance(
        value=50000.0,
        source_id="binance_ws_btcusdt",
        symbol="BTCUSDT",
        data_type="price",
        source_type=DataSourceType.BINANCE_WS
    )
    
    is_valid = validator.validate(record)
    print(f"Record valid: {is_valid}")
    print(f"Quality score: {record.quality_score:.2f}")
    print(f"Staleness: {record.staleness_ms:.0f}ms")
    print(f"Stats: {validator.get_stats()}")
