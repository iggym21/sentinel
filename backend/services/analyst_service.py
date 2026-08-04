"""Analyst orchestration: wires the tool-calling agent loop to the DB.

`run_analyst_for_ticker` is the single entry point that ties together:

- `build_tool_dispatch` (Task 8) — the per-run tool functions the agent
  loop can call, closed over this ticker's providers/db session.
- `get_reasoning_backend` (Task 9/10) — the `ReasoningBackend` (Claude or
  Heuristic) that actually runs the investigate -> brief loop.
- The Task 3 ORM models (`Ticker`, `AgentRun`, `Brief`) — persistence.

It looks up (or creates) the `Ticker` row, opens an `AgentRun` in
"running" status, runs the agent loop, and on success persists the full
reasoning trace (`TraceRecorder.to_json()` — never truncated, per the
plan's Global Constraints) plus a new `Brief` row, linking
`AgentRun.brief_id` back to it. On any exception from the backend, the
`AgentRun` is marked "failed" and the exception is re-raised so the
caller (CLI script, future Watchdog wiring) knows the run didn't
succeed.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import desc
from sqlalchemy.orm import Session

from agents.backend_factory import get_reasoning_backend
from agents.reasoning_backend import ReasoningBackend
from agents.tools.registry import build_tool_dispatch
from models.agent_run import AgentRun
from models.brief import Brief
from models.ticker import Ticker
from providers.base import FilingsProvider, MarketDataProvider
from services.trace import TraceRecorder


def _get_or_create_ticker(db: Session, ticker_symbol: str) -> Ticker:
    ticker = db.query(Ticker).filter_by(symbol=ticker_symbol).one_or_none()
    if ticker is None:
        ticker = Ticker(
            symbol=ticker_symbol,
            added_at=datetime.now(timezone.utc),
            active=True,
        )
        db.add(ticker)
        db.commit()
        db.refresh(ticker)
    return ticker


def _compute_diff_from_prior(prior: Brief | None, thesis: str, confidence: int) -> str | None:
    """Simple text diff comparing the new thesis/confidence against the most
    recent prior brief for this ticker. Returns None if there is no prior."""
    if prior is None:
        return None

    prior_thesis = getattr(prior.thesis, "value", prior.thesis)
    if prior_thesis == thesis:
        parts = [f"Thesis unchanged ({thesis})"]
        if confidence != prior.confidence:
            parts.append(f"confidence {'up' if confidence > prior.confidence else 'down'} from {prior.confidence} to {confidence}")
        else:
            parts.append(f"confidence unchanged at {confidence}")
        return "; ".join(parts) + "."
    else:
        return f"Thesis flipped from {prior_thesis} to {thesis}."


def run_analyst_for_ticker(
    db: Session,
    ticker_symbol: str,
    market: MarketDataProvider,
    filings: FilingsProvider,
    anomaly_id: int | None = None,
    backend: ReasoningBackend | None = None,
) -> Brief:
    """Run the Analyst agent loop for `ticker_symbol` and persist the result.

    Creates an `AgentRun` (status="running"), runs the tool-calling loop via
    `backend.run_analyst` (defaults to `get_reasoning_backend()`), and on
    success writes the full trace plus a new `Brief`, marking the run
    "complete" and linking `AgentRun.brief_id`. On any exception from the
    backend, marks the run "failed" and re-raises.
    """
    if backend is None:
        backend = get_reasoning_backend()

    ticker = _get_or_create_ticker(db, ticker_symbol)

    agent_run = AgentRun(
        ticker_id=ticker.id,
        anomaly_id=anomaly_id,
        started_at=datetime.now(timezone.utc),
        status="running",
        trace=[],
    )
    db.add(agent_run)
    db.commit()
    db.refresh(agent_run)

    tool_dispatch = build_tool_dispatch(db, market, filings, ticker_symbol)
    trace = TraceRecorder()

    trigger_context = {"anomaly_id": anomaly_id} if anomaly_id is not None else None

    try:
        result = backend.run_analyst(ticker_symbol, trigger_context, tool_dispatch, trace)
    except Exception:
        agent_run.status = "failed"
        agent_run.completed_at = datetime.now(timezone.utc)
        agent_run.trace = trace.to_json()
        db.commit()
        raise

    agent_run.trace = trace.to_json()
    agent_run.status = "complete"
    agent_run.completed_at = datetime.now(timezone.utc)

    diff_from_prior = result.diff_from_prior
    if diff_from_prior is None:
        prior_brief = (
            db.query(Brief)
            .filter(Brief.ticker_id == ticker.id)
            .order_by(desc(Brief.created_at))
            .first()
        )
        diff_from_prior = _compute_diff_from_prior(prior_brief, result.thesis, result.confidence)

    brief = Brief(
        ticker_id=ticker.id,
        agent_run_id=agent_run.id,
        created_at=datetime.now(timezone.utc),
        thesis=result.thesis,
        confidence=result.confidence,
        summary=result.summary,
        evidence=result.evidence,
        diff_from_prior=diff_from_prior,
        suggested_action=result.suggested_action,
    )
    db.add(brief)
    db.commit()
    db.refresh(brief)

    agent_run.brief_id = brief.id
    db.commit()

    return brief
