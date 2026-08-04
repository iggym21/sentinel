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

def test_watchlist_added_at_serializes_with_utc_offset(db_session):
    # Finding #4 regression: SQLite drops tzinfo on round-trip, and Pydantic
    # serializing a naive datetime produces an offset-less ISO string (e.g.
    # "...T20:21:50.195238" with no "Z"/"+00:00"), which JavaScript's
    # `new Date()` then parses as local time instead of UTC. Every `*Out`
    # schema's datetime fields must serialize with an explicit UTC marker.
    client = make_client(db_session)
    resp = client.post("/api/watchlist", json={"symbol": "AAPL"})
    assert resp.status_code == 200
    added_at = resp.json()["added_at"]
    assert added_at.endswith("Z") or added_at[-6] in "+-"

def test_post_watchlist_rejects_path_traversal_symbol(db_session):
    # Finding #5 regression: TickerCreate.symbol was a bare `str` reaching
    # AlpacaProvider's f-string-interpolated URL paths unescaped. A symbol
    # containing "/" or "?" or ".." must be rejected at the API boundary,
    # not passed through.
    client = make_client(db_session)
    resp = client.post("/api/watchlist", json={"symbol": "../../v2/account"})
    assert resp.status_code == 422

    resp = client.post("/api/watchlist", json={"symbol": "AAPL?x=1"})
    assert resp.status_code == 422

def test_delete_watchlist_rejects_invalid_symbol(db_session):
    # A single path segment (no "/") that's still not a valid ticker
    # symbol (too long) — exercises `normalize_symbol`'s 422 on a
    # path-param symbol, since FastAPI path params never go through
    # `TickerCreate`'s Pydantic validation.
    client = make_client(db_session)
    resp = client.delete("/api/watchlist/NOTAVALIDTICKERSYMBOL")
    assert resp.status_code == 422

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
    body = resp.json()
    assert body["agent_run"]["trace"][0]["type"] == "final"
    assert body["ticker_symbol"] == "AAPL"

    resp = client.get("/api/briefs")
    assert resp.status_code == 200
    assert resp.json()[0]["ticker_symbol"] == "AAPL"
