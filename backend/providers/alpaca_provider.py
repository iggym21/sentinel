"""Real Alpaca Markets API integration.

AlpacaProvider implements MarketDataProvider against Alpaca's REST API,
hitting:
  - GET /v2/stocks/{symbol}/bars      -> get_price_history
  - GET /v2/stocks/{symbol}/snapshot  -> get_price_snapshot
  - GET /v1beta1/news                 -> get_recent_news

Auth is via the APCA-API-KEY-ID / APCA-API-SECRET-KEY headers Alpaca
expects on every request. Only exercised live if the caller supplies a
real api_key/secret_key (see backend/config.py); tests mock all HTTP
via respx, so no network access or real credentials are needed to run
this module's test suite.

Note: `get_price_snapshot` reads current price/volume/timestamp from
the snapshot endpoint's dailyBar (falling back to latestTrade), but
derives `day_change_pct` and `avg_volume_20d` from a fresh 20-day
`get_price_history` call rather than from the snapshot payload itself
- this keeps those two derived numbers consistent with whatever
get_price_history returns elsewhere in the app.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx

from providers.base import NewsItem, OHLCVBar, PriceSnapshotData

_SNAPSHOT_HISTORY_DAYS = 20


class AlpacaProvider:
    """MarketDataProvider backed by the real Alpaca Markets REST API."""

    def __init__(self, api_key: str, secret_key: str, base_url: str) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            headers={
                "APCA-API-KEY-ID": api_key,
                "APCA-API-SECRET-KEY": secret_key,
            },
            timeout=10.0,
        )

    def close(self) -> None:
        self._client.close()

    def get_price_history(self, ticker: str, days: int) -> list[OHLCVBar]:
        start = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
        response = self._client.get(
            f"/v2/stocks/{ticker}/bars",
            params={"timeframe": "1Day", "start": start, "limit": days},
        )
        response.raise_for_status()
        data = response.json()

        return [
            OHLCVBar(
                date=bar["t"],
                open=bar["o"],
                high=bar["h"],
                low=bar["l"],
                close=bar["c"],
                volume=bar["v"],
            )
            for bar in (data.get("bars") or [])
        ]

    def get_price_snapshot(self, ticker: str) -> PriceSnapshotData:
        response = self._client.get(f"/v2/stocks/{ticker}/snapshot")
        response.raise_for_status()
        data = response.json()

        daily_bar = data.get("dailyBar") or {}
        latest_trade = data.get("latestTrade") or {}

        price = daily_bar.get("c", latest_trade.get("p", 0.0))
        volume = daily_bar.get("v", latest_trade.get("s", 0))
        timestamp = (
            daily_bar.get("t")
            or latest_trade.get("t")
            or datetime.now(timezone.utc).isoformat()
        )

        history = self.get_price_history(ticker, days=_SNAPSHOT_HISTORY_DAYS)

        if len(history) >= 2:
            prev_close = history[-2].close
            last_close = history[-1].close
            day_change_pct = (
                ((last_close - prev_close) / prev_close) * 100 if prev_close else 0.0
            )
        else:
            day_change_pct = 0.0

        if history:
            avg_volume_20d = sum(bar.volume for bar in history) / len(history)
        else:
            avg_volume_20d = 0.0

        return PriceSnapshotData(
            ticker=ticker,
            price=price,
            volume=volume,
            day_change_pct=round(day_change_pct, 4),
            avg_volume_20d=round(avg_volume_20d, 2),
            timestamp=timestamp,
        )

    def get_recent_news(self, ticker: str, days: int) -> list[NewsItem]:
        start = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
        response = self._client.get(
            "/v1beta1/news",
            params={"symbols": ticker, "start": start},
        )
        response.raise_for_status()
        data = response.json()

        return [
            NewsItem(
                headline=item["headline"],
                summary=item.get("summary", ""),
                published_at=item["created_at"],
                source=item.get("source", ""),
            )
            for item in (data.get("news") or [])
        ]
