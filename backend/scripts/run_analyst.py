"""Manual CLI runner for the Analyst orchestration service.

Usage:

    cd backend && source venv/bin/activate
    python scripts/run_analyst.py AAPL

Opens a real DB session (`SessionLocal`), builds a live market-data
provider (`AlpacaProvider` if `settings.alpaca_api_key` is configured,
else `DemoProvider` — same "prefer real, fall back to the free/offline
option" pattern `backend_factory.py` uses for the reasoning backend)
and a real `EdgarProvider` for filings (EDGAR is free/key-free), runs
`run_analyst_for_ticker`, and pretty-prints the resulting `Brief` plus
the number of steps recorded in its `AgentRun`'s reasoning trace.
"""

from __future__ import annotations

import sys

from database import SessionLocal
from models.agent_run import AgentRun
from providers.factory import build_providers
from services.analyst_service import run_analyst_for_ticker


def main(ticker_symbol: str) -> None:
    db = SessionLocal()

    try:
        with build_providers() as (market, filings):
            brief = run_analyst_for_ticker(db, ticker_symbol, market, filings)

        run = db.query(AgentRun).filter_by(id=brief.agent_run_id).one()

        thesis = getattr(brief.thesis, "value", brief.thesis)
        suggested_action = getattr(brief.suggested_action, "value", brief.suggested_action)

        print(f"\n=== Analyst Brief: {ticker_symbol} ===")
        print(f"Thesis:     {thesis}")
        print(f"Confidence: {brief.confidence}/5")
        print(f"Summary:    {brief.summary}")
        if suggested_action:
            print(f"Suggested action: {suggested_action}")
        if brief.diff_from_prior:
            print(f"Diff from prior: {brief.diff_from_prior}")
        print("\nEvidence:")
        for item in brief.evidence:
            claim = item.get("claim")
            source_tool = item.get("source_tool")
            source_ref = item.get("source_ref")
            ref_suffix = f" ({source_ref})" if source_ref else ""
            print(f"  - [{source_tool}] {claim}{ref_suffix}")

        print(f"\nTrace steps recorded: {len(run.trace)}")
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts/run_analyst.py <TICKER>")
        sys.exit(1)
    main(sys.argv[1].upper())
