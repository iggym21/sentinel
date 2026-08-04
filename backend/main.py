"""Sentinel FastAPI app: exposes the DB models, providers, and
Analyst/Watchdog services (Tasks 1-13) over REST, and wires the
APScheduler-driven Watchdog tick (`scheduler.py`) into the app
lifecycle.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api import briefs, runs, tickers, watchlist
from scheduler import start_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = start_scheduler(app.state)
    try:
        yield
    finally:
        scheduler.shutdown()


app = FastAPI(title="Sentinel", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(watchlist.router, prefix="/api")
app.include_router(briefs.router, prefix="/api")
app.include_router(tickers.router, prefix="/api")
app.include_router(runs.router, prefix="/api")
