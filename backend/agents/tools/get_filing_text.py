"""Analyst tool: get_filing_text.

Thin adapter from FilingsProvider.get_filing_text's raw string return
to a plain, JSON-serializable dict (a bare string would already be
JSON-serializable, but wrapping it keeps the tool_result shape
consistent with the other tools and echoes back which URL it fetched).
"""

from __future__ import annotations

from providers.base import FilingsProvider


def get_filing_text(
    filings: FilingsProvider, filing_url: str, max_chars: int = 8000
) -> dict:
    text = filings.get_filing_text(filing_url, max_chars)
    return {
        "filing_url": filing_url,
        "text": text,
    }
