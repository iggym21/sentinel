from fastapi.testclient import TestClient
from datetime import datetime, timezone
import main
from database import get_db
from models.ticker import Ticker

def make_client(db_session):
    main.app.dependency_overrides[get_db] = lambda: db_session
    return TestClient(main.app)

def test_post_and_get_watchlist(db_session):
    client = make_client(db_session)
    resp = client.post("/api/watchlist", json={"symbol": "AAPL"})
    assert resp.status_code == 200
    assert resp.json()["symbol"] == "AAPL"

    resp = client.get("/api/watchlist")
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["symbol"] == "AAPL"
    assert body[0]["status"] == "quiet"

def test_watchlist_status_not_triggered_when_run_failed(db_session):
    # Finding 1 regression test: an Anomaly with triggered_analyst_run=True
    # whose linked AgentRun failed (status="failed", but completed_at is
    # still set — see services/analyst_service.py's except block) must NOT
    # report status "triggered". A failed run isn't actively investigating
    # and produced no fresh Brief, so the watchlist should fall through to
    # "quiet" instead.
    from models.agent_run import AgentRun
    from models.anomaly import Anomaly

    t = Ticker(symbol="AAPL", added_at=datetime.now(timezone.utc), active=True)
    db_session.add(t); db_session.commit(); db_session.refresh(t)

    anomaly = Anomaly(
        ticker_id=t.id,
        detected_at=datetime.now(timezone.utc),
        trigger_type="volume_spike",
        raw_metrics={},
        watchdog_rationale="test",
        triggered_analyst_run=True,
    )
    db_session.add(anomaly); db_session.commit(); db_session.refresh(anomaly)

    run = AgentRun(
        ticker_id=t.id,
        anomaly_id=anomaly.id,
        started_at=datetime.now(timezone.utc),
        completed_at=datetime.now(timezone.utc),
        status="failed",
        trace=[],
    )
    db_session.add(run); db_session.commit()

    client = make_client(db_session)
    resp = client.get("/api/watchlist")
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["symbol"] == "AAPL"
    assert body[0]["status"] != "triggered"
    assert body[0]["status"] == "quiet"

def test_delete_watchlist_soft_deletes(db_session):
    client = make_client(db_session)
    client.post("/api/watchlist", json={"symbol": "AAPL"})
    resp = client.delete("/api/watchlist/AAPL")
    assert resp.status_code == 204
    resp = client.get("/api/watchlist")
    assert resp.json() == []

def test_get_briefs_empty(db_session):
    client = make_client(db_session)
    resp = client.get("/api/briefs")
    assert resp.status_code == 200
    assert resp.json() == []

def test_get_brief_detail_includes_trace(db_session):
    from models.agent_run import AgentRun
    from models.brief import Brief
    t = Ticker(symbol="AAPL", added_at=datetime.now(timezone.utc), active=True)
    db_session.add(t); db_session.commit(); db_session.refresh(t)
    run = AgentRun(ticker_id=t.id, started_at=datetime.now(timezone.utc), status="complete", trace=[{"step": 1, "type": "final", "output": {}}])
    db_session.add(run); db_session.commit(); db_session.refresh(run)
    brief = Brief(ticker_id=t.id, agent_run_id=run.id, created_at=datetime.now(timezone.utc), thesis="neutral", confidence=3, summary="s", evidence=[])
    db_session.add(brief); db_session.commit(); db_session.refresh(brief)

    client = make_client(db_session)
    resp = client.get(f"/api/briefs/{brief.id}")
    assert resp.status_code == 200
    assert resp.json()["agent_run"]["trace"][0]["type"] == "final"
