"""
L0-3: Heartbeat Dead Man's Switch
=================================
Automatically cancel all open orders and halt trading if the strategy engine
becomes unresponsive, preventing runaway positions.

Escalation Hierarchy:
1. 1 missed heartbeat: Log warning, increment counter
2. 2 consecutive missed: Alert to monitoring, prepare cancellation
3. 3 consecutive missed: Cancel all open orders (CANCEL_ALL)
4. 5 consecutive missed: Close all positions at market (PANIC_CLOSE)
5. Recovery: Require manual acknowledgment before resuming trading

File: Layer 0 Data infrastructure/src/safety/heartbeat_switch.py
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Callable, List
from enum import Enum
import hashlib
import threading
import time
import logging

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Self-reported health status from strategy engine."""
    OK = "ok"
    DEGRADED = "degraded"
    FAILING = "failing"
    UNKNOWN = "unknown"


class EscalationLevel(Enum):
    """Escalation levels for missed heartbeats."""
    NORMAL = 0
    WARNING = 1       # 1 missed
    ALERT = 2         # 2 consecutive missed
    CANCEL_ALL = 3    # 3 consecutive missed
    PANIC_CLOSE = 5   # 5 consecutive missed
    HALTED = 99       # System halted


@dataclass
class HeartbeatMessage:
    """
    Heartbeat message from strategy engine.
    
    Contents:
    - strategy_id: Which strategy is alive
    - timestamp: When heartbeat was generated
    - positions_hash: Hash of current position state (for consistency check)
    - health_status: Self-reported health (OK, DEGRADED, FAILING)
    """
    strategy_id: str
    timestamp: datetime
    positions_hash: str
    health_status: HealthStatus
    
    # Optional metadata
    active_orders: int = 0
    open_positions: int = 0
    last_trade_time: Optional[datetime] = None
    
    @staticmethod
    def create(
        strategy_id: str,
        positions: Dict[str, Any],
        health_status: HealthStatus = HealthStatus.OK,
        active_orders: int = 0,
        open_positions: int = 0
    ) -> "HeartbeatMessage":
        """Create a new heartbeat message."""
        # Hash the positions for consistency checking
        pos_str = str(sorted(positions.items()))
        pos_hash = hashlib.sha256(pos_str.encode()).hexdigest()[:16]
        
        return HeartbeatMessage(
            strategy_id=strategy_id,
            timestamp=datetime.now(),
            positions_hash=pos_hash,
            health_status=health_status,
            active_orders=active_orders,
            open_positions=open_positions
        )
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "timestamp": self.timestamp.isoformat(),
            "positions_hash": self.positions_hash,
            "health_status": self.health_status.value,
            "active_orders": self.active_orders,
            "open_positions": self.open_positions
        }


@dataclass
class StrategyState:
    """Track state for a single strategy."""
    strategy_id: str
    last_heartbeat: Optional[datetime] = None
    last_positions_hash: Optional[str] = None
    missed_count: int = 0
    escalation_level: EscalationLevel = EscalationLevel.NORMAL
    is_halted: bool = False
    halt_reason: Optional[str] = None
    halt_time: Optional[datetime] = None


class EscalationHandler:
    """
    Handle escalation actions when heartbeats are missed.
    
    Override these methods to integrate with your execution system.
    """
    
    def on_warning(self, strategy_id: str, missed_count: int) -> None:
        """Called on first missed heartbeat."""
        logger.warning(f"[HEARTBEAT] Strategy {strategy_id}: {missed_count} missed heartbeat(s)")
    
    def on_alert(self, strategy_id: str) -> None:
        """Called on 2 consecutive missed heartbeats."""
        logger.error(f"[HEARTBEAT] Strategy {strategy_id}: ALERT - preparing cancellation")
    
    def on_cancel_all(self, strategy_id: str) -> bool:
        """
        Called on 3 consecutive missed heartbeats.
        Should cancel all open orders.
        Returns True if cancellation was successful.
        """
        logger.critical(f"[HEARTBEAT] Strategy {strategy_id}: CANCEL_ALL triggered")
        # Override this to actually cancel orders
        return True
    
    def on_panic_close(self, strategy_id: str) -> bool:
        """
        Called on 5 consecutive missed heartbeats.
        Should close all positions at market.
        Returns True if panic close was successful.
        """
        logger.critical(f"[HEARTBEAT] Strategy {strategy_id}: PANIC_CLOSE triggered")
        # Override this to actually close positions
        return True
    
    def on_recovery(self, strategy_id: str) -> None:
        """Called when heartbeats resume after escalation."""
        logger.info(f"[HEARTBEAT] Strategy {strategy_id}: Heartbeat resumed")
    
    def on_halt(self, strategy_id: str, reason: str) -> None:
        """Called when system is halted."""
        logger.critical(f"[HEARTBEAT] Strategy {strategy_id}: HALTED - {reason}")


