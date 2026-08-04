"""Shared provider construction for request-handling call sites.

Every call site that needs live data builds a `MarketDataProvider` (real
`AlpacaProvider` if Alpaca keys are configured, else the free/offline
`DemoProvider`) alongside a real `EdgarProvider` (SEC EDGAR is
free/key-free) — `api/watchlist.py`, `api/tickers.py`, `api/runs.py`,
`scheduler.py`, and `scripts/run_analyst.py` each used to hand-roll this
same pairing. `AlpacaProvider` and `EdgarProvider` each own an
`httpx.Client`, and every one of those duplicated copies except
`scripts/seed_demo_data.py` only closed the market provider in its
`finally` block, leaking the `EdgarProvider`'s client on every call.
Centralizing construction (and closing) here fixes that leak in one
place instead of five.

`AlpacaProvider`'s market-data endpoints (`/v2/stocks/{s}/bars`,
`/v2/stocks/{s}/snapshot`, `/v1beta1/news`) live on Alpaca's *data* host,
not the trading/account host `alpaca_base_url` points at — so this is
also the one place that needs to pass `settings.alpaca_data_url` as
`AlpacaProvider`'s `base_url`.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from config import settings
from providers.alpaca_provider import AlpacaProvider
from providers.demo_provider import DemoProvider
from providers.edgar_provider import EdgarProvider

# Identical literal previously duplicated across api/tickers.py,
# api/runs.py, scheduler.py, and scripts/run_analyst.py.
EDGAR_USER_AGENT = "Sentinel MVP research@sentinel.example"


def build_market_provider() -> AlpacaProvider | DemoProvider:
    """Real `AlpacaProvider` if Alpaca keys are configured, else the
    free/offline `DemoProvider` — matches the "real if keys configured,
    else demo" check every duplicated `_build_market_provider()` used."""
    if settings.alpaca_api_key:
        return AlpacaProvider(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_secret_key,
            base_url=settings.alpaca_data_url,
        )
    return DemoProvider()


@contextmanager
def build_providers() -> Iterator[tuple[AlpacaProvider | DemoProvider, EdgarProvider]]:
    """Build a (market, filings) provider pair and guarantee both get
    closed, even if the caller's body raises."""
    market = build_market_provider()
    filings = EdgarProvider(user_agent=EDGAR_USER_AGENT)
    try:
        yield market, filings
    finally:
        if isinstance(market, AlpacaProvider):
            market.close()
        filings.close()
