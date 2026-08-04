from unittest.mock import MagicMock
from providers.base import OHLCVBar, NewsItem, FilingRef
from agents.tools.get_price_history import get_price_history
from agents.tools.get_recent_news import get_recent_news
from agents.tools.calculate_ratios import calculate_ratios
from agents.tools.get_prior_briefs import get_prior_briefs
from agents.tools.get_filings import get_filings
from agents.tools.get_filing_text import get_filing_text
from agents.tools.schemas import TOOL_SCHEMAS
from agents.tools.registry import build_tool_dispatch
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


def test_get_filings_serializes_refs():
    filings = MagicMock()
    filings.get_filings.return_value = [
        FilingRef(ticker="AAPL", form_type="10-K", filed_at="2026-02-01", url="https://sec.gov/x", title="Annual Report")
    ]
    result = get_filings(filings, "AAPL", form_types=["10-K"], limit=5)
    assert result == [
        {
            "ticker": "AAPL",
            "form_type": "10-K",
            "filed_at": "2026-02-01",
            "url": "https://sec.gov/x",
            "title": "Annual Report",
        }
    ]


def test_get_filing_text_wraps_url_and_text():
    filings = MagicMock()
    filings.get_filing_text.return_value = "cleaned filing text"
    result = get_filing_text(filings, "https://sec.gov/x", max_chars=100)
    assert result == {"filing_url": "https://sec.gov/x", "text": "cleaned filing text"}


def test_tool_schemas_cover_all_seven_tools():
    expected_names = [
        "get_filings",
        "get_filing_text",
        "get_recent_news",
        "get_price_history",
        "calculate_ratios",
        "get_prior_briefs",
        "submit_brief",
    ]
    assert [s["name"] for s in TOOL_SCHEMAS] == expected_names
    for schema in TOOL_SCHEMAS:
        assert set(schema.keys()) == {"name", "description", "input_schema"}
        assert isinstance(schema["description"], str) and schema["description"]
        assert schema["input_schema"]["type"] == "object"


def test_dispatch_ignores_ticker_in_tool_input_for_price_history():
    market = MagicMock()
    market.get_price_history.return_value = []
    dispatch = build_tool_dispatch(db=MagicMock(), market=market, filings=MagicMock(), ticker="AAPL")

    dispatch["get_price_history"]({"ticker": "MSFT", "days": 10})

    market.get_price_history.assert_called_once_with("AAPL", 10)


def test_dispatch_ignores_ticker_in_tool_input_for_filing_text():
    filings = MagicMock()
    filings.get_filing_text.return_value = "text"
    dispatch = build_tool_dispatch(db=MagicMock(), market=MagicMock(), filings=filings, ticker="AAPL")

    result = dispatch["get_filing_text"]({"ticker": "MSFT", "filing_url": "https://sec.gov/x"})

    filings.get_filing_text.assert_called_once_with("https://sec.gov/x", 8000)
    assert result == {"filing_url": "https://sec.gov/x", "text": "text"}
