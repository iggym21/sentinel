# Sentinel — Technical Architecture

## 1. System Overview

```
                         ┌─────────────────────┐
                         │   Next.js Frontend   │
                         │  (dashboard, briefs, │
                         │   reasoning trace)   │
                         └──────────┬───────────┘
                                    │ REST (+ polling or WS for live updates)
                         ┌──────────▼───────────┐
                         │   FastAPI Backend     │
                         │  ┌─────────────────┐  │
                         │  │  Scheduler       │  │  (APScheduler, in-process)
                         │  │  (runs Watchdog  │  │
                         │  │   every N min)   │  │
                         │  └────────┬────────┘  │
                         │           │            │
                         │  ┌────────▼────────┐  │
                         │  │  Watchdog Agent  │  │──► trigger? ──► Analyst Agent
                         │  └─────────────────┘  │
                         │  ┌─────────────────┐  │
                         │  │  Analyst Agent   │  │
                         │  └─────────────────┘  │
                         └──────────┬───────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              ▼                     ▼                     ▼
      ┌──────────────┐     ┌───────────────┐     ┌────────────────┐
      │  Postgres     │     │  Alpaca API    │     │  SEC EDGAR API  │
      │  (Neon) /     │     │  (price/volume │     │  (filings)      │
      │  SQLite local │     │   /news)       │     │                 │
      └──────────────┘     └───────────────┘     └────────────────┘
                                    ▲
                                    │
                         ┌──────────┴───────────┐
                         │    Claude API         │
                         │ (both agents call     │
                         │  this for reasoning)  │
                         └───────────────────────┘
```

## 2. Agent Design

Both agents use the Claude Messages API with **tool use**. The key architectural point: an "agent" here means a loop where Claude can call tools, see results, and decide to call more tools or finish — not a single prompt-completion.

### 2.1 Watchdog Agent

**Trigger:** scheduler tick (every 15-30 min during market hours)

**Flow per ticker:**
1. Backend fetches price/volume/headlines directly (no LLM needed for raw data fetch — this is cheaper and more reliable done in plain code)
2. Cheap threshold check in code: does volume or price move exceed a configurable bound? If no → stop, log a "quiet" check, done.
3. If yes → call Claude with the data + headlines + a system prompt asking it to judge: is this genuinely noteworthy given context (e.g., a 5% move on no news might be less interesting than a 2% move right after an earnings headline)? Claude has **no tools** at this tier — it's a single reasoning call, not a multi-step agent, since the data is already in hand.
4. Claude returns a structured decision: `{trigger: bool, rationale: str}`
5. If `trigger: true` → create an `Anomaly` row, enqueue the Analyst Agent for that ticker

**Model: `claude-haiku-4-5-20251001`.** This is a single, cheap, low-latency call, not deep multi-step reasoning — Haiku is more than capable of this judgment and is priced well below Sonnet, which matters since this tier runs far more often than the Analyst (every threshold-crossing tick, vs. only on confirmed triggers).

**Why split threshold (code) + judgment (LLM):** keeps API costs down (most polling ticks are quiet and never hit the LLM at all) and makes the "is this real" decision use context an if/else can't easily capture.

### 2.2 Analyst Agent

**Trigger:** an Anomaly record (from Watchdog) OR a manual "research this ticker" request from the UI

**Model: `claude-sonnet-5`.** This tier does genuine multi-step reasoning across several tool calls and needs to synthesize evidence into a coherent thesis — worth the higher cost per call since it runs far less often than the Watchdog and the output quality directly determines whether the brief is any good.

**This is the multi-step agentic loop.** Claude is given a system prompt describing its role and a set of tools, then runs in a loop:

```
messages = [system_prompt, user_message(ticker, trigger_context)]
loop:
    response = claude.messages.create(model="claude-sonnet-5", messages=messages, tools=TOOLS)
    persist_trace_step(response)  # <-- critical for the reasoning-trace UI
    if response.stop_reason == "tool_use":
        for each tool_call in response.content:
            result = execute_tool(tool_call)          # see tools list below
            persist_trace_step(tool_call, result)
            messages.append(tool_result_message(result))
        continue loop
    else:
        # Claude decided it has enough info and returned final text
        brief = parse_structured_brief(response)
        break
save Brief to DB with full trace
```

**Available tools for the Analyst Agent** (see `docs/AGENT_TOOLS.md` for full JSON schemas):
- `get_filings(ticker, form_types, limit)` — SEC EDGAR full-text search
- `get_filing_text(filing_url)` — fetch and return cleaned text of a specific filing
- `get_recent_news(ticker, days)` — headlines from Alpaca/news API
- `get_price_history(ticker, days)` — OHLCV data
- `calculate_ratios(ticker)` — computes basic ratios from available fundamentals
- `get_prior_briefs(ticker, limit)` — pulls Sentinel's own past briefs on this ticker for comparison

**Output contract:** the Analyst Agent's final message must be structured (use Claude's tool-use mechanism itself, or a final "submit_brief" tool call) matching the `Brief` schema in `docs/DATA_MODELS.md`. Using a `submit_brief` tool as the terminal action (rather than parsing free text) is strongly recommended — it's more reliable than regex/JSON-parsing a text response.

## 3. Why two agents instead of one

A single agent that both watches and researches would either (a) run the expensive multi-step research loop on every polling tick, which is slow and costly, or (b) not have a good way to represent "quick glance" vs "deep dive" as different reasoning depths. Splitting them mirrors how a real research desk works: a cheap continuous scan, and an expensive deep-dive only when warranted. It's also a stronger portfolio story — it shows you can architect *when* to invoke an LLM, not just how.

## 4. Live updates to the frontend

For MVP, simple polling (frontend re-fetches `/api/watchlist` and `/api/briefs` every 10-15s) is sufficient and much simpler than WebSockets. Upgrade to WebSockets/SSE only if time allows — it's a nice-to-have for the demo, not core to the architecture.

## 5. Cost notes

The Watchdog's threshold tier (plain code, no LLM) filters out most polling ticks for free — Claude is only called for ticks that already crossed a volume/price bound, and even then only Haiku 4.5's judgment call, not the full Analyst loop. The expensive multi-step Analyst run only fires on confirmed triggers. This two-tier + two-model split is deliberate cost architecture, not just a performance optimization: it's the difference between paying for an LLM call on every scheduler tick vs. only on the handful that matter. Combine with prompt caching (system prompts and tool schemas are static across calls) for further savings once usage grows beyond demo scale.

## 6. Persisting the reasoning trace

This is the single most important technical detail for the demo to land. Every Analyst Agent run must store, in order:
1. The initial prompt/context
2. Each tool call (name, input arguments)
3. Each tool result
4. The final synthesized brief

Store this as a `trace` JSON column on the `AgentRun` table (see `docs/DATA_MODELS.md`) — a list of step objects. The frontend renders this as an expandable timeline. Don't discard intermediate steps to save space; they're the whole point.
