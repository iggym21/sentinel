"""Dispatch registry for the Analyst's non-terminal tools.

`build_tool_dispatch` closes over the per-run context (db session,
market/filings providers, and the ticker under investigation) and
returns a name -> callable map that Task 10's agent loop can index
straight from a Claude tool_use block's `name`, passing its `input`
dict through.

`submit_brief` is deliberately excluded — it's the terminal action
that ends the agent loop (handled directly by the loop itself, not
dispatched as a data-fetching tool call), even though its schema still
lives alongside the others in `schemas.TOOL_SCHEMAS`.

The ticker each tool acts on is always the one this dispatch was built
for, not whatever the model happens to put in a given tool_use input's
`ticker` field — the model can only ever operate on the single ticker
this Analyst run was launched for, so any `ticker` key in a tool's
input is intentionally dropped in favor of the closed-over value.
"""

from __future__ import annotations

from typing import Callable

from sqlalchemy.orm import Session

from agents.tools.calculate_ratios import calculate_ratios
from agents.tools.get_filing_text import get_filing_text
from agents.tools.get_filings import get_filings
from agents.tools.get_price_history import get_price_history
from agents.tools.get_prior_briefs import get_prior_briefs
from agents.tools.get_recent_news import get_recent_news
from providers.base import FilingsProvider, MarketDataProvider


def _without_ticker(tool_input: dict) -> dict:
    return {k: v for k, v in tool_input.items() if k != "ticker"}


def build_tool_dispatch(
    db: Session,
    market: MarketDataProvider,
    filings: FilingsProvider,
    ticker: str,
) -> dict[str, Callable[[dict], dict]]:
    return {
        "get_filings": lambda tool_input: get_filings(
            filings, ticker, **_without_ticker(tool_input)
        ),
        "get_filing_text": lambda tool_input: get_filing_text(
            filings, **_without_ticker(tool_input)
        ),
        "get_recent_news": lambda tool_input: get_recent_news(
            market, ticker, **_without_ticker(tool_input)
        ),
        "get_price_history": lambda tool_input: get_price_history(
            market, ticker, **_without_ticker(tool_input)
        ),
        "calculate_ratios": lambda tool_input: calculate_ratios(market, ticker),
        "get_prior_briefs": lambda tool_input: get_prior_briefs(
            db, ticker, **_without_ticker(tool_input)
        ),
    }