class DeadMansSwitch:
    """
    Heartbeat-based dead man's switch for strategy engines.
    
    Configuration Parameters:
    - heartbeat_interval_ms: Expected heartbeat frequency (default: 100)
    - heartbeat_timeout_ms: Timeout before missed heartbeat (default: 150)
    - cancel_threshold: Missed heartbeats before CANCEL_ALL (default: 3)
    - panic_threshold: Missed heartbeats before PANIC_CLOSE (default: 5)
    - recovery_requires_ack: Manual ack required to resume (default: true)
    """
    
    def __init__(
        self,
        heartbeat_interval_ms: int = 100,
        heartbeat_timeout_ms: int = 150,
        cancel_threshold: int = 3,
        panic_threshold: int = 5,
        recovery_requires_ack: bool = True,
        escalation_handler: Optional[EscalationHandler] = None
    ):
        self.heartbeat_interval_ms = heartbeat_interval_ms
        self.heartbeat_timeout_ms = heartbeat_timeout_ms
        self.cancel_threshold = cancel_threshold
        self.panic_threshold = panic_threshold
        self.recovery_requires_ack = recovery_requires_ack
        
        self.handler = escalation_handler or EscalationHandler()
        
        # State tracking per strategy
        self.strategies: Dict[str, StrategyState] = {}
        
        # Monitoring thread
        self._monitor_thread: Optional[threading.Thread] = None
        self._running = False
        self._lock = threading.Lock()
        
        # Callbacks for external monitoring
        self.escalation_callbacks: List[Callable[[str, EscalationLevel], None]] = []
    
    def register_strategy(self, strategy_id: str) -> None:
        """Register a strategy to be monitored."""
        with self._lock:
            if strategy_id not in self.strategies:
                self.strategies[strategy_id] = StrategyState(strategy_id=strategy_id)
                logger.info(f"[HEARTBEAT] Registered strategy: {strategy_id}")
    
    def receive_heartbeat(self, heartbeat: HeartbeatMessage) -> bool:
        """
        Process an incoming heartbeat.
        
        Returns True if heartbeat was accepted, False if strategy is halted.
        """
        with self._lock:
            strategy_id = heartbeat.strategy_id
            
            if strategy_id not in self.strategies:
                self.register_strategy(strategy_id)
            
            state = self.strategies[strategy_id]
            
            # Check if system is halted
            if state.is_halted:
                logger.warning(f"[HEARTBEAT] Strategy {strategy_id} is HALTED, heartbeat ignored")
                return False
            
            # Check for position hash mismatch (optional consistency check)
            if state.last_positions_hash and heartbeat.positions_hash != state.last_positions_hash:
                logger.warning(f"[HEARTBEAT] Strategy {strategy_id}: position hash changed")
            
            # Reset missed count and update state
            was_escalated = state.escalation_level != EscalationLevel.NORMAL
            state.last_heartbeat = heartbeat.timestamp
            state.last_positions_hash = heartbeat.positions_hash
            state.missed_count = 0
            state.escalation_level = EscalationLevel.NORMAL
            
            # Handle recovery
            if was_escalated:
                self.handler.on_recovery(strategy_id)
            
            return True
    
    def check_heartbeats(self) -> Dict[str, EscalationLevel]:
        """
        Check all strategies for missed heartbeats.
        
        Call this periodically (typically from monitoring thread).
        Returns dict of strategy_id -> escalation_level.
        """
        now = datetime.now()
        timeout = timedelta(milliseconds=self.heartbeat_timeout_ms)
        results = {}
        
        with self._lock:
            for strategy_id, state in self.strategies.items():
                if state.is_halted:
                    results[strategy_id] = EscalationLevel.HALTED
                    continue
                
                if state.last_heartbeat is None:
                    # Never received a heartbeat
                    continue
                
                time_since_heartbeat = now - state.last_heartbeat
                
                if time_since_heartbeat > timeout:
                    # Missed heartbeat
                    state.missed_count += 1
                    self._escalate(strategy_id, state)
                
                results[strategy_id] = state.escalation_level
        
        return results
    
    def _escalate(self, strategy_id: str, state: StrategyState) -> None:
        """Handle escalation based on missed count."""
        missed = state.missed_count
        old_level = state.escalation_level
        
        if missed >= self.panic_threshold:
            state.escalation_level = EscalationLevel.PANIC_CLOSE
            if old_level != EscalationLevel.PANIC_CLOSE:
                success = self.handler.on_panic_close(strategy_id)
                if success:
                    self._halt_strategy(strategy_id, "PANIC_CLOSE executed")
        
        elif missed >= self.cancel_threshold:
            state.escalation_level = EscalationLevel.CANCEL_ALL
            if old_level != EscalationLevel.CANCEL_ALL:
                self.handler.on_cancel_all(strategy_id)
        
        elif missed >= 2:
            state.escalation_level = EscalationLevel.ALERT
            if old_level != EscalationLevel.ALERT:
                self.handler.on_alert(strategy_id)
        
        elif missed >= 1:
            state.escalation_level = EscalationLevel.WARNING
            self.handler.on_warning(strategy_id, missed)
        
        # Notify callbacks
        if state.escalation_level != old_level:
            for callback in self.escalation_callbacks:
                try:
                    callback(strategy_id, state.escalation_level)
                except Exception:
                    pass
    
    def _halt_strategy(self, strategy_id: str, reason: str) -> None:
        """Halt a strategy."""
        state = self.strategies[strategy_id]
        state.is_halted = True
        state.halt_reason = reason
        state.halt_time = datetime.now()
        state.escalation_level = EscalationLevel.HALTED
        self.handler.on_halt(strategy_id, reason)
    
    def acknowledge_recovery(self, strategy_id: str) -> bool:
        """
        Manually acknowledge recovery and allow trading to resume.
        
        Required when recovery_requires_ack is True.
        Returns True if strategy was unhalted.
        """
        with self._lock:
            if strategy_id not in self.strategies:
                return False
            
            state = self.strategies[strategy_id]
            if not state.is_halted:
                return True
            
            # Reset state
            state.is_halted = False
            state.halt_reason = None
            state.halt_time = None
            state.missed_count = 0
            state.escalation_level = EscalationLevel.NORMAL
            
            logger.info(f"[HEARTBEAT] Strategy {strategy_id}: Recovery acknowledged, trading resumed")
            return True
    
    def start_monitoring(self) -> None:
        """Start the background monitoring thread."""
        if self._running:
            return
        
        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("[HEARTBEAT] Monitoring started")
    
    def stop_monitoring(self) -> None:
        """Stop the background monitoring thread."""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1.0)
            self._monitor_thread = None
        logger.info("[HEARTBEAT] Monitoring stopped")
    
    def _monitor_loop(self) -> None:
        """Background monitoring loop."""
        check_interval = self.heartbeat_timeout_ms / 1000.0
        
        while self._running:
            self.check_heartbeats()
            time.sleep(check_interval)
    
    def get_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all monitored strategies."""
        with self._lock:
            return {
                strategy_id: {
                    "last_heartbeat": state.last_heartbeat.isoformat() if state.last_heartbeat else None,
                    "missed_count": state.missed_count,
                    "escalation_level": state.escalation_level.name,
                    "is_halted": state.is_halted,
                    "halt_reason": state.halt_reason
                }
                for strategy_id, state in self.strategies.items()
            }
    
    def is_strategy_healthy(self, strategy_id: str) -> bool:
        """Check if a strategy is healthy and can trade."""
        with self._lock:
            if strategy_id not in self.strategies:
                return False
            state = self.strategies[strategy_id]
            return not state.is_halted and state.escalation_level == EscalationLevel.NORMAL


# Example integration with execution gateway
class ExecutionGatewayHandler(EscalationHandler):
    """Example handler that integrates with an execution gateway."""
    
    def __init__(self, gateway_client=None):
        self.gateway = gateway_client
    
    def on_cancel_all(self, strategy_id: str) -> bool:
        """Cancel all orders via gateway."""
        logger.critical(f"[GATEWAY] Sending CANCEL_ALL for {strategy_id}")
        if self.gateway:
            try:
                # self.gateway.cancel_all_orders(strategy_id)
                return True
            except Exception as e:
                logger.error(f"[GATEWAY] Cancel failed: {e}")
                return False
        return True
    
    def on_panic_close(self, strategy_id: str) -> bool:
        """Close all positions via gateway."""
        logger.critical(f"[GATEWAY] Sending PANIC_CLOSE for {strategy_id}")
        if self.gateway:
            try:
                # self.gateway.market_close_all(strategy_id)
                return True
            except Exception as e:
                logger.error(f"[GATEWAY] Panic close failed: {e}")
                return False
        return True


if __name__ == "__main__":
    # Quick test
    logging.basicConfig(level=logging.INFO)
    
    switch = DeadMansSwitch(
        heartbeat_interval_ms=100,
        heartbeat_timeout_ms=150,
        cancel_threshold=3,
        panic_threshold=5
    )
    
    # Register and send heartbeats
    heartbeat = HeartbeatMessage.create(
        strategy_id="himari_btc",
        positions={"BTCUSDT": 0.1},
        health_status=HealthStatus.OK
    )
    
    switch.receive_heartbeat(heartbeat)
    print(f"Status: {switch.get_status()}")
    print(f"Healthy: {switch.is_strategy_healthy('himari_btc')}")
    
    # Simulate missed heartbeats
    for i in range(6):
        switch.check_heartbeats()
        time.sleep(0.2)
        print(f"After {i+1} checks: {switch.get_status()}")
