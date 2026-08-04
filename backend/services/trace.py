"""Reasoning-trace recorder.

Records the ordered sequence of steps (tool_call/tool_result/reasoning/final)
an agent run produces, so the full trace can be persisted to `AgentRun.trace`
(a JSON column) and rendered by the frontend's reasoning-trace UI. Never
discard intermediate steps — this is the single most important technical
detail for the demo to land (`sentinel-spec/docs/ARCHITECTURE.md` §6).
"""

from datetime import datetime, timezone


class TraceRecorder:
    """Accumulates an ordered list of trace steps with incrementing step numbers."""

    def __init__(self) -> None:
        self._steps: list[dict] = []

    def _next_step_number(self) -> int:
        return len(self._steps) + 1

    def _timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def record_tool_call(self, tool_name: str, input: dict) -> None:
        self._steps.append({
            "step": self._next_step_number(),
            "type": "tool_call",
            "tool_name": tool_name,
            "input": input,
            "output": None,
            "text": None,
            "timestamp": self._timestamp(),
        })

    def record_tool_result(self, tool_name: str, output: object) -> None:
        self._steps.append({
            "step": self._next_step_number(),
            "type": "tool_result",
            "tool_name": tool_name,
            "input": None,
            "output": output,
            "text": None,
            "timestamp": self._timestamp(),
        })

    def record_reasoning(self, text: str) -> None:
        self._steps.append({
            "step": self._next_step_number(),
            "type": "reasoning",
            "tool_name": None,
            "input": None,
            "output": None,
            "text": text,
            "timestamp": self._timestamp(),
        })

    def record_final(self, output: dict) -> None:
        self._steps.append({
            "step": self._next_step_number(),
            "type": "final",
            "tool_name": None,
            "input": None,
            "output": output,
            "text": None,
            "timestamp": self._timestamp(),
        })

    def to_json(self) -> list[dict]:
        return list(self._steps)
