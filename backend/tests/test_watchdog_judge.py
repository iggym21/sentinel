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
