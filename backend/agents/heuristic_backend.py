"""Deterministic, no-LLM `ReasoningBackend` implementation.

Runs the exact same five non-terminal Analyst tools the real Claude
tool-use loop would (`get_prior_briefs`, `get_price_history`,
`get_recent_news`, `get_filings`, `calculate_ratios`), in a fixed
order, recording each call/result pair through the same `TraceRecorder`
shape the real loop uses. This is what lets the whole trigger ->
investigate -> brief pipeline run end-to-end with zero external API
keys (`sentinel-spec` Global Constraints) — no LLM judgment, just
simple rules derived from the real data the tools return.
"""

from __future__ import annotations

from typing import Callable

from config import settings
from providers.base import NewsItem
from services.trace import TraceRecorder

from agents.reasoning_backend import AnalystBriefResult, WatchdogDecision

# Large-magnitude thresholds that alone are enough to warrant a full
# Analyst investigation, independent of any corroborating news — a
# volume or price move this extreme is unusual enough on its own.
_LARGE_VOLUME_RATIO = 3.0
_LARGE_PRICE_MOVE_PCT = 5.0

# Fixed tool call order — matches what the real Claude loop is expected
# to do per the system prompt guidance (check prior briefs early, then
# gather price/news/filings evidence, then compute ratios last since
# they summarize the price history already fetched).
_TOOL_ORDER = [
    "get_prior_briefs",
    "get_price_history",
    "get_recent_news",
    "get_filings",
    "calculate_ratios",
]


class HeuristicBackend:
    """Reasoning backend that runs the same tools with rule-based judgment, no LLM."""

    def watchdog_judge(
        self, ticker: str, metrics: dict, headlines: list[NewsItem]
    ) -> WatchdogDecision:
        volume_ratio = metrics.get("volume_ratio", 0) or 0
        day_change_pct = metrics.get("day_change_pct", 0) or 0

        large_volume = volume_ratio >= _LARGE_VOLUME_RATIO
        large_move = abs(day_change_pct) >= _LARGE_PRICE_MOVE_PCT

        # "Threshold crossed at all" refers to the base anomaly-detection
        # thresholds (the reason `watchdog_judge` is being called in the
        # first place), lower bars than the large-magnitude ones above.
        threshold_crossed = (
            volume_ratio >= settings.volume_spike_threshold_multiplier
            or abs(day_change_pct) >= settings.price_move_threshold_pct
        )
        has_corroborating_news = any(
            ticker.lower() in headline.headline.lower() for headline in headlines
        )

        trigger = large_volume or large_move or (threshold_crossed and has_corroborating_news)

        if large_volume:
            rationale = (
                f"Volume at {volume_ratio:.1f}x average — a large enough deviation "
                "from normal trading activity to warrant investigation on its own."
            )
        elif large_move:
            rationale = (
                f"Price moved {day_change_pct:+.1f}% today — a large single-day "
                "move that warrants investigation on its own."
            )
        elif trigger:
            rationale = (
                f"Volume at {volume_ratio:.1f}x average with a corroborating "
                f"headline mentioning {ticker} — likely more than routine noise."
            )
        else:
            rationale = (
                f"Volume at {volume_ratio:.1f}x average with no corroborating "
                "headlines — likely routine noise."
            )

        return WatchdogDecision(trigger=trigger, rationale=rationale)

    def run_analyst(
        self,
        ticker: str,
        trigger_context: dict | None,
        tool_dispatch: dict[str, Callable],
        trace: TraceRecorder,
    ) -> AnalystBriefResult:
        results: dict[str, object] = {}
        for tool_name in _TOOL_ORDER:
            tool_input = {"ticker": ticker}
            trace.record_tool_call(tool_name, tool_input)
            output = tool_dispatch[tool_name](tool_input)
            trace.record_tool_result(tool_name, output)
            results[tool_name] = output

        prior_briefs = results["get_prior_briefs"] or []
        price_history = results["get_price_history"] or []
        news = results["get_recent_news"] or []
        filings = results["get_filings"] or []
        ratios = results["calculate_ratios"] or {}

        trend_20d_pct = ratios.get("trend_20d_pct") or 0
        trend_5d_pct = ratios.get("trend_5d_pct")
        volatility_20d_pct = ratios.get("volatility_20d_pct")
        avg_volume_20d = ratios.get("avg_volume_20d")

        if trend_20d_pct > 1:
            thesis = "bullish"
        elif trend_20d_pct < -1:
            thesis = "bearish"
        else:
            thesis = "neutral"

        # Scale confidence by the magnitude of the trend: bigger moves
        # are more legible signals, so a stronger trend earns higher
        # confidence, clamped to the [1, 5] Brief schema range.
        confidence = max(1, min(5, round(1 + abs(trend_20d_pct) / 2)))

        evidence: list[dict] = [
            {
                "claim": (
                    f"20-day price trend is {trend_20d_pct:+.2f}% "
                    f"(5-day: {trend_5d_pct:+.2f}%)"
                    if trend_5d_pct is not None
                    else f"20-day price trend is {trend_20d_pct:+.2f}%"
                ),
                "source_tool": "calculate_ratios",
                "source_ref": None,
            }
        ]
        if volatility_20d_pct is not None:
            evidence.append(
                {
                    "claim": f"20-day volatility is {volatility_20d_pct}%",
                    "source_tool": "calculate_ratios",
                    "source_ref": None,
                }
            )
        if avg_volume_20d is not None:
            evidence.append(
                {
                    "claim": f"Average 20-day volume is {avg_volume_20d}",
                    "source_tool": "calculate_ratios",
                    "source_ref": None,
                }
            )
        if news:
            headline = news[0]
            evidence.append(
                {
                    "claim": f"Recent headline: \"{headline.get('headline')}\"",
                    "source_tool": "get_recent_news",
                    "source_ref": headline.get("source"),
                }
            )
        if filings:
            filing = filings[0]
            evidence.append(
                {
                    "claim": (
                        f"Most recent filing: {filing.get('form_type')} "
                        f"filed {filing.get('filed_at')}"
                    ),
                    "source_tool": "get_filings",
                    "source_ref": filing.get("url"),
                }
            )
        if price_history:
            first_close = price_history[0].get("close")
            last_close = price_history[-1].get("close")
            evidence.append(
                {
                    "claim": (
                        f"Price moved from {first_close} to {last_close} "
                        "over the fetched history"
                    ),
                    "source_tool": "get_price_history",
                    "source_ref": None,
                }
            )

        summary = (
            f"{ticker} shows a {thesis} signal based on price action: "
            f"20-day trend {trend_20d_pct:+.2f}%"
            + (f", volatility {volatility_20d_pct}%" if volatility_20d_pct is not None else "")
            + ". "
            + (ratios.get("note") or "")
        ).strip()

        diff_from_prior: str | None = None
        if prior_briefs:
            prior_thesis = prior_briefs[0].get("thesis")
            if prior_thesis and prior_thesis != thesis:
                diff_from_prior = (
                    f"Thesis changed from {prior_thesis} to {thesis} "
                    "since the most recent prior brief."
                )
            else:
                diff_from_prior = "Thesis is unchanged from the most recent prior brief."

        if thesis == "bullish":
            suggested_action = "buy"
        elif thesis == "bearish":
            suggested_action = "sell"
        else:
            suggested_action = "hold"

        result = AnalystBriefResult(
            thesis=thesis,
            confidence=confidence,
            summary=summary,
            evidence=evidence,
            diff_from_prior=diff_from_prior,
            suggested_action=suggested_action,
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
