"""`/api/briefs` router: list briefs and fetch a single brief with its full
Analyst reasoning trace."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc
from sqlalchemy.orm import Session

from database import get_db
from models.brief import Brief
from models.ticker import Ticker
from schemas.brief import BriefDetail, BriefOut

router = APIRouter(prefix="/briefs", tags=["briefs"])


@router.get("", response_model=list[BriefOut])
def list_briefs(
    ticker: str | None = None, limit: int = 50, db: Session = Depends(get_db)
) -> list[Brief]:
    query = db.query(Brief)
    if ticker:
        matched_ticker = db.query(Ticker).filter_by(symbol=ticker.strip().upper()).one_or_none()
        if matched_ticker is None:
            return []
        query = query.filter(Brief.ticker_id == matched_ticker.id)

    return query.order_by(desc(Brief.created_at)).limit(limit).all()


@router.get("/{brief_id}", response_model=BriefDetail)
def get_brief_detail(brief_id: int, db: Session = Depends(get_db)) -> Brief:
    brief = db.get(Brief, brief_id)
    if brief is None:
        raise HTTPException(status_code=404, detail="Brief not found")
    return brief
