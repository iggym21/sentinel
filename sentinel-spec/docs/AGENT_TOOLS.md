# Sentinel — Agent Tool Schemas

These are the tool definitions to pass to the Claude API's `tools` parameter. Implement each as a plain Python function in `backend/agents/tools/`, matching the schema's input, and register them in a `TOOLS` list + a name→function dispatch dict used by the agent loop.

## Watchdog Agent

The Watchdog's judgment tier does **not** use tools — it receives pre-fetched data in the prompt and returns a single structured decision. Use a `submit_decision` tool as the only tool, purely to force structured output:

```json
{
  "name": "submit_decision",
  "description": "Submit your judgment on whether this ticker's activity warrants a deeper investigation.",
  "input_schema": {
    "type": "object",
    "properties": {
      "trigger": {"type": "boolean", "description": "true if this warrants a full research brief"},
      "rationale": {"type": "string", "description": "1-2 sentence explanation of the judgment"}
    },
    "required": ["trigger", "rationale"]
  }
}
```

## Analyst Agent tools

### get_filings
```json
{
  "name": "get_filings",
  "description": "Search SEC EDGAR for recent filings by a company. Returns a list of filings with type, date, and URL.",
  "input_schema": {
    "type": "object",
    "properties": {
      "ticker": {"type": "string"},
      "form_types": {"type": "array", "items": {"type": "string"}, "description": "e.g. ['10-K', '10-Q', '8-K']"},
      "limit": {"type": "integer", "default": 5}
    },
    "required": ["ticker"]
  }
}
```

### get_filing_text
```json
{
  "name": "get_filing_text",
  "description": "Fetch and return cleaned text content of a specific filing by its URL, for detailed review.",
  "input_schema": {
    "type": "object",
    "properties": {
      "filing_url": {"type": "string"},
      "max_chars": {"type": "integer", "default": 8000, "description": "Truncate to this length to control context usage"}
    },
    "required": ["filing_url"]
  }
}
```

### get_recent_news
```json
{
  "name": "get_recent_news",
  "description": "Get recent news headlines and short summaries for a ticker.",
  "input_schema": {
    "type": "object",
    "properties": {
      "ticker": {"type": "string"},
      "days": {"type": "integer", "default": 7}
    },
    "required": ["ticker"]
  }
}
```

### get_price_history
```json
{
  "name": "get_price_history",
  "description": "Get daily OHLCV price history for a ticker.",
  "input_schema": {
    "type": "object",
    "properties": {
      "ticker": {"type": "string"},
      "days": {"type": "integer", "default": 30}
    },
    "required": ["ticker"]
  }
}
```

### calculate_ratios
```json
{
  "name": "calculate_ratios",
  "description": "Calculate basic financial ratios (P/E, revenue growth, margin trends) from available fundamental data for a ticker.",
  "input_schema": {
    "type": "object",
    "properties": {
      "ticker": {"type": "string"}
    },
    "required": ["ticker"]
  }
}
```

### get_prior_briefs
```json
{
  "name": "get_prior_briefs",
  "description": "Retrieve Sentinel's own previously generated briefs for this ticker, to compare against current findings.",
  "input_schema": {
    "type": "object",
    "properties": {
      "ticker": {"type": "string"},
      "limit": {"type": "integer", "default": 3}
    },
    "required": ["ticker"]
  }
}
```

### submit_brief  (terminal action — ends the agent loop)
```json
{
  "name": "submit_brief",
  "description": "Submit your final research brief. Call this only once you have gathered sufficient evidence from the other tools.",
  "input_schema": {
    "type": "object",
    "properties": {
      "thesis": {"type": "string", "enum": ["bullish", "bearish", "neutral"]},
      "confidence": {"type": "integer", "minimum": 1, "maximum": 5},
      "summary": {"type": "string", "description": "2-4 sentence human-readable summary"},
      "evidence": {
        "type": "array",
        "items": {
          "type": "object",
          "properties": {
            "claim": {"type": "string"},
            "source_tool": {"type": "string"},
            "source_ref": {"type": "string", "description": "e.g. filing URL or headline"}
          },
          "required": ["claim", "source_tool"]
        }
      },
      "diff_from_prior": {"type": "string", "description": "What changed vs. the last brief on this ticker, if any prior brief exists"},
      "suggested_action": {"type": "string", "enum": ["buy", "sell", "hold"]}
    },
    "required": ["thesis", "confidence", "summary", "evidence"]
  }
}
```

## System prompt guidance

**Watchdog system prompt** (model: `claude-haiku-4-5-20251001`) should emphasize: distinguishing routine volatility from genuinely unusual activity, using the provided headlines as context, and being conservative (false triggers waste an expensive Analyst run). This is a single call with no tools — keep the prompt tight, since it runs on every threshold-crossing tick and cost/latency matter more here than at the Analyst tier.

**Analyst system prompt** (model: `claude-sonnet-5`) should emphasize: gathering evidence from multiple tools before concluding, always checking `get_prior_briefs` early so it can produce a meaningful diff, citing which tool produced each claim in `evidence`, and calling `submit_brief` as the final action rather than ending with plain text.

## Model selection rationale

Don't use Sonnet for the Watchdog or Haiku for the Analyst — the split matters:
- **Watchdog runs often, reasons shallowly:** every scheduler tick that crosses the code-level threshold triggers one Watchdog call. High frequency + simple single-step judgment = use the cheaper model (Haiku 4.5, $1/$5 per MTok).
- **Analyst runs rarely, reasons deeply:** only fires on confirmed triggers, but does several rounds of tool use and has to synthesize a coherent thesis. Low frequency + high reasoning demand = worth the pricier model (Sonnet 5, $2/$10 per MTok through Aug 31 2026, then $3/$15).

If you're testing locally and want to minimize spend further, you can temporarily point the Analyst at Haiku too — quality will be noticeably weaker (shallower tool-use planning, less coherent synthesis) but it's a reasonable way to debug the plumbing before switching back to Sonnet for real runs.
