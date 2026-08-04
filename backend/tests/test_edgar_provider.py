import respx
import httpx
from providers.edgar_provider import EdgarProvider

@respx.mock
def test_get_filings_parses_results():
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
def test_get_filing_text_strips_html_and_truncates():
    respx.get("https://www.sec.gov/Archives/edgar/data/example.htm").mock(
        return_value=httpx.Response(200, text="<html><body><p>Revenue grew 12%.</p></body></html>")
    )
    provider = EdgarProvider(user_agent="Sentinel test@example.com")
    text = provider.get_filing_text("https://www.sec.gov/Archives/edgar/data/example.htm", max_chars=1000)
    assert "Revenue grew 12%" in text
    assert "<p>" not in text
