from unittest.mock import MagicMock
from datetime import datetime, timezone
from providers.base import PriceSnapshotData
from models.ticker import Ticker
from models.anomaly import Anomaly
from agents.reasoning_backend import WatchdogDecision, AnalystBriefResult
from services.watchdog_service import run_watchdog_tick

def test_quiet_ticker_produces_no_anomaly(db_session):
    t = Ticker(symbol="AAPL", added_at=datetime.now(timezone.utc), active=True)
    db_session.add(t); db_session.commit()
    market = MagicMock()
    market.get_price_snapshot.return_value = PriceSnapshotData(ticker="AAPL", price=190, volume=1_000_000, day_change_pct=0.3, avg_volume_20d=1_000_000, timestamp="t")
    market.get_recent_news.return_value = []
    results = run_watchdog_tick(db_session, market, MagicMock())
    assert results == [{"ticker": "AAPL", "crossed": False, "triggered": False, "anomaly_id": None}]
    assert db_session.query(Anomaly).count() == 0

def test_crossed_but_not_triggered_creates_anomaly_without_analyst_run(db_session):
    t = Ticker(symbol="AAPL", added_at=datetime.now(timezone.utc), active=True)
    db_session.add(t); db_session.commit()
    market = MagicMock()
    market.get_price_snapshot.return_value = PriceSnapshotData(ticker="AAPL", price=190, volume=2_500_000, day_change_pct=0.5, avg_volume_20d=1_000_000, timestamp="t")
    market.get_recent_news.return_value = []
    backend = MagicMock()
    backend.watchdog_judge.return_value = WatchdogDecision(trigger=False, rationale="Just noise.")

    results = run_watchdog_tick(db_session, market, MagicMock(), backend=backend)

    assert results[0]["crossed"] is True
    assert results[0]["triggered"] is False
    anomaly = db_session.query(Anomaly).one()
    assert anomaly.triggered_analyst_run is False

def test_crossed_and_triggered_runs_analyst(db_session):
    t = Ticker(symbol="AAPL", added_at=datetime.now(timezone.utc), active=True)
    db_session.add(t); db_session.commit()
    market = MagicMock()
    market.get_price_snapshot.return_value = PriceSnapshotData(ticker="AAPL", price=190, volume=3_000_000, day_change_pct=4.0, avg_volume_20d=1_000_000, timestamp="t")
    market.get_recent_news.return_value = []
    backend = MagicMock()
    backend.watchdog_judge.return_value = WatchdogDecision(trigger=True, rationale="Big move, real news.")
    backend.run_analyst.return_value = AnalystBriefResult(thesis="bullish", confidence=4, summary="s", evidence=[], diff_from_prior=None, suggested_action=None)

    results = run_watchdog_tick(db_session, market, MagicMock(), backend=backend)

    assert results[0]["triggered"] is True
    anomaly = db_session.query(Anomaly).one()
    assert anomaly.triggered_analyst_run is True
    backend.run_analyst.assert_called_once()
