"""SEC EDGAR full-text search integration.

EdgarProvider implements FilingsProvider against SEC EDGAR's public,
key-free full-text search API:

  - GET https://www.sec.gov/files/company_tickers.json  -> ticker -> CIK
                                                             resolution
  - GET https://efts.sec.gov/LATEST/search-index         -> get_filings
  - GET {filing_url}                                     -> get_filing_text

SEC requires a descriptive `User-Agent` header on every request
(company/app name + contact) and will reject unidentified traffic, so
every request made by this provider - the ticker/CIK lookup, the
search API, and the filing document fetch - carries the
caller-supplied `user_agent`.

Ticker -> CIK resolution
--------------------------
EDGAR's full-text search `q` param is a free-text query over document
*content*, not an issuer filter: `q="AAPL"` matches any filing whose
text happens to contain "AAPL", including filings from unrelated
companies that merely mention Apple (e.g. as a customer). To make
`get_filings` actually issuer-scoped, this provider first resolves the
ticker to its CIK via SEC's free, key-free
`company_tickers.json` mapping, then passes that CIK to full-text
search via the `ciks` param - the same resolution EDGAR's own web UI
does under the hood when you search by ticker. The mapping is fetched
once per provider instance and cached (it's ~1000s of entries and
doesn't change intra-process).

If ticker resolution fails (network hiccup, SEC endpoint down, unknown
ticker), `get_filings` degrades gracefully to a content-only search
(no `ciks` scoping) rather than raising - callers may still get
useful, if noisier, results.

Archives URL construction
--------------------------
EDGAR full-text search hits don't return a ready-made document URL.
Each hit's `_id` has the form `"{accession}:{filename}"`, where
`accession` is the filing's SEC accession number (dashed,
`XXXXXXXXXX-YY-NNNNNN`, per the real API - though this provider also
tolerates an already-undashed value defensively). The Archives URL is:

    https://www.sec.gov/Archives/edgar/data/{cik}/{accession-no-dashes}/{filename}

`cik` here is the *issuer's* CIK, and is taken - in order of
preference - from: (1) the ticker's CIK as resolved above (most
reliable: a real EDGAR company-level CIK, not the filer/agent CIK
sometimes present on the hit itself), (2) `_source["ciks"]` /
`_source["cik"]` / `_source["cik_str"]` on the hit when ticker
resolution wasn't available, (3) as a last resort, the first 10
digits of the accession number - by SEC convention those digits are
the CIK of whoever *submitted* the filing, which is only the issuer's
own CIK when the issuer filed directly rather than through a filing
agent (Donnelley, Toppan Merrill, Broadridge, etc. all file under
their own CIKs on behalf of clients), so this fallback can be wrong
for agent-filed documents and is only used when nothing better is
available. Leading zeros are stripped in all cases, matching how
EDGAR's own Archives URLs are built (e.g. CIK 320193, not
0000320193).

Note: the `_id`-derived filename is whatever specific document the
full-text-search index matched inside the filing (frequently an XBRL
fragment like `R38.xml`, not the filing's primary human-readable
document), so `get_filing_text` on that URL may return exhibit/XBRL
content rather than the main filing prose.
"""

from __future__ import annotations

import html
import re
from typing import Any

import httpx

from providers.base import FilingRef

_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"

