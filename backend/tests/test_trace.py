from services.trace import TraceRecorder


def test_trace_records_steps_in_order_with_incrementing_step_numbers():
    trace = TraceRecorder()
    trace.record_reasoning("Starting research on AAPL")
    trace.record_tool_call("get_price_history", {"ticker": "AAPL", "days": 30})
    trace.record_tool_result("get_price_history", [{"close": 190.0}])
    trace.record_final({"thesis": "bullish"})

    steps = trace.to_json()
    assert [s["step"] for s in steps] == [1, 2, 3, 4]
    assert steps[0]["type"] == "reasoning" and steps[0]["text"] == "Starting research on AAPL"
    assert steps[1]["type"] == "tool_call" and steps[1]["tool_name"] == "get_price_history"
    assert steps[2]["type"] == "tool_result" and steps[2]["output"] == [{"close": 190.0}]
    assert steps[3]["type"] == "final" and steps[3]["output"] == {"thesis": "bullish"}
    assert all("timestamp" in s for s in steps)
