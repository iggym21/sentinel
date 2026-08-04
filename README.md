# Sentinel

An autonomous market research agent. Watches a stock watchlist, decides when something's worth investigating, and runs a multi-step research agent that produces a structured, cited brief.

See `sentinel-spec/CLAUDE.md` for a project orientation if you're using Claude Code, or read in this order:
1. `sentinel-spec/docs/PRD.md` — what we're building and why
2. `sentinel-spec/docs/ARCHITECTURE.md` — how the two agents work and how they fit together
3. `sentinel-spec/docs/DATA_MODELS.md` — database schema
4. `sentinel-spec/docs/AGENT_TOOLS.md` — exact tool schemas for the Claude API
5. `sentinel-spec/docs/BUILD_PLAN.md` — day-by-day build order

## Quick start (once scaffolded)

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp ../.env.example .env   # fill in your API keys
alembic upgrade head
uvicorn main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

## Required API keys

- **Anthropic API key** — for both agents
- **Alpaca API key** (free tier, paper account) — price/volume/news
- SEC EDGAR requires no key

See `backend/.env.example` for the full list of environment variables.
