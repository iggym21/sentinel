"""Analyst tool: calculate_ratios.

Derives what's actually computable for the MVP — rolling volatility,
short/medium-term price trend, and volume trend — from
MarketDataProvider.get_price_history alone. There is no fundamentals
data source (P/E, revenue growth, margins) configured for this MVP, so
rather than fabricate those numbers, the `note` field says so plainly
and the agent/prompt layer is expected to treat this as a
price-action-only signal.
"""

from __future__ import annotations

import statistics

from providers.base import MarketDataProvider

# Enough history to cover the longest trend window (60d).
_HISTORY_DAYS = 60


def _trend_pct(closes: list[float], window: int) -> float | None:
    slice_ = closes[-window:] if len(closes) >= window else closes
    if len(slice_) < 2 or slice_[0] == 0:
        return None
    return round(((slice_[-1] - slice_[0]) / slice_[0]) * 100, 4)


def calculate_ratios(market: MarketDataProvider, ticker: str) -> dict:
    bars = market.get_price_history(ticker, days=_HISTORY_DAYS)
    closes = [bar.close for bar in bars]
    volumes = [bar.volume for bar in bars]

    daily_returns = [
        (closes[i] - closes[i - 1]) / closes[i - 1]
        for i in range(1, len(closes))
        if closes[i - 1]
    ]
    vol_window = daily_returns[-20:] if len(daily_returns) >= 20 else daily_returns
    volatility_20d_pct = (
        round(statistics.pstdev(vol_window) * 100, 4) if len(vol_window) >= 2 else None
    )

    vol_slice = volumes[-20:] if len(volumes) >= 20 else volumes
    avg_volume_20d = round(sum(vol_slice) / len(vol_slice), 2) if vol_slice else None

    return {
        "ticker": ticker,
        "volatility_20d_pct": volatility_20d_pct,
        "trend_5d_pct": _trend_pct(closes, 5),
        "trend_20d_pct": _trend_pct(closes, 20),
        "avg_volume_20d": avg_volume_20d,
        "note": (
            "Derived from price/volume history only; no fundamentals "
            "data source configured for this MVP."
        ),
    }
