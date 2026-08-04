# CLAUDE.md — Project Context for Claude Code

This file orients Claude Code (or any agentic coding assistant) working in this repo. Read this first, then `docs/PRD.md`, then `docs/ARCHITECTURE.md` before writing code.

## What this project is

**Sentinel** is an autonomous market research agent. It watches a stock watchlist, decides when something is worth investigating (a "trigger"), and then runs a deeper multi-step research agent that produces a structured brief (thesis + confidence score + reasoning trace). Optionally logs a paper-trade recommendation.

Two cooperating agents:
1. **Watchdog Agent** — polls market data on a schedule, decides "is this normal noise or worth investigating?"
2. **Analyst Agent** — when triggered, autonomously calls tools (filings, news, ratio calculators) to build a research brief

Full detail: see `docs/PRD.md` (product spec) and `docs/ARCHITECTURE.md` (technical design).

## Build order (see docs/BUILD_PLAN.md for full detail)

1. Data layer + basic threshold-based anomaly detection (no LLM yet)
2. Analyst agent: tool-use loop that drafts a brief for a given ticker
3. Wire Watchdog → Analyst trigger; upgrade Watchdog to LLM judgment
4. Dashboard: live feed, brief detail view with reasoning trace
5. Paper-trade log + polish + deploy

**Build in this order.** Don't start the dashboard before the agents work end-to-end from the CLI/API — verify each agent with a script before wiring up the UI.

## Tech stack (see docs/ARCHITECTURE.md for rationale)

- Frontend: Next.js (App Router) + React + Tailwind
- Backend: Python + FastAPI
- Agent/AI: Claude API (Messages API with tool use) — `claude-haiku-4-5-20251001` for the Watchdog's judgment tier, `claude-sonnet-5` for the Analyst agent (see docs/ARCHITECTURE.md §2 for rationale)
- DB: Postgres via Neon (free tier, permanent) for deployed use; SQLite acceptable for local dev
- Market data: Alpaca or Polygon.io (free tier)
- News: NewsAPI or Alpaca news endpoint
- Filings: SEC EDGAR full-text search API (free, no key required)
- Scheduler: APScheduler (in-process) for MVP; can move to a proper queue later

## Conventions

- All agent tool schemas live in `backend/agents/tools/` — one file per tool, exported as a JSON schema + a Python function with matching signature
- Every agent run (Watchdog decision or Analyst brief) is persisted with its full reasoning trace — never discard intermediate agent steps, they're needed for the UI's "show reasoning" view
- Use Pydantic models for all API request/response bodies and mirror them in `docs/DATA_MODELS.md` if you change a schema
- Keep secrets in `.env` (see `.env.example`) — never hardcode API keys
- This is a portfolio/demo project: prioritize a working, demoable end-to-end flow over exhaustive edge-case handling. It's fine to hardcode a small watchlist (5-10 tickers) for the MVP.

## Environment variables

See `.env.example` for the full list. You will need your own API keys for: Anthropic, a market data provider (Alpaca or Polygon), and optionally a news API. SEC EDGAR requires no key.

## Non-goals for MVP (do not build these unless asked)

- Real money execution (paper trades only, logged to DB, never sent to a broker)
- User auth / multi-tenant support
- Mobile app
- Support for asset classes beyond US equities
