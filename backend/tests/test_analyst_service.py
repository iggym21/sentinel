from unittest.mock import MagicMock
from datetime import datetime, timezone

from services.analyst_service import run_analyst_for_ticker
from agents.reasoning_backend import AnalystBriefResult
from models.agent_run import AgentRun
from models.brief import Brief


def make_fake_backend(result):
    backend = MagicMock()
    backend.run_analyst.return_value = result
    return backend


def test_run_analyst_creates_run_and_brief(db_session):
    result = AnalystBriefResult(
        thesis="bullish", confidence=4, summary="Strong signals.",
        evidence=[{"claim": "c", "source_tool": "get_price_history", "source_ref": None}],
        diff_from_prior=None, suggested_action="buy",
    )
    backend = make_fake_backend(result)
    market, filings = MagicMock(), MagicMock()

    brief = run_analyst_for_ticker(db_session, "AAPL", market, filings, backend=backend)

    assert brief.thesis == "bullish"
    run = db_session.query(AgentRun).filter_by(id=brief.agent_run_id).one()
    assert run.status == "complete"
    assert run.brief_id == brief.id


def test_run_analyst_computes_diff_from_prior(db_session):
    from models.ticker import Ticker
    t = Ticker(symbol="AAPL", added_at=datetime.now(timezone.utc), active=True)
    db_session.add(t); db_session.commit(); db_session.refresh(t)
    prior_run = AgentRun(ticker_id=t.id, started_at=datetime.now(timezone.utc), status="complete", trace=[])
    db_session.add(prior_run); db_session.commit(); db_session.refresh(prior_run)
    prior_brief = Brief(ticker_id=t.id, agent_run_id=prior_run.id, created_at=datetime.now(timezone.utc), thesis="bearish", confidence=2, summary="s", evidence=[])
    db_session.add(prior_brief); db_session.commit()

    result = AnalystBriefResult(thesis="bullish", confidence=4, summary="Turned around.", evidence=[], diff_from_prior=None, suggested_action=None)
    backend = make_fake_backend(result)
    brief = run_analyst_for_ticker(db_session, "AAPL", MagicMock(), MagicMock(), backend=backend)

    assert brief.diff_from_prior is not None
    assert "bearish" in brief.diff_from_prior and "bullish" in brief.diff_from_prior


def test_run_analyst_marks_failed_on_exception(db_session):
    backend = MagicMock()
    backend.run_analyst.side_effect = RuntimeError("boom")
    try:
        run_analyst_for_ticker(db_session, "AAPL", MagicMock(), MagicMock(), backend=backend)
        assert False, "expected RuntimeError"
    except RuntimeError:
        pass
    run = db_session.query(AgentRun).one()
    assert run.status == "failed"
