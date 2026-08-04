"""Deterministic, no-network synthetic market-data provider.

DemoProvider exists so Sentinel can run and be demoed end-to-end with
zero API keys and zero external calls (see plan Global Constraints).
It generates an internally-consistent synthetic price series per
ticker using a random walk seeded from hash(ticker), so repeated
calls within a process are deterministic for a given ticker, but
different tickers produce different series.

Note: Python's str hash is randomized per-process (PYTHONHASHSEED),
so the exact numbers will differ across process runs. That's fine —
determinism is only required within a single process/import, which is
what backs the "same ticker -> same numbers" invariant used by tools
and tests here.
"""

from __future__ import annotations

import random
from datetime import date, datetime, timedelta, timezone

from providers.base import NewsItem, OHLCVBar, PriceSnapshotData

# How many days of history get_price_snapshot derives its numbers from.
_SNAPSHOT_HISTORY_DAYS = 30

_NEWS_TEMPLATES = [
    "{ticker} shares {direction} as investors weigh recent trading activity",
    "What's moving {ticker} today: volume and price action in focus",
    "{ticker} sees notable {gain_loss} amid broader market moves",
    "Analysts watch {ticker} after recent price swings",
]


class DemoProvider:
    """Synthetic MarketDataProvider. No external calls, no API keys."""

    def get_price_history(self, ticker: str, days: int) -> list[OHLCVBar]:
        rng = random.Random(hash(ticker))
        base_price = 50 + (hash(ticker) % 400)
        price = float(base_price)
        today = date.today()
        bars: list[OHLCVBar] = []

        for i in range(days):
            pct_move = rng.gauss(0, 0.015)
            if rng.random() < 0.1:
                pct_move *= 4  # occasional larger move for realism

            open_price = price
            close_price = max(0.01, price * (1 + pct_move))
            wiggle = abs(rng.gauss(0, 0.005))
            high = max(open_price, close_price) * (1 + wiggle)
            low = max(0.01, min(open_price, close_price) * (1 - wiggle))
            volume = int(rng.uniform(500_000, 5_000_000))

            bar_date = today - timedelta(days=(days - 1 - i))
            bars.append(
                OHLCVBar(
                    date=bar_date.isoformat(),
                    open=round(open_price, 2),
                    high=round(high, 2),
                    low=round(low, 2),
                    close=round(close_price, 2),
                    volume=volume,
                )
            )
            price = close_price

        return bars

    def get_price_snapshot(self, ticker: str) -> PriceSnapshotData:
        history = self.get_price_history(ticker, days=_SNAPSHOT_HISTORY_DAYS)
        last = history[-1]
        prev_close = history[-2].close if len(history) > 1 else last.open
        day_change_pct = (
            ((last.close - prev_close) / prev_close) * 100 if prev_close else 0.0
        )
        recent_volumes = [b.volume for b in history[-20:]]
        avg_volume_20d = sum(recent_volumes) / len(recent_volumes)

        return PriceSnapshotData(
            ticker=ticker,
            price=last.close,
            volume=last.volume,
            day_change_pct=round(day_change_pct, 4),
            avg_volume_20d=round(avg_volume_20d, 2),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    def get_recent_news(self, ticker: str, days: int) -> list[NewsItem]:
        rng = random.Random(hash(ticker) + days)
        history = self.get_price_history(ticker, days=max(days, 2))
        prev_close = history[-2].close
        last_close = history[-1].close
        pct = ((last_close - prev_close) / prev_close) * 100 if prev_close else 0.0
        direction = "climb" if pct >= 0 else "slip"
        gain_loss = "gains" if pct >= 0 else "losses"

        templates = [
            t.format(ticker=ticker, direction=direction, gain_loss=gain_loss)
            for t in _NEWS_TEMPLATES
        ]
        count = rng.randint(1, len(templates))
        selected = templates[:count]

        now = datetime.now(timezone.utc)
        return [
            NewsItem(
                headline=headline,
                summary=(
                    f"Recent trading activity in {ticker} shows a "
                    f"{abs(pct):.2f}% move, with market participants "
                    "monitoring volume trends."
                ),
                published_at=(now - timedelta(days=i)).isoformat(),
                source="Sentinel Demo Wire",
            )
            for i, headline in enumerate(selected)
        ]
