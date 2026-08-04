"""Watchdog tick orchestration: sweeps the active watchlist once per tick.

`run_watchdog_tick` is the integration point that ties together:

- `check_thresholds` (Task 6) — pure threshold math over a price snapshot.
- `ReasoningBackend.watchdog_judge` (Task 12) — the Watchdog's judgment
  call on whether a crossed threshold is worth escalating.
- `run_analyst_for_ticker` (Task 11) — the Analyst agent loop, triggered
  only when the Watchdog decides to escalate.

For every `active=True` `Ticker`, it fetches a fresh snapshot + recent
news via `market`, runs `check_thresholds`. If nothing crossed, this is
a quiet check and produces no DB write: the architecture doc's "log a
quiet check" is treated as a no-op for MVP, since persisting a row per
ticker per tick (mostly "nothing happened") would grow an unbounded
`PriceSnapshot` table for no benefit that isn't already covered by the
`Anomaly` history. Snapshots themselves are already documented as "can
be ephemeral" in the spec, so this simplification is in the spirit of
that caveat rather than against it.

If a threshold crossed, the Watchdog is asked to judge whether it's
worth escalating; either way an `Anomaly` row is persisted (this is the
full reasoning trace for the judgment call, at this task's scope — the
per-step `TraceRecorder` trace is only required for the Analyst run,
per Task 11). If the Watchdog says trigger, the Analyst is run and
linked back to the anomaly via `anomaly_id`.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from agents.backend_factory import get_reasoning_backend
from agents.reasoning_backend import ReasoningBackend
from config import settings
from models.anomaly import Anomaly
from models.ticker import Ticker
from providers.base import FilingsProvider, MarketDataProvider
from services.analyst_service import run_analyst_for_ticker
from services.threshold_detector import check_thresholds


def run_watchdog_tick(
    db: Session,
    market: MarketDataProvider,
    filings: FilingsProvider,
    backend: ReasoningBackend | None = None,
) -> list[dict]:
    """Run one Watchdog sweep over every active `Ticker`.

    `backend` is the single reasoning-backend injection point the tests
    use: when provided (e.g. a `MagicMock` in tests), the *same* instance
    is used for both the Watchdog's `watchdog_judge` call and the
    Analyst's `run_analyst` call (via `run_analyst_for_ticker`), which is
    what lets a test assert on `backend.run_analyst.assert_called_once()`
    after only injecting one mock.

    When `backend` is None, `watchdog_judge` and the Analyst run each
    resolve their own default independently via `get_reasoning_backend()`
    — `run_analyst_for_ticker` is called with `backend=None` so it does
    its own resolution. This matches the interface note that Watchdog
    judgment and Analyst investigation are different concerns that may
    reasonably use different backend instances (e.g. a cheap/fast model
    for the quick judgment call vs. a stronger model for the multi-step
    investigation), while still letting a single injected mock drive both
    code paths in a test.

    Returns a list of per-ticker result dicts:
    `{"ticker": symbol, "crossed": bool, "triggered": bool, "anomaly_id": int|None}`
    for the caller (API layer / seed script) to summarize.

    A single ticker's exception (from `market`, `watchdog_judge`, or
    `run_analyst_for_ticker`) is caught per-ticker so it can't abort the
    sweep: that ticker's result dict instead has `"crossed": None`,
    `"triggered": False`, `"anomaly_id": None`, plus an `"error": str(exc)`
    key, and the loop continues to the next ticker.
    """
    watchdog_backend = backend if backend is not None else get_reasoning_backend()

    tickers = db.query(Ticker).filter(Ticker.active.is_(True)).all()

    results: list[dict] = []

    for ticker in tickers:
        try:
            snapshot = market.get_price_snapshot(ticker.symbol)
            news = market.get_recent_news(ticker.symbol, days=3)

            threshold_result = check_thresholds(
                snapshot,
                settings.volume_spike_threshold_multiplier,
                settings.price_move_threshold_pct,
            )

            if not threshold_result.crossed:
                # Quiet check: no DB write. See module docstring for why
                # this is a deliberate no-op rather than a `PriceSnapshot`
                # row.
                results.append(
                    {
                        "ticker": ticker.symbol,
                        "crossed": False,
                        "triggered": False,
                        "anomaly_id": None,
                    }
                )
                continue

            decision = watchdog_backend.watchdog_judge(
                ticker.symbol, threshold_result.raw_metrics, news
            )

            anomaly = Anomaly(
                ticker_id=ticker.id,
                detected_at=datetime.now(timezone.utc),
                trigger_type=threshold_result.trigger_type,
                raw_metrics=threshold_result.raw_metrics,
                watchdog_rationale=decision.rationale,
                triggered_analyst_run=decision.trigger,
            )
            db.add(anomaly)
            db.commit()
            db.refresh(anomaly)

            if decision.trigger:
                run_analyst_for_ticker(
                    db,
                    ticker.symbol,
                    market,
                    filings,
                    anomaly_id=anomaly.id,
                    backend=backend,
                )

            results.append(
                {
                    "ticker": ticker.symbol,
                    "crossed": True,
                    "triggered": decision.trigger,
                    "anomaly_id": anomaly.id,
                }
            )
        except Exception as exc:
            # One ticker's failure (transient Claude API error, provider
            # hiccup, etc.) must not abort the whole sweep: prior results
            # in `results` stay intact and remaining tickers still get
            # processed. Roll back first so a partial `db.add()`/`db.commit()`
            # sequence for *this* ticker (e.g. the anomaly insert failing,
            # or `run_analyst_for_ticker` leaving the session dirty) can't
            # leave the session in a broken state for the next iteration.
            db.rollback()
            results.append(
                {
                    "ticker": ticker.symbol,
                    "crossed": None,
                    "triggered": False,
                    "anomaly_id": None,
                    "error": str(exc),
                }
            )

    return results
