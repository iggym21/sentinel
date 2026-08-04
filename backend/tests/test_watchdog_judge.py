from providers.base import NewsItem
from agents.heuristic_backend import HeuristicBackend
from agents.claude_backend import ClaudeBackend
from unittest.mock import MagicMock

def test_heuristic_triggers_on_large_volume_ratio():
    decision = HeuristicBackend().watchdog_judge("AAPL", {"volume_ratio": 3.5, "day_change_pct": 1.0}, [])
    assert decision.trigger is True

def test_heuristic_does_not_trigger_on_mild_move_no_news():
    decision = HeuristicBackend().watchdog_judge("AAPL", {"volume_ratio": 2.1, "day_change_pct": 1.5}, [])
    assert decision.trigger is False

def test_heuristic_triggers_on_large_price_move():
    decision = HeuristicBackend().watchdog_judge("AAPL", {"volume_ratio": 1.0, "day_change_pct": -6.0}, [])
    assert decision.trigger is True

def test_heuristic_triggers_on_price_move_only_with_corroborating_news_cites_price_not_volume():
    # volume_ratio=1.0 never crosses the 2.0 volume-spike threshold;
    # day_change_pct=4.0 crosses the 3.0 price-move threshold but is
    # under the 5.0 "large move" bar. A corroborating headline pushes
    # this into the `threshold_crossed and has_corroborating_news`
    # branch of `trigger`, which must attribute the rationale to price,
    # not volume.
    headlines = [NewsItem(headline="AAPL surges on guidance", summary="", published_at="2026-08-04", source="src")]
    decision = HeuristicBackend().watchdog_judge(
        "AAPL", {"volume_ratio": 1.0, "day_change_pct": 4.0}, headlines
    )
    assert decision.trigger is True
    assert "4.0%" in decision.rationale or "+4.0%" in decision.rationale
    assert "day" in decision.rationale.lower() or "price" in decision.rationale.lower()
    assert "volume" not in decision.rationale.lower()

class FakeContentBlock:
    def __init__(self, type_, **kwargs):
        self.type = type_
        for k, v in kwargs.items():
            setattr(self, k, v)

class FakeResponse:
    def __init__(self, stop_reason, content):
        self.stop_reason = stop_reason
        self.content = content

def test_claude_backend_parses_submit_decision():
    fake_client = MagicMock()
    submit = FakeContentBlock("tool_use", id="t1", name="submit_decision", input={
        "trigger": True, "rationale": "Volume 4x average right after an earnings headline.",
    })
    fake_client.messages.create.return_value = FakeResponse("tool_use", [submit])

    backend = ClaudeBackend(client=fake_client)
    decision = backend.watchdog_judge(
        "AAPL",
        {"volume_ratio": 4.0, "day_change_pct": 2.0},
        [NewsItem(headline="AAPL beats estimates", summary="", published_at="2026-08-04", source="src")],
    )

    assert decision.trigger is True
    assert "earnings" in decision.rationale
    call_kwargs = fake_client.messages.create.call_args.kwargs
    assert call_kwargs["tool_choice"] == {"type": "tool", "name": "submit_decision"}

def test_claude_backend_watchdog_raises_on_missing_submit_decision_block():
    fake_client = MagicMock()
    text_block = FakeContentBlock("text", text="I'm not sure.")
    fake_client.messages.create.return_value = FakeResponse("end_turn", [text_block])

    backend = ClaudeBackend(client=fake_client)
    try:
        backend.watchdog_judge("AAPL", {"volume_ratio": 4.0, "day_change_pct": 2.0}, [])
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "submit_decision" in str(e)

def test_claude_backend_watchdog_raises_on_missing_required_field():
    fake_client = MagicMock()
    bad_submit = FakeContentBlock("tool_use", id="t1", name="submit_decision", input={"trigger": True})
    fake_client.messages.create.return_value = FakeResponse("tool_use", [bad_submit])

    backend = ClaudeBackend(client=fake_client)
    try:
        backend.watchdog_judge("AAPL", {"volume_ratio": 4.0, "day_change_pct": 2.0}, [])
        assert False, "expected ValueError"
    except ValueError as e:
        assert "rationale" in str(e)
