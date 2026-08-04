"""SEC EDGAR full-text search integration.

EdgarProvider implements FilingsProvider against SEC EDGAR's public,
key-free full-text search API:

  - GET https://efts.sec.gov/LATEST/search-index  -> get_filings
  - GET {filing_url}                               -> get_filing_text

SEC requires a descriptive `User-Agent` header on every request
(company/app name + contact) and will reject unidentified traffic, so
every request made by this provider - both the search API and the
filing document fetch - carries the caller-supplied `user_agent`.

Archives URL construction
--------------------------
EDGAR full-text search hits don't return a ready-made document URL.
Each hit's `_id` has the form `"{accession}:{filename}"`, where
`accession` is the filing's SEC accession number (dashed,
`XXXXXXXXXX-YY-NNNNNN`, per the real API - though this provider also
tolerates an already-undashed value defensively). The Archives URL is:

    https://www.sec.gov/Archives/edgar/data/{cik}/{accession-no-dashes}/{filename}

`cik` is the filer's CIK. Real `_source` payloads usually carry it
directly (as `cik` or `cik_str`, sometimes as a list of related
CIKs - the first is used). When it's absent, this provider falls back
to the first 10 digits of the accession number: by SEC convention
those digits *are* the CIK of whoever submitted the filing, which for
a company's own filings is the company's own CIK. Either way the
leading zeros are stripped, matching how EDGAR's own Archives URLs are
built (e.g. CIK 320193, not 0000320193).
"""

from __future__ import annotations

import html
import re
from typing import Any

import httpx

from providers.base import FilingRef

_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"

_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


class EdgarProvider:
    """FilingsProvider backed by SEC EDGAR's full-text search API."""

    def __init__(self, user_agent: str) -> None:
        self._client = httpx.Client(
            headers={"User-Agent": user_agent},
            timeout=10.0,
        )

    def close(self) -> None:
        self._client.close()

    def get_filings(
        self, ticker: str, form_types: list[str] | None, limit: int
    ) -> list[FilingRef]:
        params: dict[str, str] = {"q": ticker}
        if form_types:
            params["forms"] = ",".join(form_types)

        response = self._client.get(_SEARCH_URL, params=params)
        response.raise_for_status()
        data = response.json()

        hits = (data.get("hits") or {}).get("hits") or []

        return [
            self._parse_hit(hit, ticker)
            for hit in hits[:limit]
        ]

    def get_filing_text(self, filing_url: str, max_chars: int) -> str:
        response = self._client.get(filing_url)
        response.raise_for_status()

        without_tags = _TAG_RE.sub(" ", response.text)
        unescaped = html.unescape(without_tags)
        collapsed = _WHITESPACE_RE.sub(" ", unescaped).strip()

        return collapsed[:max_chars]

    def _parse_hit(self, hit: dict[str, Any], ticker: str) -> FilingRef:
        source = hit.get("_source") or {}
        display_names = source.get("display_names") or []

        return FilingRef(
            ticker=ticker,
            form_type=source.get("form", ""),
            filed_at=source.get("file_date", ""),
            url=self._build_archives_url(hit.get("_id", ""), source),
            title=display_names[0] if display_names else ticker,
        )

    def _build_archives_url(self, doc_id: str, source: dict[str, Any]) -> str:
        accession_raw, _, filename = doc_id.partition(":")
        accession_no_dashes = accession_raw.replace("-", "")

        if not accession_no_dashes or not filename:
            # Malformed/unexpected _id shape - fall back to the site root
            # rather than raising, so a single bad hit doesn't blow up
            # the whole get_filings call.
            return "https://www.sec.gov/"

        cik = self._extract_cik(source, accession_no_dashes)

        return (
            f"https://www.sec.gov/Archives/edgar/data/{cik}/"
            f"{accession_no_dashes}/{filename}"
        )

    @staticmethod
    def _extract_cik(source: dict[str, Any], accession_no_dashes: str) -> str:
        cik = source.get("cik") or source.get("cik_str")
        if isinstance(cik, list):
            cik = cik[0] if cik else None

        if cik is None and len(accession_no_dashes) >= 10:
            # By SEC convention, the first 10 digits of the accession
            # number are the submitter's CIK.
            cik = accession_no_dashes[:10]

        if cik is None:
            return ""

        try:
            return str(int(cik))
        except (TypeError, ValueError):
            return str(cik)
