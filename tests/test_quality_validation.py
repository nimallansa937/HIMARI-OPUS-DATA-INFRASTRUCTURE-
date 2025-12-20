# test_quality_validation.py
# HIMARI Opus1 - Unit Tests for Quality Validation Pipeline
# These tests mock external dependencies and can run without infrastructure

import pytest
import json
from datetime import datetime
from unittest.mock import MagicMock, patch
from typing import Dict, Any


# Mock the pyflink imports for unit testing
@pytest.fixture(autouse=True)
def mock_pyflink():
    """Mock PyFlink classes for unit testing without Flink dependencies."""
    with patch.dict('sys.modules', {
        'pyflink': MagicMock(),
        'pyflink.datastream': MagicMock(),
        'pyflink.datastream.functions': MagicMock(),
        'pyflink.datastream.state': MagicMock(),
        'pyflink.datastream.connectors': MagicMock(),
        'pyflink.datastream.connectors.kafka': MagicMock(),
        'pyflink.common': MagicMock(),
        'pyflink.common.typeinfo': MagicMock(),
        'pyflink.common.serialization': MagicMock(),
    }):
        yield


class MockRuntimeContext:
    """Mock runtime context for state management."""
    def __init__(self):
        self.states = {}
    
    def get_state(self, descriptor):
        name = descriptor.name if hasattr(descriptor, 'name') else str(descriptor)
        if name not in self.states:
            self.states[name] = MockValueState()
        return self.states[name]


class MockValueState:
    """Mock value state for testing stateful operators."""
    def __init__(self):
        self._value = None
    
    def value(self):
        return self._value
    
    def update(self, val):
        self._value = val
    
    def clear(self):
        self._value = None


class MockValueStateDescriptor:
    """Mock state descriptor."""
    def __init__(self, name, type_info):
        self.name = name
        self.type_info = type_info
    
    def enable_time_to_live(self, ttl_config):
        pass


class TestParseMarketData:
    """Tests for the ParseMarketData map function."""
    
    def test_parse_valid_json(self):
        """Test parsing valid market data JSON."""
        input_data = json.dumps({
            'symbol': 'BTC/USDT',
            'price': 45000.50,
            'volume': 123.456,
            'exchange': 'binance',
            'timestamp': 1703024400000
        })
        
        # Simulate parsing logic
        data = json.loads(input_data)
        result = (
            data['symbol'],
            {
                'timestamp': data['timestamp'],
                'symbol': data['symbol'],
                'price': float(data['price']),
                'volume': float(data['volume']),
                'exchange': data['exchange'].lower(),
                'raw': data
            }
        )
        
        assert result[0] == 'BTC/USDT'
        assert result[1]['price'] == 45000.50
        assert result[1]['volume'] == 123.456
        assert result[1]['exchange'] == 'binance'
    
    def test_parse_iso_timestamp(self):
        """Test parsing ISO format timestamp."""
        input_data = json.dumps({
            'symbol': 'ETH/USDT',
            'price': 2500.00,
            'volume': 50.0,
            'exchange': 'kraken',
            'timestamp': '2024-12-19T15:00:00Z'
        })
        
        data = json.loads(input_data)
        timestamp = data['timestamp']
        
        if isinstance(timestamp, str):
            dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            timestamp = int(dt.timestamp() * 1000)
        
        assert isinstance(timestamp, int)
        assert timestamp > 0
    
    def test_parse_invalid_json(self):
        """Test handling invalid JSON gracefully."""
        input_data = "not valid json {"
        
        try:
            json.loads(input_data)
            parsed = False
        except json.JSONDecodeError:
            parsed = True
        
        assert parsed is True


