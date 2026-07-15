import pandas as pd

from openedge.engines import market_internals


class _TickerSuccess:
    def history(self, period="2d"):
        return pd.DataFrame({"Close": [100.0, 101.5]})


class _TickerFailure:
    def history(self, period="2d"):
        raise RuntimeError("provider unavailable")


def test_get_market_internals_returns_expected_shape(monkeypatch):
    monkeypatch.setattr(market_internals.yf, "Ticker", lambda ticker: _TickerSuccess())

    result = market_internals.get_market_internals()

    assert "SPY" in result
    assert set(result["SPY"].keys()) == {"price", "daily_change_percent", "direction"}
    assert result["SPY"]["direction"] == "UP"


def test_get_market_internals_handles_provider_failure(monkeypatch):
    monkeypatch.setattr(market_internals.yf, "Ticker", lambda ticker: _TickerFailure())

    result = market_internals.get_market_internals()

    assert result["SPY"]["price"] is None
    assert result["SPY"]["daily_change_percent"] is None
    assert result["SPY"]["direction"] == "N/A"


def test_summarize_market_internals_returns_text():
    internals = {
        "SPY": {"price": 615.2, "daily_change_percent": 0.42, "direction": "UP"},
        "QQQ": {"price": 532.1, "daily_change_percent": -0.15, "direction": "DOWN"},
        "VIX": {"price": 14.8, "daily_change_percent": 0.00, "direction": "UP"},
    }

    summary = market_internals.summarize_market_internals(internals)

    assert isinstance(summary, str)
    assert len(summary.split(".")) >= 3
