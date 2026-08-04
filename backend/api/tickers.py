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
from database import get_db
from models.brief import Brief
from models.ticker import Ticker
from providers.factory import build_providers
from schemas.brief import BriefOut
from schemas.ticker import normalize_symbol
from services.analyst_service import run_analyst_for_ticker

router = APIRouter(prefix="/tickers", tags=["tickers"])


@router.get("/{symbol}/history")
def get_ticker_history(symbol: str, db: Session = Depends(get_db)) -> dict:
    ticker = db.query(Ticker).filter_by(symbol=normalize_symbol(symbol)).one_or_none()
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
    normalized_symbol = normalize_symbol(symbol)
    with build_providers() as (market, filings):
        backend = get_reasoning_backend()
        return run_analyst_for_ticker(
            db, normalized_symbol, market, filings, backend=backend
        )
