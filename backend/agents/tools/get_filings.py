"""Analyst tool: get_filings.

Thin adapter from FilingsProvider.get_filings's list[FilingRef] to a
list of plain, JSON-serializable dicts.
"""

from __future__ import annotations

from providers.base import FilingsProvider


def get_filings(
    filings: FilingsProvider,
    ticker: str,
    form_types: list[str] | None = None,
    limit: int = 5,
) -> list[dict]:
    refs = filings.get_filings(ticker, form_types, limit)
    return [
        {
            "ticker": ref.ticker,
            "form_type": ref.form_type,
            "filed_at": ref.filed_at,
            "url": ref.url,
            "title": ref.title,
        }
        for ref in refs
    ]
