"""`/api/watchlist` router: list/add/remove tickers on the watchlist.

`GET /api/watchlist` needs a live price quote per ticker (`latest_price`,
`day_change_pct`), so it builds a `MarketDataProvider` at request time —
same "real if keys configured, else free/offline `DemoProvider`" pattern
`scripts/run_analyst.py` uses. `DemoProvider` is synthetic/no-network, so
this is safe to exercise in tests without any API keys or monkeypatching.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from models.agent_run import AgentRun, RunStatus
from models.anomaly import Anomaly
from models.brief import Brief
from models.ticker import Ticker
from providers.alpaca_provider import AlpacaProvider
from providers.demo_provider import DemoProvider
from schemas.ticker import TickerCreate, TickerOut, WatchlistEntry

router = APIRouter(prefix="/watchlist", tags=["watchlist"])

# How recently an AgentRun triggered by an anomaly must have completed for
# a ticker's status to still read "triggered" rather than falling back to
# "quiet".
_TRIGGERED_WINDOW = timedelta(hours=1)


def _build_market_provider():
    if settings.alpaca_api_key:
        return AlpacaProvider(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_secret_key,
            base_url=settings.alpaca_base_url,
        )
    return DemoProvider()


def _as_utc(dt: datetime) -> datetime:
    """SQLite round-trips `DateTime(timezone=True)` columns as naive; treat
    naive values as UTC (the only timezone anything in this app ever
    writes) so comparisons against `datetime.now(timezone.utc)` don't
    raise."""
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _compute_status(db: Session, ticker_id: int) -> str:
    running = (
        db.query(AgentRun)
        .filter(AgentRun.ticker_id == ticker_id, AgentRun.status == RunStatus.running)
        .first()
    )
    if running is not None:
        return "investigating"

    latest_anomaly = (
        db.query(Anomaly)
        .filter(Anomaly.ticker_id == ticker_id)
        .order_by(desc(Anomaly.detected_at))
        .first()
    )
    if latest_anomaly is not None and latest_anomaly.triggered_analyst_run:
        run = latest_anomaly.agent_run
        if run is not None and run.completed_at is not None:
            if datetime.now(timezone.utc) - _as_utc(run.completed_at) <= _TRIGGERED_WINDOW:
                return "triggered"

    return "quiet"


@router.get("", response_model=list[WatchlistEntry])
def list_watchlist(db: Session = Depends(get_db)) -> list[WatchlistEntry]:
    tickers = db.query(Ticker).filter(Ticker.active.is_(True)).all()
    market = _build_market_provider()

    entries: list[WatchlistEntry] = []
    try:
        for ticker in tickers:
            latest_price: float | None = None
            day_change_pct: float | None = None
            try:
                snapshot = market.get_price_snapshot(ticker.symbol)
                latest_price = snapshot.price
                day_change_pct = snapshot.day_change_pct
            except Exception:
                # A provider hiccup for one ticker's quote shouldn't break
                # the whole watchlist view.
                pass

            last_brief = (
                db.query(Brief)
                .filter(Brief.ticker_id == ticker.id)
                .order_by(desc(Brief.created_at))
                .first()
            )

            entries.append(
                WatchlistEntry(
                    id=ticker.id,
                    symbol=ticker.symbol,
                    added_at=ticker.added_at,
                    active=ticker.active,
                    latest_price=latest_price,
                    day_change_pct=day_change_pct,
                    status=_compute_status(db, ticker.id),
                    last_brief_at=last_brief.created_at if last_brief else None,
                )
            )
    finally:
        if isinstance(market, AlpacaProvider):
            market.close()

    return entries


@router.post("", response_model=TickerOut)
def create_watchlist_entry(body: TickerCreate, db: Session = Depends(get_db)) -> Ticker:
    symbol = body.symbol.strip().upper()
    ticker = db.query(Ticker).filter_by(symbol=symbol).one_or_none()
    if ticker is None:
        ticker = Ticker(symbol=symbol, added_at=datetime.now(timezone.utc), active=True)
        db.add(ticker)
    else:
        ticker.active = True
    db.commit()
    db.refresh(ticker)
    return ticker


@router.delete("/{symbol}", status_code=204)
def delete_watchlist_entry(symbol: str, db: Session = Depends(get_db)) -> None:
    ticker = db.query(Ticker).filter_by(symbol=symbol.strip().upper()).one_or_none()
    if ticker is None:
        raise HTTPException(status_code=404, detail="Ticker not found")
    ticker.active = False
    db.commit()