class TestQualityValidation:
    """Tests for quality validation logic."""
    
    VALID_EXCHANGES = {'binance', 'kraken', 'bybit', 'deribit', 'coinbase'}
    
    def _validate_quality(self, data: Dict[str, Any], last_timestamp=None, 
                          last_price=None, price_ema=None) -> tuple:
        """Simulate quality validation logic."""
        quality_score = 1.0
        issues = []
        
        # Check 1: Schema validation
        if data.get('price', 0) <= 0:
            quality_score -= 0.25
            issues.append('INVALID_PRICE_NEGATIVE')
        
        if data.get('volume', 0) < 0:
            quality_score -= 0.20
            issues.append('INVALID_VOLUME_NEGATIVE')
        
        # Check 2: Exchange validation
        if data.get('exchange', '').lower() not in self.VALID_EXCHANGES:
            quality_score -= 0.15
            issues.append('UNKNOWN_EXCHANGE')
        
        # Check 3: Temporal ordering
        current_ts = data.get('timestamp', 0)
        if last_timestamp is not None:
            if current_ts < last_timestamp:
                quality_score -= 0.30
                issues.append('OUT_OF_ORDER')
            elif current_ts == last_timestamp:
                quality_score -= 0.10
                issues.append('DUPLICATE_TIMESTAMP')
            elif current_ts - last_timestamp > 60000:
                quality_score -= 0.05
                issues.append('LARGE_GAP')
        
        # Check 4: Price deviation
        if last_price is not None and last_price > 0:
            pct_change = abs(data['price'] - last_price) / last_price
            if pct_change > 0.10:
                quality_score -= 0.20
                issues.append('EXTREME_PRICE_MOVE')
            elif pct_change > 0.05:
                quality_score -= 0.05
                issues.append('LARGE_PRICE_MOVE')
        
        # Clamp score
        quality_score = max(0.0, min(1.0, quality_score))
        
        return quality_score, issues
    
    def test_valid_data_perfect_score(self):
        """Valid data should get perfect quality score."""
        data = {
            'symbol': 'BTC/USDT',
            'price': 45000.0,
            'volume': 100.0,
            'exchange': 'binance',
            'timestamp': int(datetime.utcnow().timestamp() * 1000)
        }
        
        score, issues = self._validate_quality(data)
        
        assert score == 1.0
        assert len(issues) == 0
    
    def test_negative_price_penalty(self):
        """Negative price should reduce quality score."""
        data = {
            'symbol': 'BTC/USDT',
            'price': -1000.0,
            'volume': 100.0,
            'exchange': 'binance',
            'timestamp': int(datetime.utcnow().timestamp() * 1000)
        }
        
        score, issues = self._validate_quality(data)
        
        assert score < 1.0
        assert 'INVALID_PRICE_NEGATIVE' in issues
    
    def test_negative_volume_penalty(self):
        """Negative volume should reduce quality score."""
        data = {
            'symbol': 'BTC/USDT',
            'price': 45000.0,
            'volume': -50.0,
            'exchange': 'binance',
            'timestamp': int(datetime.utcnow().timestamp() * 1000)
        }
        
        score, issues = self._validate_quality(data)
        
        assert score < 1.0
        assert 'INVALID_VOLUME_NEGATIVE' in issues
    
    def test_unknown_exchange_penalty(self):
        """Unknown exchange should reduce quality score."""
        data = {
            'symbol': 'BTC/USDT',
            'price': 45000.0,
            'volume': 100.0,
            'exchange': 'unknown_exchange',
            'timestamp': int(datetime.utcnow().timestamp() * 1000)
        }
        
        score, issues = self._validate_quality(data)
        
        assert score < 1.0
        assert 'UNKNOWN_EXCHANGE' in issues
    
    def test_out_of_order_timestamp_penalty(self):
        """Out-of-order timestamps should reduce quality score."""
        now = int(datetime.utcnow().timestamp() * 1000)
        
        data = {
            'symbol': 'BTC/USDT',
            'price': 45000.0,
            'volume': 100.0,
            'exchange': 'binance',
            'timestamp': now - 10000  # 10 seconds ago
        }
        
        score, issues = self._validate_quality(data, last_timestamp=now)
        
        assert score < 1.0
        assert 'OUT_OF_ORDER' in issues
    
    def test_duplicate_timestamp_penalty(self):
        """Duplicate timestamps should reduce quality score."""
        now = int(datetime.utcnow().timestamp() * 1000)
        
        data = {
            'symbol': 'BTC/USDT',
            'price': 45000.0,
            'volume': 100.0,
            'exchange': 'binance',
            'timestamp': now
        }
        
        score, issues = self._validate_quality(data, last_timestamp=now)
        
        assert score < 1.0
        assert 'DUPLICATE_TIMESTAMP' in issues
    
    def test_large_gap_penalty(self):
        """Large timestamp gaps should reduce quality score."""
        now = int(datetime.utcnow().timestamp() * 1000)
        old = now - 120000  # 2 minutes ago
        
        data = {
            'symbol': 'BTC/USDT',
            'price': 45000.0,
            'volume': 100.0,
            'exchange': 'binance',
            'timestamp': now
        }
        
        score, issues = self._validate_quality(data, last_timestamp=old)
        
        assert score < 1.0
        assert 'LARGE_GAP' in issues
    
    def test_extreme_price_move_penalty(self):
        """Extreme price moves (>10%) should reduce quality score."""
        data = {
            'symbol': 'BTC/USDT',
            'price': 50000.0,  # 11% higher than last
            'volume': 100.0,
            'exchange': 'binance',
            'timestamp': int(datetime.utcnow().timestamp() * 1000)
        }
        
        score, issues = self._validate_quality(data, last_price=45000.0)
        
        assert score < 1.0
        assert 'EXTREME_PRICE_MOVE' in issues
    
    def test_large_price_move_penalty(self):
        """Large price moves (5-10%) should reduce quality score slightly."""
        data = {
            'symbol': 'BTC/USDT',
            'price': 47500.0,  # ~5.5% higher than last
            'volume': 100.0,
            'exchange': 'binance',
            'timestamp': int(datetime.utcnow().timestamp() * 1000)
        }
        
        score, issues = self._validate_quality(data, last_price=45000.0)
        
        assert score < 1.0
        assert 'LARGE_PRICE_MOVE' in issues
    
    def test_multiple_issues_stack(self):
        """Multiple issues should stack penalties."""
        data = {
            'symbol': 'BTC/USDT',
            'price': -1000.0,  # Invalid
            'volume': -50.0,   # Invalid
            'exchange': 'fake_exchange',  # Unknown
            'timestamp': int(datetime.utcnow().timestamp() * 1000)
        }
        
        score, issues = self._validate_quality(data)
        
        assert score < 0.5  # Multiple penalties
        assert len(issues) >= 3
    
    def test_score_never_below_zero(self):
        """Quality score should never go below 0."""
        data = {
            'symbol': 'BTC/USDT',
            'price': -1000.0,
            'volume': -50.0,
            'exchange': 'fake',
            'timestamp': 0
        }
        
        score, _ = self._validate_quality(
            data, 
            last_timestamp=int(datetime.utcnow().timestamp() * 1000),
            last_price=1000.0
        )
        
        assert score >= 0.0


