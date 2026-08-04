# Sentinel — Build Plan

A rough day-by-day breakdown for a 1-2 week build. Each phase should be independently testable before moving to the next — verify agents work via a script/CLI before wiring up the UI.

## Phase 1: Foundations (Days 1-2)
- [ ] Repo scaffold: `backend/` (FastAPI + SQLAlchemy) and `frontend/` (Next.js + Tailwind)
- [ ] DB models from `docs/DATA_MODELS.md`, migrations set up (Alembic)
- [ ] Alpaca API integration: fetch price/volume/news for a hardcoded ticker list
- [ ] Basic threshold-based anomaly check (no LLM yet) — prove you can detect a volume/price spike in code
- [ ] `.env.example` filled in, README updated with setup steps

## Phase 2: Analyst Agent (Days 3-5)
- [ ] Implement each tool from `docs/AGENT_TOOLS.md` as a Python function, tested independently (e.g. `get_filings("AAPL")` returns real EDGAR results)
- [ ] Implement the agent loop per `docs/ARCHITECTURE.md` §2.2, using Claude API tool use
- [ ] Persist full trace to `AgentRun.trace` per the schema in `docs/DATA_MODELS.md`
- [ ] CLI/script test: run the Analyst Agent for one ticker end-to-end, print the resulting Brief
- [ ] Sanity-check: does the brief cite real evidence, and does it call `get_prior_briefs`?

## Phase 3: Watchdog Agent + Wiring (Days 6-8)
- [ ] Implement the judgment-tier LLM call (single call, `submit_decision` tool, no loop)
- [ ] Wire: scheduler tick → threshold check → (if crossed) judgment call → (if triggered) kick off Analyst Agent → save Anomaly + AgentRun + Brief
- [ ] APScheduler job running every 15-30 min (configurable), only during market hours
- [ ] Seed/backfill option: a script to manually trigger a few Watchdog ticks against historical data, so you have demo data without waiting for real market hours

## Phase 4: Dashboard (Days 9-11)
- [ ] Watchlist view: cards per ticker with live status (poll `/api/watchlist` every 10-15s)
- [ ] Brief feed: reverse-chronological list
- [ ] Brief detail view with expandable reasoning trace (render `AgentRun.trace` as a step timeline)
- [ ] Ticker history view with diff highlighting between the two most recent briefs
- [ ] Basic responsive styling — doesn't need to be fancy, but should look intentional (see your `frontend-design` conventions if using Claude Code with that skill available)

## Phase 5: Polish + Deploy (Days 12-14)
- [ ] Paper trade log (stretch goal — cut if behind schedule)
- [ ] Deploy backend (Render/Fly.io) + frontend (Vercel)
- [ ] Seed the deployed instance with a few real briefs so it's not empty on first view
- [ ] Record a 60-90 second demo video/GIF showing: watchlist → trigger → reasoning trace → brief → diff view
- [ ] Write the resume bullet(s) once real metrics exist (e.g., number of tools, number of briefs generated, latency of a full Analyst run)

## Cut list if time runs short (in order of what to cut first)
1. Paper trade log
2. Ticker diff view (keep the brief detail view, drop the comparison)
3. Live scheduler (fall back to a manual "run now" button instead of automatic polling)
4. WebSocket/live updates (polling is fine)

Do not cut: the reasoning-trace UI. It's the entire point of the demo.
