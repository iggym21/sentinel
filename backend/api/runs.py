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
from config import settings
from database import get_db
from providers.alpaca_provider import AlpacaProvider
from providers.demo_provider import DemoProvider
from providers.edgar_provider import EdgarProvider
from services.watchdog_service import run_watchdog_tick

router = APIRouter(prefix="/watchdog", tags=["watchdog"])

_EDGAR_USER_AGENT = "Sentinel MVP research@sentinel.example"


def _build_market_provider():
    if settings.alpaca_api_key:
        return AlpacaProvider(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_secret_key,
            base_url=settings.alpaca_base_url,
        )
    return DemoProvider()


@router.post("/tick")
def trigger_watchdog_tick(db: Session = Depends(get_db)) -> list[dict]:
    market = _build_market_provider()
    filings = EdgarProvider(user_agent=_EDGAR_USER_AGENT)
    backend = get_reasoning_backend()
    try:
        return run_watchdog_tick(db, market, filings, backend=backend)
    finally:
        if isinstance(market, AlpacaProvider):
            market.close()
