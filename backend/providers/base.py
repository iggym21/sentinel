"""Shared provider dataclasses and Protocols.

These types are the contract every market-data / filings provider
(DemoProvider, AlpacaProvider, EdgarProvider, ...) implements or
consumes, and what the Analyst tool functions operate on. Defined
once here so later tasks don't redefine them differently.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass
class PriceSnapshotData:
    ticker: str
    price: float
    volume: int
    day_change_pct: float
    avg_volume_20d: float
    timestamp: str


@dataclass
class OHLCVBar:
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


@dataclass
class NewsItem:
    headline: str
    summary: str
    published_at: str
    source: str


@dataclass
class FilingRef:
    ticker: str
    form_type: str
    filed_at: str
    url: str
    title: str


class MarketDataProvider(Protocol):
    def get_price_snapshot(self, ticker: str) -> PriceSnapshotData: ...

    def get_price_history(self, ticker: str, days: int) -> list[OHLCVBar]: ...

    def get_recent_news(self, ticker: str, days: int) -> list[NewsItem]: ...


class FilingsProvider(Protocol):
    def get_filings(
        self, ticker: str, form_types: list[str] | None, limit: int
    ) -> list[FilingRef]: ...

    def get_filing_text(self, filing_url: str, max_chars: int) -> str: ...
