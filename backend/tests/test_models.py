from datetime import datetime, timezone
from models.ticker import Ticker
from models.anomaly import Anomaly
from models.agent_run import AgentRun
from models.brief import Brief

def test_create_ticker_and_related_rows(db_session):
    t = Ticker(symbol="AAPL", added_at=datetime.now(timezone.utc), active=True)
    db_session.add(t)
    db_session.commit()
    db_session.refresh(t)
    assert t.id is not None

    anomaly = Anomaly(
        ticker_id=t.id, detected_at=datetime.now(timezone.utc),
        trigger_type="volume_spike", raw_metrics={"volume_ratio": 2.4},
        watchdog_rationale="Volume 2.4x average with no corroborating news.",
        triggered_analyst_run=True,
    )
    db_session.add(anomaly)
    db_session.commit()
    db_session.refresh(anomaly)

    run = AgentRun(
        ticker_id=t.id, anomaly_id=anomaly.id, started_at=datetime.now(timezone.utc),
        status="running", trace=[{"step": 1, "type": "reasoning", "text": "start"}],
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)

    brief = Brief(
        ticker_id=t.id, agent_run_id=run.id, created_at=datetime.now(timezone.utc),
        thesis="bullish", confidence=4, summary="Strong quarter.",
        evidence=[{"claim": "Revenue up 12% YoY", "source_tool": "get_filings", "source_ref": "10-Q"}],
    )
    db_session.add(brief)
    db_session.commit()
    db_session.refresh(brief)

    run.brief_id = brief.id
    db_session.commit()

    assert anomaly.ticker_id == t.id
    assert run.trace[0]["type"] == "reasoning"
    assert brief.evidence[0]["claim"] == "Revenue up 12% YoY"
    assert run.brief_id == brief.id