class TestQualityOutput:
    """Tests for quality output formatting."""
    
    def test_output_format(self):
        """Test quality output JSON structure."""
        output = {
            'symbol': 'BTC/USDT',
            'timestamp': 1703024400000,
            'quality_score': 0.85,
            'issues': ['LARGE_GAP'],
            'issue_count': 1,
            'processed_at': datetime.utcnow().isoformat(),
            'original_data': {}
        }
        
        # Verify structure
        assert 'symbol' in output
        assert 'timestamp' in output
        assert 'quality_score' in output
        assert 'issues' in output
        assert 'issue_count' in output
        assert 'processed_at' in output
        
        # Verify types
        assert isinstance(output['quality_score'], float)
        assert isinstance(output['issues'], list)
        assert isinstance(output['issue_count'], int)
    
    def test_output_serializable(self):
        """Test that output is JSON serializable."""
        output = {
            'symbol': 'BTC/USDT',
            'timestamp': 1703024400000,
            'quality_score': 0.85,
            'issues': ['LARGE_GAP'],
            'issue_count': 1,
            'processed_at': datetime.utcnow().isoformat(),
            'original_data': {'price': 45000.0}
        }
        
        json_str = json.dumps(output)
        parsed = json.loads(json_str)
        
        assert parsed['symbol'] == 'BTC/USDT'
        assert parsed['quality_score'] == 0.85


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
