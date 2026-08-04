"""Real Claude-backed `ReasoningBackend` implementation.

Stub for Task 9 — `backend_factory.get_reasoning_backend()` needs a
`ClaudeBackend` class to select when an API key is configured, but the
actual Messages API tool-use loop (per `sentinel-spec/docs/ARCHITECTURE.md`
§2.2) is implemented in Task 10/12. Construction must stay side-effect
free (no client construction here) so importing/instantiating this class
doesn't require `anthropic` to be configured; only calling its methods
does real work, once implemented.
"""

from __future__ import annotations

from typing import Callable

from providers.base import NewsItem
from services.trace import TraceRecorder

from agents.reasoning_backend import AnalystBriefResult, WatchdogDecision


class ClaudeBackend:
    """Reasoning backend that delegates to the real Claude Messages API."""

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
