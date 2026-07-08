from __future__ import annotations

import yfinance as yf

INTERNALS_TICKERS = {
    "SPY": "SPY",
    "DIA": "DIA",
    "QQQ": "QQQ",
    "VIX": "^VIX",
    "US10Y": "^TNX",
    "DXY": "DX-Y.NYB",
    "Gold": "GC=F",
    "Oil": "CL=F",
    "Bitcoin": "BTC-USD",
    "Russell 2000": "^RUT",
}


def _direction_from_change(change):
    if change is None:
        return "N/A"
    if change > 0:
        return "UP"
    if change < 0:
        return "DOWN"
    return "FLAT"


def get_market_internals():
    """Return a multi-asset market internals map for dashboard rendering."""
    internals = {}

    for name, ticker in INTERNALS_TICKERS.items():
        try:
            data = yf.Ticker(ticker).history(period="2d")

            if data.empty or len(data.index) < 2:
                raise ValueError("Insufficient data")

            close = float(data["Close"].iloc[-1])
            prev = float(data["Close"].iloc[-2])
            change = ((close - prev) / prev) * 100 if prev != 0 else 0.0

            internals[name] = {
                "price": round(close, 2),
                "daily_change": round(change, 2),
                "direction": _direction_from_change(change),
            }
        except Exception:
            internals[name] = {
                "price": None,
                "daily_change": None,
                "direction": "N/A",
            }

    return internals
