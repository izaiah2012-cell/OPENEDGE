import pandas as pd

from openedge.models import leadership_engine


class FakeTicker:
    def __init__(self, ticker, closes):
        self.ticker = ticker
        self._closes = closes

    def history(self, period="2d"):
        return pd.DataFrame({"Close": self._closes})


def test_evaluate_sector_leadership_classification(monkeypatch):
    closes = {
        "MSFT": [100, 103],
        "NVDA": [100, 104],
        "AAPL": [100, 102],
        "JPM": [100, 100.5],
        "GS": [100, 99.7],
        "BAC": [100, 100.1],
        "CAT": [100, 98],
        "DE": [100, 98.5],
        "HON": [100, 99],
        "UNH": [100, 100],
        "LLY": [100, 100.5],
        "JNJ": [100, 99.9],
        "AMZN": [100, 100.6],
        "COST": [100, 100.4],
        "WMT": [100, 100.2],
        "XOM": [100, 98],
        "CVX": [100, 98.2],
    }

    monkeypatch.setattr(
        leadership_engine.yf,
        "Ticker",
        lambda ticker: FakeTicker(ticker, closes[ticker]),
    )

    result = leadership_engine.evaluate_sector_leadership()

    assert result["Technology"]["status"] == "Strong"
    assert result["Financials"]["status"] == "Neutral"
    assert result["Industrials"]["status"] == "Weak"
    assert result["Energy"]["status"] == "Weak"
    assert isinstance(result["Technology"]["score"], float)