# Strip <script>/<style> elements *including their content* first - the
# general tag-strip regex below only removes tags, not the CSS/JS text
# between them, which real SEC filing HTML often front-loads in large
# inline <style> blocks and would otherwise pollute (and, combined with
# max_chars truncation, potentially crowd out) the extracted prose.
_SCRIPT_STYLE_RE = re.compile(r"<(script|style)\b[^>]*>.*?</\1>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


class EdgarProvider:
    """FilingsProvider backed by SEC EDGAR's full-text search API."""

    def __init__(self, user_agent: str) -> None:
        self._client = httpx.Client(
            headers={"User-Agent": user_agent},
            timeout=10.0,
        )
        # Lazily populated, cached ticker -> CIK (unpadded, as string) map.
        # None means "not fetched yet"; {} means "fetch was attempted and
        # failed", so we don't retry it on every call.
        self._ticker_to_cik: dict[str, str] | None = None

    def close(self) -> None:
        self._client.close()

    def get_filings(
        self, ticker: str, form_types: list[str] | None, limit: int
    ) -> list[FilingRef]:
        params: dict[str, str] = {"q": ticker}
        if form_types:
            params["forms"] = ",".join(form_types)

        resolved_cik = self._resolve_cik(ticker)
        if resolved_cik:
            # EDGAR's full-text search API expects zero-padded 10-digit
            # CIKs in the `ciks` param (comma-separated for multiple).
            params["ciks"] = resolved_cik.zfill(10)

        response = self._client.get(_SEARCH_URL, params=params)
        response.raise_for_status()
        data = response.json()

        # NOTE: this takes EDGAR's first page of hits as-is and slices to
        # `limit` client-side; it does not paginate via `from`/`size` if
        # `limit` exceeds EDGAR's default page size (10). Fine for the
        # small limits this provider is used with, but worth knowing.
        hits = (data.get("hits") or {}).get("hits") or []

        return [
            self._parse_hit(hit, ticker, resolved_cik)
            for hit in hits[:limit]
        ]

    def get_filing_text(self, filing_url: str, max_chars: int) -> str:
        response = self._client.get(filing_url)
        response.raise_for_status()

        without_script_style = _SCRIPT_STYLE_RE.sub(" ", response.text)
        without_tags = _TAG_RE.sub(" ", without_script_style)
        unescaped = html.unescape(without_tags)
        collapsed = _WHITESPACE_RE.sub(" ", unescaped).strip()

        return collapsed[:max_chars]

    def _resolve_cik(self, ticker: str) -> str | None:
        if self._ticker_to_cik is None:
            try:
                self._ticker_to_cik = self._fetch_ticker_map()
            except httpx.HTTPError:
                self._ticker_to_cik = {}

        return self._ticker_to_cik.get(ticker.upper())

    def _fetch_ticker_map(self) -> dict[str, str]:
        response = self._client.get(_TICKERS_URL)
        response.raise_for_status()
        data = response.json()

        mapping: dict[str, str] = {}
        for entry in data.values():
            entry_ticker = entry.get("ticker")
            cik = entry.get("cik_str")
            if entry_ticker and cik is not None:
                mapping[str(entry_ticker).upper()] = str(int(cik))

        return mapping

    def _parse_hit(
        self, hit: dict[str, Any], ticker: str, resolved_cik: str | None
    ) -> FilingRef:
        source = hit.get("_source") or {}
        display_names = source.get("display_names") or []

        return FilingRef(
            ticker=ticker,
            form_type=source.get("form", ""),
            filed_at=source.get("file_date", ""),
            url=self._build_archives_url(hit.get("_id", ""), source, resolved_cik),
            title=display_names[0] if display_names else ticker,
        )

    def _build_archives_url(
        self, doc_id: str, source: dict[str, Any], resolved_cik: str | None
    ) -> str:
        accession_raw, _, filename = doc_id.partition(":")
        accession_no_dashes = accession_raw.replace("-", "")

        if not accession_no_dashes or not filename:
            # Malformed/unexpected _id shape - fall back to the site root
            # rather than raising, so a single bad hit doesn't blow up
            # the whole get_filings call. (No logging here, so this
            # failure is silent to callers beyond the odd-looking URL -
            # acceptable for now given how rare a malformed _id is, but
            # worth a log line if this ever needs debugging.)
            return "https://www.sec.gov/"

        cik = resolved_cik or self._extract_cik(source, accession_no_dashes)

        return (
            f"https://www.sec.gov/Archives/edgar/data/{cik}/"
            f"{accession_no_dashes}/{filename}"
        )

    @staticmethod
    def _extract_cik(source: dict[str, Any], accession_no_dashes: str) -> str:
        """Best-effort issuer CIK from a single search hit's _source.

        Only used when ticker->CIK resolution (the preferred, reliable
        path - see module docstring) wasn't available. Prefers the
        plural `ciks` field real EDGAR responses actually use, then
        falls back to singular `cik`/`cik_str` variants, then finally to
        the accession-number-prefix heuristic - which is only correct
        for filings submitted under the issuer's own EDGAR account, not
        ones submitted via a filing agent.
        """
        ciks = source.get("ciks")
        cik: Any = None
        if isinstance(ciks, list) and ciks:
            cik = ciks[0]

        if cik is None:
            cik = source.get("cik") or source.get("cik_str")
            if isinstance(cik, list):
                cik = cik[0] if cik else None

        if cik is None and len(accession_no_dashes) >= 10:
            # Last resort: by SEC convention, the first 10 digits of the
            # accession number are the CIK of whoever *submitted* the
            # filing, which is only the issuer's own CIK for self-filed
            # documents (see module docstring caveat).
            cik = accession_no_dashes[:10]

        if cik is None:
            return ""

        try:
            return str(int(cik))
        except (TypeError, ValueError):
            return str(cik)
