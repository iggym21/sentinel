"""`/api/watchdog` router: manual trigger for a Watchdog sweep, for
demo/testing without waiting for the scheduler (`backend/scheduler.py`
runs the same sweep automatically on an interval).

Constructs real providers/backend at request time (real if keys are
configured, else the free/offline `DemoProvider` / key-free
`EdgarProvider`) — this hits real EDGAR/Alpaca/Claude, so it is
deliberately left untested by Task 14's `test_api.py` (Task 15's seed
script exercises it for real).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from agents.backend_factory import get_reasoning_backend
from database import get_db
from providers.factory import build_providers
from services.watchdog_service import run_watchdog_tick

router = APIRouter(prefix="/watchdog", tags=["watchdog"])


@router.post("/tick")
def trigger_watchdog_tick(db: Session = Depends(get_db)) -> list[dict]:
    with build_providers() as (market, filings):
        backend = get_reasoning_backend()
        return run_watchdog_tick(db, market, filings, backend=backend)
