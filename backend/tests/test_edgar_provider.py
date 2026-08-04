import respx
import httpx
from providers.edgar_provider import EdgarProvider

_TICKERS_JSON = {
    "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
}


@respx.mock
def test_get_filings_parses_results():
    respx.get("https://www.sec.gov/files/company_tickers.json").mock(
        return_value=httpx.Response(200, json=_TICKERS_JSON)
    )
    respx.get(url__regex=r"https://efts\.sec\.gov/LATEST/search-index.*").mock(
        return_value=httpx.Response(200, json={"hits": {"hits": [
            {"_source": {"form": "10-Q", "file_date": "2026-07-15", "display_names": ["APPLE INC"]},
             "_id": "0000320193-26-000050:aapl-20260630.htm"},
        ]}})
    )
    provider = EdgarProvider(user_agent="Sentinel test@example.com")
    filings = provider.get_filings("AAPL", form_types=["10-Q"], limit=5)
    assert filings[0].form_type == "10-Q"
    assert filings[0].url.startswith("https://www.sec.gov/")


@respx.mock
def test_get_filings_uses_resolved_cik_for_url_not_agent_cik():
    # Regression for the "off-issuer CIK" bug: even though this hit's
    # _source carries no cik/ciks field at all (as in EDGAR's real
    # full-text search payloads, which frequently omit it), and even if
    # it did, the resolved ticker->CIK lookup should win over whatever a
    # filing-agent-submitted hit's own fields say - the Archives URL
    # must be built from Apple's real CIK (320193), not derived from the
    # accession-number-prefix fallback.
    respx.get("https://www.sec.gov/files/company_tickers.json").mock(
        return_value=httpx.Response(200, json=_TICKERS_JSON)
    )
    respx.get(url__regex=r"https://efts\.sec\.gov/LATEST/search-index.*").mock(
        return_value=httpx.Response(200, json={"hits": {"hits": [
            {"_source": {"form": "10-Q", "file_date": "2026-07-15", "display_names": ["APPLE INC"]},
             "_id": "1193125-26-000050:aapl-20260630.htm"},
        ]}})
    )
    provider = EdgarProvider(user_agent="Sentinel test@example.com")
    filings = provider.get_filings("AAPL", form_types=["10-Q"], limit=5)
    assert filings[0].url == (
        "https://www.sec.gov/Archives/edgar/data/320193/119312526000050/aapl-20260630.htm"
    )


@respx.mock
def test_get_filings_scopes_search_to_resolved_cik():
    respx.get("https://www.sec.gov/files/company_tickers.json").mock(
        return_value=httpx.Response(200, json=_TICKERS_JSON)
    )
    route = respx.get(url__regex=r"https://efts\.sec\.gov/LATEST/search-index.*").mock(
        return_value=httpx.Response(200, json={"hits": {"hits": []}})
    )
    provider = EdgarProvider(user_agent="Sentinel test@example.com")
    provider.get_filings("AAPL", form_types=["10-Q"], limit=5)

    sent = route.calls[0].request
    assert httpx.QueryParams(sent.url.query.decode())["ciks"] == "0000320193"


@respx.mock
def test_get_filings_degrades_gracefully_when_ticker_lookup_fails():
    respx.get("https://www.sec.gov/files/company_tickers.json").mock(
        return_value=httpx.Response(500)
    )
    route = respx.get(url__regex=r"https://efts\.sec\.gov/LATEST/search-index.*").mock(
        return_value=httpx.Response(200, json={"hits": {"hits": [
            {"_source": {"form": "10-Q", "file_date": "2026-07-15", "display_names": ["APPLE INC"]},
             "_id": "0000320193-26-000050:aapl-20260630.htm"},
        ]}})
    )
    provider = EdgarProvider(user_agent="Sentinel test@example.com")
    filings = provider.get_filings("AAPL", form_types=["10-Q"], limit=5)

    sent = route.calls[0].request
    assert "ciks" not in httpx.QueryParams(sent.url.query.decode())
    assert filings[0].url.startswith("https://www.sec.gov/")


@respx.mock
def test_get_filing_text_strips_html_and_truncates():
    respx.get("https://www.sec.gov/Archives/edgar/data/example.htm").mock(
        return_value=httpx.Response(200, text="<html><body><p>Revenue grew 12%.</p></body></html>")
    )
    provider = EdgarProvider(user_agent="Sentinel test@example.com")
    text = provider.get_filing_text("https://www.sec.gov/Archives/edgar/data/example.htm", max_chars=1000)
    assert "Revenue grew 12%" in text
    assert "<p>" not in text


@respx.mock
def test_get_filing_text_strips_script_and_style_content():
    respx.get("https://www.sec.gov/Archives/edgar/data/example2.htm").mock(
        return_value=httpx.Response(200, text=(
            "<html><head><style>.foo{color:red;font-size:12px}</style>"
            "<script>function boom(){alert('x');}</script></head>"
            "<body><p>Revenue grew 12%.</p></body></html>"
        ))
    )
    provider = EdgarProvider(user_agent="Sentinel test@example.com")
    text = provider.get_filing_text("https://www.sec.gov/Archives/edgar/data/example2.htm", max_chars=1000)
    assert "Revenue grew 12%" in text
    assert "color:red" not in text
    assert "alert" not in text
