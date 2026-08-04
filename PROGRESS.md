# Sentinel — build progress

Two-agent (Watchdog + Analyst) autonomous market research tool. FastAPI + SQLAlchemy backend, Next.js frontend, pluggable providers (real Alpaca/EDGAR or offline `DemoProvider`) and pluggable reasoning backends (real Claude tool-use or offline `HeuristicBackend`) — runs and tests fully with zero API keys.

## Status: 14/20 tasks complete, all review-clean on `main`

Head: `96b00a4`. Full plan: `docs/superpowers/plans/2026-08-04-sentinel-mvp.md`.

### Done (backend, fully wired end-to-end)
1. Repo scaffold + config
2. DB engine/session + Alembic
3. DB models + Pydantic schemas + migration
4. Provider base types + `DemoProvider`
5. `AlpacaProvider` (real integration, mocked in tests)
6. Threshold-based anomaly detector
7. EDGAR filings provider
8. Analyst tool functions + registry
9. `TraceRecorder` + reasoning-backend scaffolding
10. Analyst agent loop (`HeuristicBackend` + `ClaudeBackend`)
11. Analyst orchestration service + CLI (`backend/scripts/run_analyst.py`)
12. Watchdog judgment call (`watchdog_judge` on both backends)
13. Watchdog tick orchestration (`backend/services/watchdog_service.py`)
14. FastAPI app, REST routers, APScheduler wiring (`backend/main.py`)

### Remaining
15. Seed/demo data script (`backend/scripts/seed_demo_data.py`)
16. Next.js scaffold + typed API client
17. Watchlist dashboard page
18. Brief feed + brief detail + reasoning-trace UI
19. Ticker history + diff view
20. End-to-end verification with real backend + browser (Chrome)
21. Final whole-branch review → `superpowers:finishing-a-development-branch`

## How to resume

This is being built with `superpowers:subagent-driven-development` — fresh implementer subagent per task, task review (spec + quality), fix loop, ledger tracking. To continue:

1. Say something like "continue the Sentinel build" / "keep going on the plan" — this re-invokes the same skill.
2. The skill reads its ledger at `.superpowers/sdd/2026-08-04-sentinel-mvp/progress.md` (git-ignored workspace scratch — NOT this file) to see which tasks are `complete` and resumes at Task 15 automatically. Don't delete that directory before the plan finishes — it's the loop's recovery map (task briefs, implementer reports, review diffs).
3. No further plan-conflict scan needed — already done once at the start of this build (clean, no contradictions found).

## Deferred minor findings (not blocking, noted for final review triage)

- `_build_market_provider()` duplicated verbatim across `watchlist.py`/`tickers.py`/`runs.py`/`scheduler.py` — candidate for a shared `providers/factory.py`.
- `GET /api/tickers/{symbol}/history` has no `response_model` (unlike other endpoints).
- No test coverage for the "investigating" watchlist status branch or `_as_utc` timezone handling.
- `AgentRun.anomaly_id` unique constraint is respected by current control flow but untested directly.
- No automated coverage of `run_analyst.py` CLI itself (manually verified end-to-end).

Full history of every task's fix rounds and parked/deferred findings: `.superpowers/sdd/2026-08-04-sentinel-mvp/progress.md`.

## Quick commands

```bash
# backend tests
cd backend && source venv/bin/activate && pytest -v

# run analyst manually (offline, real EDGAR)
cd backend && source venv/bin/activate && python scripts/run_analyst.py AAPL

# boot API
cd backend && source venv/bin/activate && uvicorn main:app --reload
```

## Key docs

- Spec: `sentinel-spec/docs/` (PRD, ARCHITECTURE, DATA_MODELS, AGENT_TOOLS, ENV_EXAMPLE, BUILD_PLAN)
- Plan: `docs/superpowers/plans/2026-08-04-sentinel-mvp.md`
- Out of scope (deliberate cuts): Paper Trade Log, cloud deployment, WebSocket/SSE live updates, real credentials exercised live — see plan's final section.
