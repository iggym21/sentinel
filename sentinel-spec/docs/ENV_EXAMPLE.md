# Environment Variables

Copy this into a `.env` file in `backend/` and fill in your own values.

```bash
# Anthropic
ANTHROPIC_API_KEY=
# Model split — see docs/ARCHITECTURE.md §2 and docs/AGENT_TOOLS.md for rationale
WATCHDOG_MODEL=claude-haiku-4-5-20251001
ANALYST_MODEL=claude-sonnet-5

# Market data (Alpaca — free paper trading account works for market data too)
ALPACA_API_KEY=
ALPACA_SECRET_KEY=
ALPACA_BASE_URL=https://paper-api.alpaca.markets

# Optional: dedicated news API — only needed if you skip Alpaca's built-in (free) news endpoint
NEWS_API_KEY=

# Database — Neon Postgres (free tier, permanent). Get your connection string from neon.tech.
DATABASE_URL=postgresql://user:password@ep-example-123456.us-east-2.aws.neon.tech/sentinel?sslmode=require
# For local dev with SQLite instead:
# DATABASE_URL=sqlite:///./sentinel.db

# Watchdog config
WATCHDOG_INTERVAL_MINUTES=15
VOLUME_SPIKE_THRESHOLD_MULTIPLIER=2.0
PRICE_MOVE_THRESHOLD_PCT=3.0

# App
ENVIRONMENT=development
```

## Where to get each key

- **ANTHROPIC_API_KEY** — console.anthropic.com
- **ALPACA_API_KEY / ALPACA_SECRET_KEY** — sign up for a free paper trading account at alpaca.markets; paper account keys work fine for market data
- **NEWS_API_KEY** — only needed if you skip Alpaca's built-in news endpoint in favor of a dedicated news API
- **DATABASE_URL** — create a free permanent Postgres project at neon.tech (no card required); copy the connection string it gives you
- **SEC EDGAR** — no key required

## Cost notes

- `WATCHDOG_MODEL` (Haiku 4.5, $1/$5 per MTok) runs frequently but does shallow single-step judgment — cheap by design
- `ANALYST_MODEL` (Sonnet 5, $2/$10 per MTok through Aug 31 2026, then $3/$15) runs only on confirmed triggers and does the deep multi-step reasoning — worth the higher cost since it's infrequent
- See `docs/ARCHITECTURE.md` §5 for the full cost-architecture rationale
