from providers.base import PriceSnapshotData
from services.threshold_detector import check_thresholds

def make_snapshot(volume=1_000_000, avg_volume=1_000_000, day_change_pct=0.5):
    return PriceSnapshotData(ticker="AAPL", price=190.0, volume=volume, day_change_pct=day_change_pct, avg_volume_20d=avg_volume, timestamp="2026-08-04T14:00:00Z")

def test_quiet_day_does_not_cross():
    result = check_thresholds(make_snapshot(), volume_multiplier=2.0, price_move_pct=3.0)
    assert result.crossed is False
    assert result.trigger_type is None

def test_volume_spike_crosses():
    result = check_thresholds(make_snapshot(volume=2_500_000, avg_volume=1_000_000), volume_multiplier=2.0, price_move_pct=3.0)
    assert result.crossed is True
    assert result.trigger_type == "volume_spike"
    assert result.raw_metrics["volume_ratio"] == 2.5

def test_price_move_crosses():
    result = check_thresholds(make_snapshot(day_change_pct=4.2), volume_multiplier=2.0, price_move_pct=3.0)
    assert result.crossed is True
    assert result.trigger_type == "price_move"

def test_price_move_takes_precedence_when_both_cross():
    result = check_thresholds(make_snapshot(volume=3_000_000, avg_volume=1_000_000, day_change_pct=5.0), volume_multiplier=2.0, price_move_pct=3.0)
    assert result.trigger_type == "price_move"
    assert "volume_ratio" in result.raw_metrics
