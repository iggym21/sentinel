"""Real Claude-backed `ReasoningBackend` implementation.

`run_analyst` is the actual multi-step Messages API tool-use loop
described in `sentinel-spec/docs/ARCHITECTURE.md` §2.2: Claude is
handed a system prompt plus `TOOL_SCHEMAS` and runs in a loop, calling
tools until it submits a final brief via the terminal `submit_brief`
tool. Every tool_use block (including `submit_brief` itself) and every
tool result is recorded through the injected `TraceRecorder` in the
order they happen — that ordered trace is what the frontend's
reasoning-trace UI renders, so nothing here may skip recording a step
to save code.

`ClaudeBackend.__init__` accepts an optional `client` so tests can
inject a fake Anthropic client without touching real credentials or
making `anthropic` a hard import-time dependency; when omitted it
lazily builds the real client via `get_anthropic_client()`.
"""

from __future__ import annotations

import json
from typing import Callable

from config import settings
from providers.base import NewsItem
from services.trace import TraceRecorder

from agents.claude_client import get_anthropic_client
from agents.reasoning_backend import AnalystBriefResult, WatchdogDecision
from agents.tools.schemas import SUBMIT_DECISION_SCHEMA, TOOL_SCHEMAS

# Hard cap on tool-use round trips per Analyst run. Guards against a
# model that never calls `submit_brief` (e.g. stuck looping on tool
# calls) from running away indefinitely / racking up API cost.
_MAX_ITERATIONS = 15

# `max_tokens` is a required keyword-only argument on the Messages API
# (missing it is a hard TypeError/400, not a soft default) — 8000 is
# comfortably enough for a brief-producing tool-use turn without being
# wasteful, since most turns are a single tool_use block, not prose.
_MAX_TOKENS = 8000

# Must match `submit_brief`'s `input_schema.required` in
# `agents/tools/schemas.py::TOOL_SCHEMAS` exactly.
_SUBMIT_BRIEF_REQUIRED_FIELDS = ["thesis", "confidence", "summary", "evidence"]

# The Watchdog's judgment call is a single small structured-output turn
# (no tool-use loop, no multi-paragraph brief), so it needs far fewer
# tokens than the Analyst's `_MAX_TOKENS`.
_WATCHDOG_MAX_TOKENS = 1024

# Must match `submit_decision`'s `input_schema.required` in
# `agents/tools/schemas.py::SUBMIT_DECISION_SCHEMA` exactly.
_SUBMIT_DECISION_REQUIRED_FIELDS = ["trigger", "rationale"]

WATCHDOG_SYSTEM_PROMPT = """You are Sentinel's Watchdog Agent. A ticker's price or volume has \
crossed a code-level anomaly threshold, and you must judge whether this warrants a full Analyst \
investigation or is likely routine market noise.

Distinguish routine volatility from genuinely unusual activity: minor moves and typical volume \
fluctuations happen constantly and are not, by themselves, worth investigating. Use the provided \
headlines as context — a threshold crossing that coincides with relevant news (earnings, \
guidance, M&A, regulatory action) is far more likely to be genuinely significant than one with no \
corroborating news at all.

Be conservative: triggering a full investigation costs real time and money, so when the evidence \
is ambiguous, prefer not to trigger. Only recommend triggering when the activity looks genuinely \
unusual or is corroborated by relevant news.

Call `submit_decision` with your judgment as your only action — this is a single-turn decision, \
not an investigation of your own."""

ANALYST_SYSTEM_PROMPT = """You are Sentinel's Analyst Agent, a market research assistant that \
investigates a single ticker and produces a structured research brief.

Gather evidence from multiple tools before concluding — do not form a thesis from a single \
data point. Always call `get_prior_briefs` early in your investigation so you can meaningfully \
compare your current findings against Sentinel's own past output on this ticker and describe \
what has changed.

For every claim you make in your final brief's `evidence` list, cite which tool produced it via \
`source_tool` (and `source_ref` where applicable, e.g. a filing URL or headline). Do not assert \
anything you cannot trace back to a tool result.

When you have gathered sufficient evidence, call `submit_brief` as your final action — this is \
the only way to end your turn with a result. Never end with plain text; the loop only terminates \
on a `submit_brief` tool call."""


def _build_user_message(ticker: str, trigger_context: dict | None) -> dict:
    content = f"Research ticker {ticker} and produce a brief."
    if trigger_context:
        content += f" Trigger context: {json.dumps(trigger_context, default=str)}"
    return {"role": "user", "content": content}


def _build_watchdog_user_message(ticker: str, metrics: dict, headlines: list[NewsItem]) -> dict:
    headlines_text = (
        "\n".join(f"- {item.headline} ({item.source}, {item.published_at})" for item in headlines)
        if headlines
        else "(no recent headlines)"
    )
    content = (
        f"Ticker: {ticker}\n"
        f"Metrics: {json.dumps(metrics, default=str)}\n"
        f"Recent headlines:\n{headlines_text}"
    )
    return {"role": "user", "content": content}


