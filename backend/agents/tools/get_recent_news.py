"""Analyst tool: get_recent_news.

Thin adapter from MarketDataProvider.get_recent_news's list[NewsItem]
to a list of plain, JSON-serializable dicts.
"""

from __future__ import annotations

from providers.base import MarketDataProvider


def get_recent_news(
    market: MarketDataProvider, ticker: str, days: int = 7
) -> list[dict]:
    items = market.get_recent_news(ticker, days)
    return [
        {
            "headline": item.headline,
            "summary": item.summary,
            "published_at": item.published_at,
            "source": item.source,
        }
        for item in items
    ]
