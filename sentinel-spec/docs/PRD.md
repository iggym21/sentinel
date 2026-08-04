# Sentinel — Product Requirements Document

**Version:** 1.0
**Author:** Ignatius Martin
**Status:** Draft

---

## 1. Overview

Sentinel is a full-stack, agentic market research tool. It continuously watches a small stock watchlist, autonomously decides when something is worth investigating, and then runs a deeper research agent that produces a structured brief — the kind of first-pass work a junior equity research analyst does manually. Two agents cooperate: a lightweight **Watchdog** that decides *when* to look closer, and a deeper **Analyst** that decides *what to say* once triggered.

The project serves two purposes: a personal tool for tracking a watchlist without manually checking the news every day, and a portfolio piece demonstrating full-stack, multi-agent, and tool-use competency.

---

## 2. Goals

- Build a working MVP within 1–2 weeks, publicly deployable
- Demonstrate a genuine closed-loop agent (observe → decide → act) plus a genuine multi-step reasoning agent (plan → tool calls → synthesize), not a single prompt-and-response wrapper
- Produce a UI that visibly shows the agent's reasoning trace — this is the core "wow" factor for a demo
- Be genuinely useful: a watchlist of ~5-10 tickers you'd actually want daily briefs on

## 3. Non-Goals (MVP)

- Real trade execution (paper/simulated only)
- Multi-user accounts / auth
- Asset classes beyond US equities (no crypto, no options)
- Mobile-native app
- Guaranteeing financial accuracy — this is a research/demo tool, not investment advice

## 4. Target Users

- **Primary:** Ignatius — personal watchlist monitoring
- **Secondary:** Recruiters / technical interviewers reviewing the portfolio

## 5. Core Features

### 5.1 Watchlist Management
- Add/remove tickers from a watchlist (hardcoded list acceptable for MVP; simple CRUD is a stretch goal)
- Each ticker shows: current price, day change, last brief date, "status" (quiet / triggered / investigating)

### 5.2 Watchdog Agent
- Runs on a schedule (e.g., every 15-30 min during market hours for MVP; can be simulated/backfilled for demo purposes if real-time isn't practical)
- Pulls price, volume, and recent headlines for each watchlist ticker
- Two-tier detection:
  1. **Threshold tier (cheap, no LLM):** flag if volume > 2x 20-day average, or price move > configurable % in a session
  2. **Judgment tier (LLM):** for anything that clears the threshold, Claude reasons over the data + headlines to decide "is this genuinely noteworthy or just normal volatility?" and outputs a trigger decision with a short rationale
- On trigger, creates an `Anomaly` record and kicks off the Analyst Agent for that ticker

### 5.3 Analyst Agent
- Given a ticker (and optionally the triggering anomaly context), autonomously plans and executes a research workflow using tool calls:
  - Fetch recent SEC filings (10-K/10-Q/8-K) via EDGAR full-text search
  - Fetch recent news/headlines
  - Calculate basic financial ratios from available data (P/E, revenue growth, margin trends — whatever is available from the free data source)
  - Search prior briefs for this ticker (to compare/diff against past conclusions)
- Synthesizes findings into a structured **Brief**: summary, thesis (bullish/bearish/neutral), confidence score (1-5), key evidence with citations to which tool call produced it, and what changed vs. the last brief on this ticker
- The full sequence of tool calls and intermediate reasoning is persisted (not just the final answer) — this powers the reasoning-trace UI

### 5.4 Dashboard (Next.js)
- **Watchlist view:** live-updating cards per ticker (price, status, last brief snippet)
- **Brief feed:** reverse-chronological list of all briefs generated
- **Brief detail view:** full brief + expandable reasoning trace showing each tool call the Analyst made, in order, with inputs/outputs
- **Ticker history view:** all past briefs for one ticker, with a simple diff highlighting what changed between the two most recent briefs

### 5.5 Paper Trade Log (stretch, include if time allows)
- Each brief can optionally include a suggested action (buy/sell/hold) with a rationale
- User can "accept" a suggestion from the UI, which logs a simulated position (no real money, no broker integration)
- Simple P&L tracking against current price for logged paper trades

---

## 6. Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js (App Router), React, Tailwind CSS |
| Backend | Python, FastAPI |
| Agent/AI | Claude API (Messages API, tool use) — `claude-haiku-4-5-20251001` for the Watchdog's judgment tier, `claude-sonnet-5` for the Analyst agent |
| Database | Postgres via Neon (free tier, permanent, scale-to-zero) for deployed use; SQLite for local dev, via SQLAlchemy |
| Market data | Alpaca Markets API (free tier) — price, volume, news |
| Filings | SEC EDGAR full-text search API (free, no key) |
| Scheduler | APScheduler (in-process, MVP-appropriate) |
| Deployment | Vercel (frontend, free Hobby tier) + Render (backend, $7/mo Starter to keep the scheduler always-on — the free tier spins down after 15 min idle, which breaks background polling) |

---

## 7. Success Criteria for Demo

- Can point Sentinel at a watchlist and, within the demo window, show at least one full trigger → investigate → brief cycle happening live (or convincingly fast-forwarded/seeded with historical data for the recording)
- Reasoning trace UI clearly shows multi-step tool use, not a black box
- At least one ticker has 2+ briefs so the diff/"what changed" view can be demoed
