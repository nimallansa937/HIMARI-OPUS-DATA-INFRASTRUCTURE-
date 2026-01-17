"""
L0-2: Timestamp Triangulation
============================
Detect latency anomalies, data bunching, and clock drift by tracking three
timestamps for every market data tick.

Three Timestamps:
1. T_exchange: Timestamp from exchange (claimed generation time)
2. T_receive: Timestamp when HIMARI network layer receives packet
3. T_process: Timestamp when data enters processing pipeline

File: Layer 0 Data infrastructure/src/timing/timestamp_triangulation.py
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Callable
from enum import Enum
from collections import deque
import time
import statistics


class AnomalyType(Enum):
    """Types of timestamp anomalies."""
    LATENCY_SPIKE = "latency_spike"
    DATA_BUNCHING = "data_bunching"
    CLOCK_DRIFT = "clock_drift"
    TIMESTAMP_REGRESSION = "timestamp_regression"
    NORMAL = "normal"


@dataclass
class TriangulatedTimestamp:
    """
    Three-timestamp record for a single data tick.
    """
    # The three timestamps
    t_exchange: datetime  # From exchange
    t_receive: datetime   # When received by HIMARI
    t_process: datetime   # When entering processing
    
    # Metadata
    source_id: str
    symbol: str
    
    @property
    def network_latency_ms(self) -> float:
        """Calculate network latency (T_receive - T_exchange)."""
        return (self.t_receive - self.t_exchange).total_seconds() * 1000
    
    @property
    def processing_latency_ms(self) -> float:
        """Calculate processing latency (T_process - T_receive)."""
        return (self.t_process - self.t_receive).total_seconds() * 1000
    
    @property
    def total_latency_ms(self) -> float:
        """Calculate total latency (T_process - T_exchange)."""
        return (self.t_process - self.t_exchange).total_seconds() * 1000
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "t_exchange": self.t_exchange.isoformat(),
            "t_receive": self.t_receive.isoformat(),
            "t_process": self.t_process.isoformat(),
            "source_id": self.source_id,
            "symbol": self.symbol,
            "network_latency_ms": self.network_latency_ms,
            "processing_latency_ms": self.processing_latency_ms,
            "total_latency_ms": self.total_latency_ms
        }


@dataclass
class LatencyMetrics:
    """Aggregated latency metrics for a source."""
    source_id: str
    window_size: int
    
    # Rolling statistics
    network_latencies: deque = field(default_factory=lambda: deque(maxlen=1000))
    processing_latencies: deque = field(default_factory=lambda: deque(maxlen=1000))
    
    @property
    def network_median_ms(self) -> float:
        if not self.network_latencies:
            return 0.0
        return statistics.median(self.network_latencies)
    
    @property
    def network_p99_ms(self) -> float:
        if len(self.network_latencies) < 10:
            return self.network_median_ms
        sorted_lat = sorted(self.network_latencies)
        idx = int(len(sorted_lat) * 0.99)
        return sorted_lat[min(idx, len(sorted_lat) - 1)]
    
    @property
    def processing_median_ms(self) -> float:
        if not self.processing_latencies:
            return 0.0
        return statistics.median(self.processing_latencies)
    
    def add_sample(self, ts: TriangulatedTimestamp) -> None:
        """Add a new timestamp sample."""
        self.network_latencies.append(ts.network_latency_ms)
        self.processing_latencies.append(ts.processing_latency_ms)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "sample_count": len(self.network_latencies),
            "network_median_ms": self.network_median_ms,
            "network_p99_ms": self.network_p99_ms,
            "processing_median_ms": self.processing_median_ms
        }


@dataclass
class TimestampAnomaly:
    """Detected timestamp anomaly."""
    anomaly_type: AnomalyType
    source_id: str
    symbol: str
    timestamp: datetime
    severity: float  # 0.0-1.0
    details: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.anomaly_type.value,
            "source_id": self.source_id,
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "severity": self.severity,
            "details": self.details
        }


class TimestampTriangulator:
    """
    Track three timestamps for every data tick and detect anomalies.
    
    Configuration Parameters:
    - latency_spike_multiplier: Alert if latency > N × median (default: 3.0)
    - bunching_threshold_ms: Max time window for bunching detection (default: 1)
    - bunching_count: Min ticks in window to trigger alert (default: 10)
    - clock_drift_max_ms: Max acceptable clock drift (default: 100)
    - calibration_window_ticks: Ticks for baseline calculation (default: 1000)
    """
    
    def __init__(
        self,
        latency_spike_multiplier: float = 3.0,
        bunching_threshold_ms: float = 1.0,
        bunching_count: int = 10,
        clock_drift_max_ms: float = 100.0,
        calibration_window_ticks: int = 1000
    ):
        self.latency_spike_multiplier = latency_spike_multiplier
        self.bunching_threshold_ms = bunching_threshold_ms
        self.bunching_count = bunching_count
        self.clock_drift_max_ms = clock_drift_max_ms
        self.calibration_window_ticks = calibration_window_ticks
        
        # State tracking
        self.metrics: Dict[str, LatencyMetrics] = {}
        self.last_exchange_timestamps: Dict[str, datetime] = {}
        self.recent_receive_times: Dict[str, deque] = {}
        self.clock_drift_samples: Dict[str, deque] = {}
        
        # Expected latency baseline (calibrated)
        self.expected_latency: Dict[str, float] = {}
        
        # Anomaly callbacks
        self.anomaly_callbacks: List[Callable[[TimestampAnomaly], None]] = []
    
    def register_anomaly_callback(
        self, 
        callback: Callable[[TimestampAnomaly], None]
    ) -> None:
        """Register a callback for anomaly alerts."""
        self.anomaly_callbacks.append(callback)
    
    def _emit_anomaly(self, anomaly: TimestampAnomaly) -> None:
        """Emit anomaly to all registered callbacks."""
        for callback in self.anomaly_callbacks:
            try:
                callback(anomaly)
            except Exception:
                pass  # Don't let callback errors break processing
    
    def create_triangulated_timestamp(
        self,
        t_exchange: datetime,
        source_id: str,
        symbol: str
    ) -> TriangulatedTimestamp:
        """
        Create a triangulated timestamp record.
        
        Call this when receiving data from exchange.
        T_receive is set automatically, T_process should be set later.
        """
        t_receive = datetime.now()
        t_process = datetime.now()  # Will be updated when processing starts
        
        return TriangulatedTimestamp(
            t_exchange=t_exchange,
            t_receive=t_receive,
            t_process=t_process,
            source_id=source_id,
            symbol=symbol
        )
    
    def record_and_check(
        self, 
        ts: TriangulatedTimestamp
    ) -> List[TimestampAnomaly]:
        """
        Record a triangulated timestamp and check for anomalies.
        
        Returns list of detected anomalies (may be empty).
        """
        source_id = ts.source_id
        anomalies = []
        
        # Initialize state for new sources
        if source_id not in self.metrics:
            self.metrics[source_id] = LatencyMetrics(
                source_id=source_id,
                window_size=self.calibration_window_ticks
            )
            self.recent_receive_times[source_id] = deque(maxlen=100)
            self.clock_drift_samples[source_id] = deque(maxlen=self.calibration_window_ticks)
        
        # Add sample to metrics
        self.metrics[source_id].add_sample(ts)
        
        # Check for timestamp regression
        regression = self._check_timestamp_regression(ts)
        if regression:
            anomalies.append(regression)
        
        # Check for latency spike
        spike = self._check_latency_spike(ts)
        if spike:
            anomalies.append(spike)
        
        # Check for data bunching
        bunching = self._check_data_bunching(ts)
        if bunching:
            anomalies.append(bunching)
        
        # Check for clock drift
        drift = self._check_clock_drift(ts)
        if drift:
            anomalies.append(drift)
        
        # Update state
        self.last_exchange_timestamps[source_id] = ts.t_exchange
        self.recent_receive_times[source_id].append(ts.t_receive)
        
        # Emit anomalies
        for anomaly in anomalies:
            self._emit_anomaly(anomaly)
        
        return anomalies
    
    def _check_timestamp_regression(
        self, 
        ts: TriangulatedTimestamp
    ) -> Optional[TimestampAnomaly]:
        """Check if exchange timestamp went backwards."""
        source_id = ts.source_id
        
        if source_id not in self.last_exchange_timestamps:
            return None
        
        last_ts = self.last_exchange_timestamps[source_id]
        delta_ms = (ts.t_exchange - last_ts).total_seconds() * 1000
        
        if delta_ms < -10:  # Allow 10ms jitter
            return TimestampAnomaly(
                anomaly_type=AnomalyType.TIMESTAMP_REGRESSION,
                source_id=source_id,
                symbol=ts.symbol,
                timestamp=datetime.now(),
                severity=min(1.0, abs(delta_ms) / 1000),
                details=f"Exchange timestamp went backwards by {abs(delta_ms):.0f}ms"
            )
        
        return None
    
    def _check_latency_spike(
        self, 
        ts: TriangulatedTimestamp
    ) -> Optional[TimestampAnomaly]:
        """Check if network latency exceeds threshold."""
        source_id = ts.source_id
        metrics = self.metrics[source_id]
        
        if len(metrics.network_latencies) < 50:
            return None  # Need more samples for baseline
        
        median = metrics.network_median_ms
        current = ts.network_latency_ms
        
        threshold = median * self.latency_spike_multiplier
        
        if current > threshold and current > 50:  # Also require >50ms absolute
            severity = min(1.0, (current - threshold) / threshold)
            return TimestampAnomaly(
                anomaly_type=AnomalyType.LATENCY_SPIKE,
                source_id=source_id,
                symbol=ts.symbol,
                timestamp=datetime.now(),
                severity=severity,
                details=f"Network latency {current:.0f}ms > {threshold:.0f}ms (median: {median:.0f}ms)"
            )
        
        return None
    
    def _check_data_bunching(
        self, 
        ts: TriangulatedTimestamp
    ) -> Optional[TimestampAnomaly]:
        """Check if multiple ticks arrived within a short window."""
        source_id = ts.source_id
        receive_times = self.recent_receive_times[source_id]
        
        if len(receive_times) < self.bunching_count:
            return None
        
        # Count ticks in the bunching window
        cutoff = ts.t_receive - timedelta(milliseconds=self.bunching_threshold_ms)
        count_in_window = sum(1 for t in receive_times if t > cutoff)
        
        if count_in_window >= self.bunching_count:
            severity = min(1.0, count_in_window / (self.bunching_count * 3))
            return TimestampAnomaly(
                anomaly_type=AnomalyType.DATA_BUNCHING,
                source_id=source_id,
                symbol=ts.symbol,
                timestamp=datetime.now(),
                severity=severity,
                details=f"{count_in_window} ticks arrived within {self.bunching_threshold_ms}ms"
            )
        
        return None
    
    def _check_clock_drift(
        self, 
        ts: TriangulatedTimestamp
    ) -> Optional[TimestampAnomaly]:
        """Check for systematic clock drift."""
        source_id = ts.source_id
        drift_samples = self.clock_drift_samples[source_id]
        
        # Calculate apparent clock offset
        offset_ms = ts.network_latency_ms
        drift_samples.append(offset_ms)
        
        if len(drift_samples) < 100:
            return None
        
        # Calculate calibrated expected latency
        if source_id not in self.expected_latency:
            self.expected_latency[source_id] = statistics.median(drift_samples)
        
        expected = self.expected_latency[source_id]
        current_median = statistics.median(list(drift_samples)[-50:])
        drift = current_median - expected
        
        if abs(drift) > self.clock_drift_max_ms:
            severity = min(1.0, abs(drift) / (self.clock_drift_max_ms * 3))
            return TimestampAnomaly(
                anomaly_type=AnomalyType.CLOCK_DRIFT,
                source_id=source_id,
                symbol=ts.symbol,
                timestamp=datetime.now(),
                severity=severity,
                details=f"Clock drift detected: {drift:.0f}ms from baseline"
            )
        
        return None
    
    def get_metrics(self, source_id: str) -> Optional[Dict[str, Any]]:
        """Get current metrics for a source."""
        if source_id not in self.metrics:
            return None
        return self.metrics[source_id].to_dict()
    
    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics for all sources."""
        return {
            source_id: m.to_dict() 
            for source_id, m in self.metrics.items()
        }


