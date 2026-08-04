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

def test_claude_backend_appends_matching_assistant_and_tool_result_messages():
    fake_client = MagicMock()
    tool_call_1 = FakeContentBlock("tool_use", id="t1", name="get_prior_briefs", input={"ticker": "AAPL"})
    submit = FakeContentBlock("tool_use", id="t2", name="submit_brief", input={
        "thesis": "neutral", "confidence": 3, "summary": "Mixed signals.",
        "evidence": [{"claim": "No major move", "source_tool": "get_prior_briefs"}],
    })
    responses = [
        FakeResponse("tool_use", [tool_call_1]),
        FakeResponse("tool_use", [submit]),
    ]
    # `messages` is a single list mutated in place across iterations, so
    # `mock.call_args_list` would otherwise alias the same (final) list
    # object for every recorded call. Snapshot a shallow copy of the
    # `messages` kwarg at the moment of each call so each snapshot
    # reflects what was actually sent on that round trip.
    call_kwargs_snapshots = []

    def fake_create(**kwargs):
        snapshot = dict(kwargs)
        snapshot["messages"] = list(kwargs["messages"])
        call_kwargs_snapshots.append(snapshot)
        return responses.pop(0)

    fake_client.messages.create.side_effect = fake_create
    dispatch = {"get_prior_briefs": lambda input: ["prior brief"]}
    trace = TraceRecorder()

    backend = ClaudeBackend(client=fake_client)
    backend.run_analyst("AAPL", trigger_context=None, tool_dispatch=dispatch, trace=trace)

    # First call must include max_tokens (required by the real Messages API).
    assert "max_tokens" in call_kwargs_snapshots[0]

    # Second call's messages must end with the assistant's tool_use turn
    # immediately followed by the paired user tool_result turn.
    second_call_messages = call_kwargs_snapshots[1]["messages"]
    assistant_msg, tool_result_msg = second_call_messages[-2], second_call_messages[-1]
    assert assistant_msg == {"role": "assistant", "content": [tool_call_1]}
    assert tool_result_msg["role"] == "user"
    assert len(tool_result_msg["content"]) == 1
    assert tool_result_msg["content"][0]["type"] == "tool_result"
    assert tool_result_msg["content"][0]["tool_use_id"] == "t1"
    assert "prior brief" in tool_result_msg["content"][0]["content"]

def test_claude_backend_raises_after_15_iterations_without_submit_brief():
    fake_client = MagicMock()
    loop_block = FakeContentBlock("tool_use", id="tX", name="get_prior_briefs", input={})
    fake_client.messages.create.return_value = FakeResponse("tool_use", [loop_block])
    dispatch = {"get_prior_briefs": lambda input: []}
    backend = ClaudeBackend(client=fake_client)

    try:
        backend.run_analyst("AAPL", None, dispatch, TraceRecorder())
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "max tool-use iterations" in str(e)

    assert fake_client.messages.create.call_count == 15

def test_claude_backend_raises_on_text_only_response_instead_of_looping_with_bad_state():
    fake_client = MagicMock()
    text_block = FakeContentBlock("text", text="Let me think about this.")
    fake_client.messages.create.side_effect = [FakeResponse("end_turn", [text_block])]
    backend = ClaudeBackend(client=fake_client)

    try:
        backend.run_analyst("AAPL", None, {}, TraceRecorder())
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "submit_brief" in str(e)

    # Must fail immediately on the next-would-be request, not retry with
    # a dangling trailing assistant message in `messages`.
    assert fake_client.messages.create.call_count == 1
