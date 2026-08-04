"""Analyst tool: get_price_history.

Thin adapter from MarketDataProvider.get_price_history's list[OHLCVBar]
to a list of plain, JSON-serializable dicts — this result gets stored
in AgentRun.trace (a JSON column) and sent back to the Claude API as
tool_result content, so it must never leak a dataclass instance.
"""

from __future__ import annotations

from providers.base import MarketDataProvider


def get_price_history(
    market: MarketDataProvider, ticker: str, days: int = 30
) -> list[dict]:
    bars = market.get_price_history(ticker, days)
    return [
        {
            "date": bar.date,
            "open": bar.open,
            "high": bar.high,
            "low": bar.low,
            "close": bar.close,
            "volume": bar.volume,
        }
        for bar in bars
    ]
