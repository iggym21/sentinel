# Sentinel

An autonomous market research agent. Watches a stock watchlist, decides when something's worth investigating, and runs a multi-step research agent that produces a structured, cited brief.

See `sentinel-spec/CLAUDE.md` for a project orientation if you're using Claude Code, or read in this order:
1. `sentinel-spec/docs/PRD.md` — what we're building and why
2. `sentinel-spec/docs/ARCHITECTURE.md` — how the two agents work and how they fit together
3. `sentinel-spec/docs/DATA_MODELS.md` — database schema
4. `sentinel-spec/docs/AGENT_TOOLS.md` — exact tool schemas for the Claude API
5. `sentinel-spec/docs/BUILD_PLAN.md` — day-by-day build order

## Quick start

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # defaults run fully offline — see "Optional API keys" below
alembic upgrade head
python scripts/seed_demo_data.py   # populates a demo watchlist + briefs
uvicorn main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## Optional API keys (the app runs fully offline without them)

Sentinel is designed to run with **zero API keys**: `cp .env.example .env` as-is
and everything above works. Two swappable-in defaults make that possible:

- **`DemoProvider`** — a synthetic, no-network market-data provider used
  whenever `ALPACA_API_KEY` isn't set. SEC EDGAR itself never requires a key.
- **`HeuristicBackend`** — a rule-based reasoning backend used whenever
  `ANTHROPIC_API_KEY` isn't set, in place of the Claude-driven agent loop.

Both are opt-in upgrades, not requirements:

- **Anthropic API key** — set `ANTHROPIC_API_KEY` to switch the Analyst/Watchdog
  over to Claude (`ClaudeBackend`) instead of `HeuristicBackend`. You can also
  force the backend explicitly via `REASONING_BACKEND=llm` or `heuristic`.
- **Alpaca API key** (free tier, paper account) — set `ALPACA_API_KEY` /
  `ALPACA_SECRET_KEY` to switch price/volume/news over to real market data
  instead of `DemoProvider`'s synthetic data.

See `backend/.env.example` for the full list of environment variables.
