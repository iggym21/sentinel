"""Analyst tool: get_prior_briefs.

Thin adapter from Brief ORM rows (joined to Ticker by symbol) to a
list of plain, JSON-serializable dicts, so the Analyst can compare its
current findings against Sentinel's own prior output on this ticker.
"""

from __future__ import annotations

from sqlalchemy import desc
from sqlalchemy.orm import Session

from models.brief import Brief
from models.ticker import Ticker


def get_prior_briefs(db: Session, ticker: str, limit: int = 3) -> list[dict]:
    briefs = (
        db.query(Brief)
        .join(Ticker, Brief.ticker_id == Ticker.id)
        .filter(Ticker.symbol == ticker)
        .order_by(desc(Brief.created_at))
        .limit(limit)
        .all()
    )
    return [
        {
            "id": brief.id,
            "created_at": brief.created_at.isoformat(),
            "thesis": getattr(brief.thesis, "value", brief.thesis),
            "confidence": brief.confidence,
            "summary": brief.summary,
            "diff_from_prior": brief.diff_from_prior,
        }
        for brief in briefs
    ]
