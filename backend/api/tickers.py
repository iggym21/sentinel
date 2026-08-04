"""`/api/tickers` router: per-ticker brief history and the manual "run
Analyst now" fallback (`sentinel-spec/docs/BUILD_PLAN.md` cut list — no
scheduler wait needed for a demo/manual trigger).

`POST /{symbol}/run` constructs real providers/backend at request time
(real if keys are configured, else the free/offline `DemoProvider` /
key-free `EdgarProvider`) — this hits real EDGAR/Alpaca/Claude, so it is
deliberately left untested by Task 14's `test_api.py` (Task 15's seed
script exercises it for real).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session

from agents.backend_factory import get_reasoning_backend
from config import settings
from database import get_db
from models.brief import Brief
from models.ticker import Ticker
from providers.alpaca_provider import AlpacaProvider
from providers.demo_provider import DemoProvider
from providers.edgar_provider import EdgarProvider
from schemas.brief import BriefOut
from services.analyst_service import run_analyst_for_ticker

router = APIRouter(prefix="/tickers", tags=["tickers"])

_EDGAR_USER_AGENT = "Sentinel MVP research@sentinel.example"


def _build_market_provider():
    if settings.alpaca_api_key:
        return AlpacaProvider(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_secret_key,
            base_url=settings.alpaca_base_url,
        )
    return DemoProvider()


@router.get("/{symbol}/history")
def get_ticker_history(symbol: str, db: Session = Depends(get_db)) -> dict:
    ticker = db.query(Ticker).filter_by(symbol=symbol.strip().upper()).one_or_none()
    if ticker is None:
        raise HTTPException(status_code=404, detail="Ticker not found")

    briefs = (
        db.query(Brief)
        .filter(Brief.ticker_id == ticker.id)
        .order_by(desc(Brief.created_at))
        .all()
    )
    diff = briefs[0].diff_from_prior if briefs else None

    return {
        "briefs": [BriefOut.model_validate(b) for b in briefs],
        "diff": diff,
    }


@router.post("/{symbol}/run", response_model=BriefOut)
def run_analyst_now(symbol: str, db: Session = Depends(get_db)) -> Brief:
    market = _build_market_provider()
    filings = EdgarProvider(user_agent=_EDGAR_USER_AGENT)
    backend = get_reasoning_backend()
    try:
        return run_analyst_for_ticker(
            db, symbol.strip().upper(), market, filings, backend=backend
        )
    finally:
        if isinstance(market, AlpacaProvider):
            market.close()