def _tool_result_content(output: object) -> str:
    if isinstance(output, str):
        return output
    return json.dumps(output, default=str)


class ClaudeBackend:
    """Reasoning backend that delegates to the real Claude Messages API."""

    def __init__(self, client=None) -> None:
        self.client = client or get_anthropic_client()

    def watchdog_judge(
        self, ticker: str, metrics: dict, headlines: list[NewsItem]
    ) -> WatchdogDecision:
        response = self.client.messages.create(
            model=settings.watchdog_model,
            max_tokens=_WATCHDOG_MAX_TOKENS,
            system=WATCHDOG_SYSTEM_PROMPT,
            messages=[_build_watchdog_user_message(ticker, metrics, headlines)],
            tools=[SUBMIT_DECISION_SCHEMA],
            tool_choice={"type": "tool", "name": "submit_decision"},
        )

        submit_input: dict | None = None
        for block in response.content:
            if block.type == "tool_use" and block.name == "submit_decision":
                submit_input = block.input
                break

        if submit_input is None:
            raise RuntimeError("Watchdog response did not include a submit_decision tool call")

        missing = [f for f in _SUBMIT_DECISION_REQUIRED_FIELDS if submit_input.get(f) is None]
        if missing:
            raise ValueError(
                f"submit_decision call is missing required field(s): {', '.join(missing)}"
            )

        return WatchdogDecision(
            trigger=submit_input["trigger"],
            rationale=submit_input["rationale"],
        )

    def run_analyst(
        self,
        ticker: str,
        trigger_context: dict | None,
        tool_dispatch: dict[str, Callable],
        trace: TraceRecorder,
    ) -> AnalystBriefResult:
        messages: list[dict] = [_build_user_message(ticker, trigger_context)]

        for _ in range(_MAX_ITERATIONS):
            response = self.client.messages.create(
                model=settings.analyst_model,
                max_tokens=_MAX_TOKENS,
                system=ANALYST_SYSTEM_PROMPT,
                messages=messages,
                tools=TOOL_SCHEMAS,
            )
            messages.append({"role": "assistant", "content": response.content})

            tool_result_blocks: list[dict] = []
            for block in response.content:
                if block.type == "text":
                    trace.record_reasoning(block.text)
                    continue
                if block.type != "tool_use":
                    continue

                trace.record_tool_call(block.name, block.input)

                if block.name == "submit_brief":
                    return self._finalize(block.input, trace)

                if block.name not in tool_dispatch:
                    # Deliberate MVP simplification: an unknown tool name
                    # (or a dispatch-time exception below) aborts the
                    # whole run rather than being reported back to the
                    # model as an `is_error: True` tool_result so it can
                    # try to recover. Acceptable for now since
                    # `tool_dispatch` only ever contains the fixed set
                    # of tools advertised in `TOOL_SCHEMAS`.
                    raise ValueError(f"Analyst requested unknown tool '{block.name}'")

                output = tool_dispatch[block.name](block.input)
                trace.record_tool_result(block.name, output)
                tool_result_blocks.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": _tool_result_content(output),
                    }
                )

            if not tool_result_blocks:
                # No non-terminal tool_use block was found in this turn
                # (e.g. the model returned text only, or an empty
                # content list) and `submit_brief` wasn't called either
                # (that path already returned above). `messages` at this
                # point ends in a trailing assistant turn with no
                # tool_result to pair it with — sending that back as the
                # next request's `messages` is an assistant-prefill,
                # which the Messages API rejects with a 400 on
                # Sonnet 4.6+/Opus 4.6+ (including `settings.analyst_model`).
                # Fail loudly here instead of silently retrying into that
                # 400 on the next iteration.
                raise RuntimeError(
                    "Analyst ended its turn without calling a tool or "
                    "submit_brief"
                )

            messages.append({"role": "user", "content": tool_result_blocks})

        raise RuntimeError("Analyst agent exceeded max tool-use iterations")

    def _finalize(self, submit_input: dict, trace: TraceRecorder) -> AnalystBriefResult:
        missing = [f for f in _SUBMIT_BRIEF_REQUIRED_FIELDS if submit_input.get(f) is None]
        if missing:
            raise ValueError(
                f"submit_brief call is missing required field(s): {', '.join(missing)}"
            )

        result = AnalystBriefResult(
            thesis=submit_input["thesis"],
            confidence=submit_input["confidence"],
            summary=submit_input["summary"],
            evidence=submit_input["evidence"],
            diff_from_prior=submit_input.get("diff_from_prior"),
            suggested_action=submit_input.get("suggested_action"),
        )

        trace.record_final(
            {
                "thesis": result.thesis,
                "confidence": result.confidence,
                "summary": result.summary,
                "evidence": result.evidence,
                "diff_from_prior": result.diff_from_prior,
                "suggested_action": result.suggested_action,
            }
        )

        return result
