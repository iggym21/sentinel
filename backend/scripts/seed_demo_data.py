"""One-off script to populate a local SQLite DB with demo data.

Usage:

    cd backend && source venv/bin/activate
    rm -f sentinel.db && alembic upgrade head
    PYTHONPATH=. python scripts/seed_demo_data.py

(`PYTHONPATH=.` is needed for a direct script invocation — `pytest.ini`'s
`pythonpath = .` only applies to pytest's own import machinery, not to a
plain `python scripts/...` run. Same caveat as `scripts/run_analyst.py`.)

What it does
------------
1. Creates the 8 watchlist tickers the frontend is designed around:
   AAPL, MSFT, NVDA, TSLA, AMZN, GOOGL, META, AMD.
2. Force-creates one `Anomaly` (`triggered_analyst_run=True`) for AAPL by
   directly constructing metrics that cross the configured thresholds,
   bypassing `check_thresholds`/`DemoProvider` entirely. This guarantees a
   demo anomaly exists regardless of what `DemoProvider`'s random walk
   happens to produce for AAPL this run.
3. Runs the Analyst for AAPL twice, a few seconds apart, in-process — the
   first run is linked to the forced anomaly via `anomaly_id`; the second
   run has no prior brief for AAPL to diff against *before* the first run
   completes, but by the time the second run executes, `run_analyst_for_ticker`
   finds that first brief as the most recent prior and computes a
   `diff_from_prior` for it automatically (see `_compute_diff_from_prior`
   in `services/analyst_service.py`) — so this guarantees at least one
   non-null `diff_from_prior` regardless of backend/randomness.
4. Runs the Analyst once more for a second ticker (MSFT) so the brief feed
   has more than one entry.

Uses only `DemoProvider` (synthetic, no network) and `EdgarProvider` (SEC
EDGAR, key-free) for providers, and lets `get_reasoning_backend()` resolve
the reasoning backend itself (via `run_analyst_for_ticker(..., backend=None)`)
rather than forcing one — in this offline build that resolves to
`HeuristicBackend` since no `ANTHROPIC_API_KEY` is configured, matching the
same pattern `scripts/run_analyst.py` (Task 11) already uses. Seeding never
requires `ANTHROPIC_API_KEY` or any `ALPACA_*` key, and performs no real
trade execution.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

from database import SessionLocal
from models.anomaly import Anomaly, TriggerType
from models.ticker import Ticker
from providers.demo_provider import DemoProvider
from providers.edgar_provider import EdgarProvider
from services.analyst_service import run_analyst_for_ticker

TICKER_SYMBOLS = ["AAPL", "MSFT", "NVDA", "TSLA", "AMZN", "GOOGL", "META", "AMD"]

# The ticker that gets the forced anomaly + two Analyst runs (history/diff demo).
ANOMALY_TICKER = "AAPL"
# A second ticker that gets one Analyst run, so the brief feed has >1 entries.
SECOND_TICKER = "MSFT"

# Seconds to wait between the two AAPL Analyst runs, so their timestamps are
# clearly distinguishable in the demo UI (not required for diff_from_prior
# correctness, which is ordered by created_at regardless of the gap size).
_RUN_GAP_SECONDS = 3


def _create_tickers(db) -> dict[str, Ticker]:
    """Create the 8 watchlist tickers (or reuse existing rows if re-run)."""
    tickers: dict[str, Ticker] = {}
    for symbol in TICKER_SYMBOLS:
        ticker = db.query(Ticker).filter_by(symbol=symbol).one_or_none()
        if ticker is None:
            ticker = Ticker(
                symbol=symbol,
                added_at=datetime.now(timezone.utc),
                active=True,
            )
            db.add(ticker)
            db.commit()
            db.refresh(ticker)
        tickers[symbol] = ticker
    return tickers


def _force_anomaly(db, ticker: Ticker) -> Anomaly:
    """Directly construct an Anomaly with metrics that would cross the
    configured price-move threshold (3.0%), bypassing `check_thresholds`
    and `DemoProvider` so a demo anomaly is guaranteed regardless of that
    tick's random walk.

    `raw_metrics` matches the shape `threshold_detector.check_thresholds`
    would have produced: {"volume", "avg_volume_20d", "volume_ratio",
    "day_change_pct"}.
    """
    raw_metrics = {
        "volume": 9_800_000,
        "avg_volume_20d": 2_450_000,
        "volume_ratio": 4.0,
        "day_change_pct": 8.7,
    }
    anomaly = Anomaly(
        ticker_id=ticker.id,
        detected_at=datetime.now(timezone.utc),
        trigger_type=TriggerType.price_move,
        raw_metrics=raw_metrics,
        watchdog_rationale=(
            f"Forced demo anomaly: {ticker.symbol} moved {raw_metrics['day_change_pct']}% "
            "in a session on volume 4.0x its 20-day average, well beyond the configured "
            "thresholds. Seeded directly (bypassing check_thresholds/DemoProvider) to "
            "guarantee demo data regardless of that tick's random walk."
        ),
        triggered_analyst_run=True,
    )
    db.add(anomaly)
    db.commit()
    db.refresh(anomaly)
    return anomaly


def main() -> None:
    db = SessionLocal()
    market = DemoProvider()
    filings = EdgarProvider(user_agent="Sentinel demo@example.com")

    briefs_created: list[tuple[str, str, int]] = []

    try:
        print(f"Creating {len(TICKER_SYMBOLS)} watchlist tickers: {', '.join(TICKER_SYMBOLS)}")
        tickers = _create_tickers(db)
        print(f"  -> {len(tickers)} ticker rows present.")

        print(f"\nForcing an anomaly for {ANOMALY_TICKER} (triggered_analyst_run=True)...")
        anomaly = _force_anomaly(db, tickers[ANOMALY_TICKER])
        print(f"  -> Anomaly id={anomaly.id} trigger_type={anomaly.trigger_type.value}")

        print(f"\nRunning Analyst for {ANOMALY_TICKER} (run 1, linked to anomaly {anomaly.id})...")
        brief1 = run_analyst_for_ticker(
            db, ANOMALY_TICKER, market, filings, anomaly_id=anomaly.id
        )
        thesis1 = getattr(brief1.thesis, "value", brief1.thesis)
        briefs_created.append((ANOMALY_TICKER, thesis1, brief1.confidence))
        print(f"  -> Brief id={brief1.id} thesis={thesis1} confidence={brief1.confidence}")

        print(f"\nWaiting {_RUN_GAP_SECONDS}s before the second {ANOMALY_TICKER} run...")
        time.sleep(_RUN_GAP_SECONDS)

        print(f"Running Analyst for {ANOMALY_TICKER} (run 2, no anomaly link)...")
        brief2 = run_analyst_for_ticker(db, ANOMALY_TICKER, market, filings)
        thesis2 = getattr(brief2.thesis, "value", brief2.thesis)
        briefs_created.append((ANOMALY_TICKER, thesis2, brief2.confidence))
        print(f"  -> Brief id={brief2.id} thesis={thesis2} confidence={brief2.confidence}")
        print(f"  -> diff_from_prior: {brief2.diff_from_prior!r}")

        print(f"\nRunning Analyst for {SECOND_TICKER} (brief feed needs >1 entries)...")
        brief3 = run_analyst_for_ticker(db, SECOND_TICKER, market, filings)
        thesis3 = getattr(brief3.thesis, "value", brief3.thesis)
        briefs_created.append((SECOND_TICKER, thesis3, brief3.confidence))
        print(f"  -> Brief id={brief3.id} thesis={thesis3} confidence={brief3.confidence}")

        print("\n=== Seed summary ===")
        print(f"Tickers: {len(tickers)}")
        print(f"Briefs created this run: {len(briefs_created)}")
        for ticker_symbol, thesis, confidence in briefs_created:
            print(f"  {ticker_symbol}: thesis={thesis} confidence={confidence}")
    finally:
        filings.close()
        db.close()


if __name__ == "__main__":
    main()
