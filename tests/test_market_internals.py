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
    assert set(result["SPY"].keys()) == {"price", "daily_change", "direction"}
    assert result["SPY"]["direction"] == "UP"


def test_get_market_internals_handles_provider_failure(monkeypatch):
    monkeypatch.setattr(market_internals.yf, "Ticker", lambda ticker: _TickerFailure())

    result = market_internals.get_market_internals()

    assert result["SPY"]["price"] is None
    assert result["SPY"]["daily_change"] is None
    assert result["SPY"]["direction"] == "N/A"
