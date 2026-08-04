"""Threshold-based anomaly detector for price snapshots.

Pure function to check if a PriceSnapshotData crosses configured thresholds
for volume spikes or price moves.
"""

from dataclasses import dataclass
from providers.base import PriceSnapshotData


@dataclass
class ThresholdResult:
    """Result of a threshold check."""
    crossed: bool
    trigger_type: str | None  # "volume_spike" | "price_move" | None
    raw_metrics: dict          # {"volume": .., "avg_volume_20d": .., "volume_ratio": .., "day_change_pct": ..}


def check_thresholds(
    snapshot: PriceSnapshotData,
    volume_multiplier: float,
    price_move_pct: float
) -> ThresholdResult:
    """Check if a price snapshot crosses volume or price-move thresholds.

    Args:
        snapshot: Current price snapshot data
        volume_multiplier: Threshold multiplier for volume spike detection
        price_move_pct: Threshold percentage for price move detection

    Returns:
        ThresholdResult with crossed status, trigger type, and raw metrics.
        If both volume and price cross, price_move takes precedence.
        raw_metrics always includes volume, avg_volume_20d, volume_ratio, day_change_pct.
    """
    # Calculate metrics
    volume_ratio = snapshot.volume / snapshot.avg_volume_20d

    # Check thresholds
    volume_crossed = volume_ratio > volume_multiplier
    price_crossed = abs(snapshot.day_change_pct) > price_move_pct

    # Determine trigger type (price_move takes precedence)
    if price_crossed:
        trigger_type = "price_move"
    elif volume_crossed:
        trigger_type = "volume_spike"
    else:
        trigger_type = None

    # Build raw metrics (always includes all metrics regardless of which crossed)
    raw_metrics = {
        "volume": snapshot.volume,
        "avg_volume_20d": snapshot.avg_volume_20d,
        "volume_ratio": volume_ratio,
        "day_change_pct": snapshot.day_change_pct,
    }

    # Determine if crossed
    crossed = volume_crossed or price_crossed

    return ThresholdResult(
        crossed=crossed,
        trigger_type=trigger_type,
        raw_metrics=raw_metrics,
    )
