from unittest.mock import MagicMock
from services.trace import TraceRecorder
from agents.claude_backend import ClaudeBackend

class FakeContentBlock:
    def __init__(self, type_, **kwargs):
        self.type = type_
        for k, v in kwargs.items():
            setattr(self, k, v)

class FakeResponse:
    def __init__(self, stop_reason, content):
        self.stop_reason = stop_reason
        self.content = content

def test_claude_backend_loops_until_submit_brief():
    fake_client = MagicMock()
    tool_call_1 = FakeContentBlock("tool_use", id="t1", name="get_prior_briefs", input={"ticker": "AAPL", "limit": 3})
    submit = FakeContentBlock("tool_use", id="t2", name="submit_brief", input={
        "thesis": "neutral", "confidence": 3, "summary": "Mixed signals.",
        "evidence": [{"claim": "No major move", "source_tool": "get_prior_briefs"}],
    })
    fake_client.messages.create.side_effect = [
        FakeResponse("tool_use", [tool_call_1]),
        FakeResponse("tool_use", [submit]),
    ]
    dispatch = {"get_prior_briefs": lambda input: []}
    trace = TraceRecorder()

    backend = ClaudeBackend(client=fake_client)
    result = backend.run_analyst("AAPL", trigger_context=None, tool_dispatch=dispatch, trace=trace)

    assert result.thesis == "neutral"
    assert fake_client.messages.create.call_count == 2
    tool_calls = [s for s in trace.to_json() if s["type"] == "tool_call"]
    assert tool_calls[0]["tool_name"] == "get_prior_briefs"

def test_claude_backend_raises_on_missing_required_field():
    fake_client = MagicMock()
    bad_submit = FakeContentBlock("tool_use", id="t1", name="submit_brief", input={"thesis": "neutral"})
    fake_client.messages.create.side_effect = [FakeResponse("tool_use", [bad_submit])]
    backend = ClaudeBackend(client=fake_client)
    try:
        backend.run_analyst("AAPL", None, {}, TraceRecorder())
        assert False, "expected ValueError"
    except ValueError:
        pass
