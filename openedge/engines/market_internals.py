from __future__ import annotations

import yfinance as yf

INTERNALS_TICKERS = {
    "SPY": "SPY",
    "QQQ": "QQQ",
    "DIA": "DIA",
    "VIX": "^VIX",
    "US10Y": "^TNX",
    "DXY": "DX-Y.NYB",
    "Gold": "GC=F",
    "Oil": "CL=F",
    "Bitcoin": "BTC-USD",
    "IWM": "IWM",
}


def _direction_from_change(change):
    if change is None:
        return "N/A"
    if change >= 0:
        return "UP"
    if change < 0:
        return "DOWN"
    return "UP"


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
                "daily_change_percent": round(change, 2),
                "direction": _direction_from_change(change),
            }
        except Exception:
            internals[name] = {
                "price": None,
                "daily_change_percent": None,
                "direction": "N/A",
            }

    return internals


def summarize_market_internals(internals):
    """Build a concise 2-3 sentence overnight market internals narrative."""
    valid_changes = []
    up_count = 0
    down_count = 0

    for values in internals.values():
        change = values.get("daily_change_percent")
        direction = values.get("direction")
        if change is not None:
            valid_changes.append(float(change))
        if direction == "UP":
            up_count += 1
        elif direction == "DOWN":
            down_count += 1

    total = len(internals)
    unavailable = total - (up_count + down_count)

    if not valid_changes:
        return (
            "Overnight internals are currently mixed with incomplete live pricing across key assets. "
            "Directional conviction is limited until additional feeds populate."
        )

    avg_move = sum(valid_changes) / len(valid_changes)
    if avg_move > 0.15:
        tone = "risk appetite leaning constructive"
    elif avg_move < -0.15:
        tone = "a mild risk-off tone"
    else:
        tone = "a balanced and range-bound tone"

    summary = (
        f"Overnight internals show {up_count} assets up and {down_count} down, "
        f"with {unavailable} temporarily unavailable. "
        f"The average move across available assets is {avg_move:+.2f}%, suggesting {tone}. "
        "Cross-asset direction should be monitored alongside early U.S. cash-session participation for confirmation."
    )
    return summary
