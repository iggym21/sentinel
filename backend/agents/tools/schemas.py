"""Analyst tool JSON schemas for the Claude API `tools` parameter.

Transcribed verbatim from `sentinel-spec/docs/AGENT_TOOLS.md` (Analyst
Agent tools section) — do not hand-edit these without updating that
doc too, they're expected to match exactly.

`submit_brief` is the terminal action: it ends the agent loop rather
than dispatching through `registry.build_tool_dispatch` (see Task 10's
agent loop), but it's still part of the schema list handed to the
Claude API so the model can call it.
"""

from __future__ import annotations

TOOL_SCHEMAS: list[dict] = [
    {
        "name": "get_filings",
        "description": "Search SEC EDGAR for recent filings by a company. Returns a list of filings with type, date, and URL.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "form_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "e.g. ['10-K', '10-Q', '8-K']",
                },
                "limit": {"type": "integer", "default": 5},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_filing_text",
        "description": "Fetch and return cleaned text content of a specific filing by its URL, for detailed review.",
        "input_schema": {
            "type": "object",
            "properties": {
                "filing_url": {"type": "string"},
                "max_chars": {
                    "type": "integer",
                    "default": 8000,
                    "description": "Truncate to this length to control context usage",
                },
            },
            "required": ["filing_url"],
        },
    },
    {
        "name": "get_recent_news",
        "description": "Get recent news headlines and short summaries for a ticker.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "days": {"type": "integer", "default": 7},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_price_history",
        "description": "Get daily OHLCV price history for a ticker.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "days": {"type": "integer", "default": 30},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "calculate_ratios",
        "description": "Calculate basic financial ratios (P/E, revenue growth, margin trends) from available fundamental data for a ticker.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "get_prior_briefs",
        "description": "Retrieve Sentinel's own previously generated briefs for this ticker, to compare against current findings.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string"},
                "limit": {"type": "integer", "default": 3},
            },
            "required": ["ticker"],
        },
    },
    {
        "name": "submit_brief",
        "description": "Submit your final research brief. Call this only once you have gathered sufficient evidence from the other tools.",
        "input_schema": {
            "type": "object",
            "properties": {
                "thesis": {"type": "string", "enum": ["bullish", "bearish", "neutral"]},
                "confidence": {"type": "integer", "minimum": 1, "maximum": 5},
                "summary": {
                    "type": "string",
                    "description": "2-4 sentence human-readable summary",
                },
                "evidence": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "claim": {"type": "string"},
                            "source_tool": {"type": "string"},
                            "source_ref": {
                                "type": "string",
                                "description": "e.g. filing URL or headline",
                            },
                        },
                        "required": ["claim", "source_tool"],
                    },
                },
                "diff_from_prior": {
                    "type": "string",
                    "description": "What changed vs. the last brief on this ticker, if any prior brief exists",
                },
                "suggested_action": {"type": "string", "enum": ["buy", "sell", "hold"]},
            },
            "required": ["thesis", "confidence", "summary", "evidence"],
        },
    },
]
