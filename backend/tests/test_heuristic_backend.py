from services.trace import TraceRecorder
from agents.heuristic_backend import HeuristicBackend

def make_dispatch():
    calls = []
    def tool(name, result):
        def _fn(input):
            calls.append(name)
            return result
        return _fn
    dispatch = {
        "get_prior_briefs": tool("get_prior_briefs", []),
        "get_price_history": tool("get_price_history", [{"date": "2026-08-01", "close": 100}, {"date": "2026-08-02", "close": 105}]),
        "get_recent_news": tool("get_recent_news", [{"headline": "AAPL rallies", "summary": "", "published_at": "2026-08-02", "source": "x"}]),
        "get_filings": tool("get_filings", [{"form_type": "10-Q", "url": "https://example.com/f.htm", "filed_at": "2026-07-15"}]),
        "calculate_ratios": tool("calculate_ratios", {"trend_20d_pct": 5.0, "trend_5d_pct": 2.0, "volatility_20d_pct": 1.1, "avg_volume_20d": 1000, "note": "..."}),
    }
    return dispatch, calls

def test_heuristic_backend_calls_all_tools_and_produces_brief():
    dispatch, calls = make_dispatch()
    trace = TraceRecorder()
    backend = HeuristicBackend()
    result = backend.run_analyst("AAPL", trigger_context=None, tool_dispatch=dispatch, trace=trace)

    assert calls == ["get_prior_briefs", "get_price_history", "get_recent_news", "get_filings", "calculate_ratios"]
    assert result.thesis == "bullish"
    assert 1 <= result.confidence <= 5
    assert len(result.evidence) >= 1
    assert any(e["source_tool"] == "calculate_ratios" for e in result.evidence)

    steps = trace.to_json()
    tool_call_names = [s["tool_name"] for s in steps if s["type"] == "tool_call"]
    assert tool_call_names == ["get_prior_briefs", "get_price_history", "get_recent_news", "get_filings", "calculate_ratios"]
    assert steps[-1]["type"] == "final"

def test_heuristic_backend_bearish_case():
    dispatch, _ = make_dispatch()
    dispatch["calculate_ratios"] = lambda input: {"trend_20d_pct": -6.0, "trend_5d_pct": -3.0, "volatility_20d_pct": 2.0, "avg_volume_20d": 1000, "note": "..."}
    result = HeuristicBackend().run_analyst("AAPL", None, dispatch, TraceRecorder())
    assert result.thesis == "bearish"