# Prometheus-compatible metrics export
def export_prometheus_metrics(triangulator: TimestampTriangulator) -> str:
    """Export metrics in Prometheus format."""
    lines = []
    
    for source_id, metrics in triangulator.metrics.items():
        safe_source = source_id.replace("-", "_").replace(".", "_")
        
        lines.append(f'himari_network_latency_median_ms{{source="{source_id}"}} {metrics.network_median_ms:.2f}')
        lines.append(f'himari_network_latency_p99_ms{{source="{source_id}"}} {metrics.network_p99_ms:.2f}')
        lines.append(f'himari_processing_latency_median_ms{{source="{source_id}"}} {metrics.processing_median_ms:.2f}')
    
    return "\n".join(lines)


if __name__ == "__main__":
    # Quick test
    triangulator = TimestampTriangulator()
    
    # Simulate some ticks
    for i in range(20):
        ts = triangulator.create_triangulated_timestamp(
            t_exchange=datetime.now() - timedelta(milliseconds=50),
            source_id="binance_ws_btcusdt",
            symbol="BTCUSDT"
        )
        anomalies = triangulator.record_and_check(ts)
        if anomalies:
            print(f"Anomalies: {[a.to_dict() for a in anomalies]}")
    
    print(f"\nMetrics: {triangulator.get_all_metrics()}")
