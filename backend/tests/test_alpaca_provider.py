import respx
import httpx
from providers.alpaca_provider import AlpacaProvider


@respx.mock
def test_get_price_history_parses_bars():
    respx.get("https://data.alpaca.markets/v2/stocks/AAPL/bars").mock(
        return_value=httpx.Response(200, json={"bars": [
            {"t": "2026-08-01T00:00:00Z", "o": 190.1, "h": 192.0, "l": 189.5, "c": 191.2, "v": 1000000},
        ]})
    )
    provider = AlpacaProvider(api_key="k", secret_key="s", base_url="https://data.alpaca.markets")
    bars = provider.get_price_history("AAPL", days=1)
    assert bars[0].close == 191.2
    assert bars[0].volume == 1000000


@respx.mock
def test_get_recent_news_parses_articles():
    respx.get("https://data.alpaca.markets/v1beta1/news").mock(
        return_value=httpx.Response(200, json={"news": [
            {"headline": "AAPL beats estimates", "summary": "...", "created_at": "2026-08-01T12:00:00Z", "source": "benzinga"},
        ]})
    )
    provider = AlpacaProvider(api_key="k", secret_key="s", base_url="https://data.alpaca.markets")
    news = provider.get_recent_news("AAPL", days=7)
    assert news[0].headline == "AAPL beats estimates"


@respx.mock
def test_get_price_history_sends_auth_headers():
    route = respx.get("https://data.alpaca.markets/v2/stocks/AAPL/bars").mock(
        return_value=httpx.Response(200, json={"bars": []})
    )
    provider = AlpacaProvider(api_key="my-key", secret_key="my-secret", base_url="https://data.alpaca.markets")
    provider.get_price_history("AAPL", days=1)
    sent = route.calls[0].request
    assert sent.headers["APCA-API-KEY-ID"] == "my-key"
    assert sent.headers["APCA-API-SECRET-KEY"] == "my-secret"


@respx.mock
def test_get_price_history_raises_on_http_error():
    respx.get("https://data.alpaca.markets/v2/stocks/AAPL/bars").mock(
        return_value=httpx.Response(500, json={"message": "boom"})
    )
    provider = AlpacaProvider(api_key="k", secret_key="s", base_url="https://data.alpaca.markets")
    try:
        provider.get_price_history("AAPL", days=1)
        assert False, "expected an HTTPStatusError"
    except httpx.HTTPStatusError:
        pass


@respx.mock
def test_get_price_snapshot_derives_change_and_avg_volume():
    respx.get("https://data.alpaca.markets/v2/stocks/AAPL/snapshot").mock(
        return_value=httpx.Response(200, json={
            "symbol": "AAPL",
            "latestTrade": {"t": "2026-08-01T20:00:00Z", "p": 191.2, "s": 100},
            "dailyBar": {"t": "2026-08-01T00:00:00Z", "o": 190.1, "h": 192.0, "l": 189.5, "c": 191.2, "v": 1000000},
        })
    )
    respx.get("https://data.alpaca.markets/v2/stocks/AAPL/bars").mock(
        return_value=httpx.Response(200, json={"bars": [
            {"t": "2026-07-31T00:00:00Z", "o": 185.0, "h": 186.0, "l": 184.0, "c": 185.0, "v": 900000},
            {"t": "2026-08-01T00:00:00Z", "o": 190.1, "h": 192.0, "l": 189.5, "c": 191.2, "v": 1000000},
        ]})
    )
    provider = AlpacaProvider(api_key="k", secret_key="s", base_url="https://data.alpaca.markets")
    snap = provider.get_price_snapshot("AAPL")
    assert snap.ticker == "AAPL"
    assert snap.price == 191.2
    assert snap.volume == 1000000
    assert round(snap.day_change_pct, 4) == round(((191.2 - 185.0) / 185.0) * 100, 4)
    assert snap.avg_volume_20d == (900000 + 1000000) / 2
