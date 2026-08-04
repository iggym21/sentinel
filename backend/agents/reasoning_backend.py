"""Reasoning-backend protocol and shared result types.

`ReasoningBackend` is the contract the Watchdog and Analyst agent loops
depend on. Two implementations exist: `ClaudeBackend` (real Messages API
tool-use loop, `backend/agents/claude_backend.py`) and `HeuristicBackend`
(deterministic, no LLM — runs the same tools, same trace shape, rule-based
judgment, `backend/agents/heuristic_backend.py`). `backend_factory.py`
picks between them at runtime. Defined once here so later tasks don't
redefine these types differently.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from providers.base import NewsItem
from services.trace import TraceRecorder


@dataclass
class WatchdogDecision:
    trigger: bool
    rationale: str


@dataclass
class AnalystBriefResult:
    thesis: str
    confidence: int
    summary: str
    evidence: list[dict]  # [{"claim": str, "source_tool": str, "source_ref": str|None}]
    diff_from_prior: str | None
    suggested_action: str | None


class ReasoningBackend(Protocol):
    def watchdog_judge(
        self, ticker: str, metrics: dict, headlines: list[NewsItem]
    ) -> WatchdogDecision: ...

    def run_analyst(
        self,
        ticker: str,
        trigger_context: dict | None,
        tool_dispatch: dict[str, Callable],
        trace: TraceRecorder,
    ) -> AnalystBriefResult: ...
