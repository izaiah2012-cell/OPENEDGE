import yfinance as yf

TICKERS = {
    "SPY": "SPY",
    "DIA": "DIA",
    "QQQ": "QQQ",
    "VIX": "^VIX",
}

def get_market_snapshot():
    snapshot = {}

    for name, ticker in TICKERS.items():
        try:
            data = yf.Ticker(ticker).history(period="2d")

            close = data["Close"].iloc[-1]
            prev = data["Close"].iloc[-2]

            change = ((close - prev) / prev) * 100

            snapshot[name] = {
                "price": round(close, 2),
                "change": round(change, 2)
            }

        except Exception:
            snapshot[name] = {
                "price": None,
                "change": None
            }

    return snapshot