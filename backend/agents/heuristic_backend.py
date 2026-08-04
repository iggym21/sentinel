"""Deterministic, no-LLM `ReasoningBackend` implementation.

Stub for Task 9 — `backend_factory.get_reasoning_backend()` needs a
`HeuristicBackend` class to select when no Anthropic API key is
configured (or the backend is forced to "heuristic"), so the whole
trigger -> investigate -> brief loop stays testable and demoable with
zero external API keys. The real rule-based logic (runs the same tools,
same trace shape, as the real loop would) is implemented in Task 10.
"""

from __future__ import annotations

from typing import Callable

from providers.base import NewsItem
from services.trace import TraceRecorder

from agents.reasoning_backend import AnalystBriefResult, WatchdogDecision


class HeuristicBackend:
    """Reasoning backend that runs the same tools with rule-based judgment, no LLM."""

    def watchdog_judge(
        self, ticker: str, metrics: dict, headlines: list[NewsItem]
    ) -> WatchdogDecision:
        raise NotImplementedError

    def run_analyst(
        self,
        ticker: str,
        trigger_context: dict | None,
        tool_dispatch: dict[str, Callable],
        trace: TraceRecorder,
    ) -> AnalystBriefResult:
        raise NotImplementedError
