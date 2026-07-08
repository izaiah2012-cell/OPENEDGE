import yfinance as yf

SECTOR_GROUPS = {
    "Technology": ["MSFT", "NVDA", "AAPL"],
    "Financials": ["JPM", "GS", "BAC"],
    "Industrials": ["CAT", "DE", "HON"],
    "Healthcare": ["UNH", "LLY", "JNJ"],
    "Consumer": ["AMZN", "COST", "WMT"],
    "Energy": ["XOM", "CVX"],
}


def _daily_pct_change(ticker):
    data = yf.Ticker(ticker).history(period="2d")
    if len(data) < 2:
        return 0.0

    close = data["Close"].iloc[-1]
    prev = data["Close"].iloc[-2]
    if prev == 0:
        return 0.0

    return ((close - prev) / prev) * 100


def _classify_sector(avg_change):
    if avg_change > 1.0:
        return "Strong"
    if avg_change < -1.0:
        return "Weak"
    return "Neutral"


def evaluate_sector_leadership():
    leadership = {}

    for sector, tickers in SECTOR_GROUPS.items():
        moves = []
        for ticker in tickers:
            try:
                moves.append(_daily_pct_change(ticker))
            except Exception:
                continue

        avg_change = sum(moves) / len(moves) if moves else 0.0
        leadership[sector] = {
            "score": round(avg_change, 2),
            "status": _classify_sector(avg_change),
        }

    return leadership
