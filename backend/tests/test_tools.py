from unittest.mock import MagicMock
from providers.base import OHLCVBar, NewsItem, FilingRef
from agents.tools.get_price_history import get_price_history
from agents.tools.get_recent_news import get_recent_news
from agents.tools.calculate_ratios import calculate_ratios
from agents.tools.get_prior_briefs import get_prior_briefs
from models.ticker import Ticker
from models.brief import Brief
from models.agent_run import AgentRun
from datetime import datetime, timezone

def test_get_price_history_serializes_bars():
    market = MagicMock()
    market.get_price_history.return_value = [OHLCVBar(date="2026-08-01", open=1, high=2, low=0.5, close=1.5, volume=100)]
    result = get_price_history(market, "AAPL", days=30)
    assert result[0]["close"] == 1.5

def test_get_recent_news_serializes_items():
    market = MagicMock()
    market.get_recent_news.return_value = [NewsItem(headline="H", summary="S", published_at="2026-08-01", source="src")]
    result = get_recent_news(market, "AAPL", days=7)
    assert result[0]["headline"] == "H"

def test_calculate_ratios_uses_price_history_only():
    market = MagicMock()
    market.get_price_history.return_value = [
        OHLCVBar(date=f"2026-07-{i:02d}", open=100+i, high=101+i, low=99+i, close=100+i, volume=1000) for i in range(1, 21)
    ]
    result = calculate_ratios(market, "AAPL")
    assert "trend_20d_pct" in result
    assert "fundamentals data source" in result["note"]

def test_get_prior_briefs_returns_ordered(db_session):
    t = Ticker(symbol="AAPL", added_at=datetime.now(timezone.utc), active=True)
    db_session.add(t); db_session.commit(); db_session.refresh(t)
    run = AgentRun(ticker_id=t.id, started_at=datetime.now(timezone.utc), status="complete", trace=[])
    db_session.add(run); db_session.commit(); db_session.refresh(run)
    b1 = Brief(ticker_id=t.id, agent_run_id=run.id, created_at=datetime.now(timezone.utc), thesis="neutral", confidence=3, summary="s1", evidence=[])
    db_session.add(b1); db_session.commit()

    result = get_prior_briefs(db_session, "AAPL", limit=3)
    assert len(result) == 1
    assert result[0]["summary"] == "s1"
