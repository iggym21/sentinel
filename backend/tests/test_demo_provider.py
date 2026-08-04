from providers.demo_provider import DemoProvider

def test_price_history_is_deterministic_and_shaped():
    p = DemoProvider()
    bars1 = p.get_price_history("AAPL", days=10)
    bars2 = p.get_price_history("AAPL", days=10)
    assert [b.close for b in bars1] == [b.close for b in bars2]
    assert len(bars1) == 10
    assert all(b.low <= b.close <= b.high for b in bars1)

def test_price_snapshot_consistent_with_history():
    p = DemoProvider()
    snap = p.get_price_snapshot("AAPL")
    history = p.get_price_history("AAPL", days=30)
    assert snap.price == history[-1].close
    assert snap.ticker == "AAPL"

def test_different_tickers_differ():
    p = DemoProvider()
    a = [b.close for b in p.get_price_history("AAPL", days=5)]
    b = [b.close for b in p.get_price_history("MSFT", days=5)]
    assert a != b

def test_recent_news_returns_items():
    p = DemoProvider()
    news = p.get_recent_news("AAPL", days=7)
    assert len(news) >= 1
    assert all(n.headline for n in news)
