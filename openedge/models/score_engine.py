def _safe_change(snapshot, symbol):
    values = snapshot.get(symbol, {})
    change = values.get("change")
    if change is None:
        return 0.0
    return float(change)


def market_bias(snapshot):
    avg_change = (
        _safe_change(snapshot, "SPY")
        + _safe_change(snapshot, "DIA")
        + _safe_change(snapshot, "QQQ")
    ) / 3

    if avg_change > 0.25:
        return ("BULLISH", 65)
    if avg_change < -0.25:
        return ("BEARISH", 65)
    return ("NEUTRAL", 55)


def opening_auction_risk(snapshot):
    score = 4

    vix_change = _safe_change(snapshot, "VIX")
    qqq_change = _safe_change(snapshot, "QQQ")

    if vix_change > 5:
        score += 2

    if abs(qqq_change) > 1:
        score += 1

    return min(score, 10)


def opportunity_score(bias, oar):
    if bias == "NEUTRAL":
        return 4

    if oar <= 4:
        return 7
    if oar <= 6:
        return 5
    return 3
