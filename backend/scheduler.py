"""APScheduler wiring: runs the Watchdog tick automatically on an
interval, so anomaly detection doesn't depend on someone hitting
`POST /api/watchdog/tick` (`backend/api/runs.py`) by hand.

The scheduled job builds its own `SessionLocal()` + providers on every
run and closes the session afterward — it must not reuse a session or
provider instance across ticks, since `BackgroundScheduler` runs jobs on
a background thread outside any request lifecycle.

Market-hours gate: in production, only actually run the sweep during US
market hours (9:30-16:00 America/New_York, Mon-Fri) so a 15-minute tick
isn't spamming EDGAR/Alpaca/Claude overnight/weekends for no reason. In
non-production environments the gate is skipped entirely so local dev
and demos can trigger a tick at any time of day. No external holiday
calendar for MVP — this is a plain weekday/hours check.
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler

from config import settings
from database import SessionLocal
from providers.factory import build_providers
from services.watchdog_service import run_watchdog_tick

_MARKET_TZ = ZoneInfo("America/New_York")


def _within_market_hours(now: datetime) -> bool:
    if now.weekday() >= 5:  # Saturday=5, Sunday=6
        return False
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
    return market_open <= now <= market_close


def _watchdog_tick_job() -> None:
    if settings.environment == "production" and not _within_market_hours(
        datetime.now(_MARKET_TZ)
    ):
        return

    db = SessionLocal()
    try:
        with build_providers() as (market, filings):
            run_watchdog_tick(db, market, filings)
    finally:
        db.close()


def start_scheduler(app_state) -> BackgroundScheduler:
    """Start the background scheduler and register the Watchdog tick job.

    `app_state` is `app.state` from the FastAPI app's lifespan — the
    running `BackgroundScheduler` is stashed there too so it's reachable
    elsewhere if needed, in addition to being returned for `main.py`'s
    lifespan to call `.shutdown()` on.
    """
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        _watchdog_tick_job,
        "interval",
        minutes=settings.watchdog_interval_minutes,
        id="watchdog_tick",
    )
    scheduler.start()
    app_state.scheduler = scheduler
    return scheduler
