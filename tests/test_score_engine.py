from openedge.models.score_engine import market_bias, opening_auction_risk, opportunity_score


def test_market_bias_bullish():
    snapshot = {
        "SPY": {"change": 0.5},
        "DIA": {"change": 0.4},
        "QQQ": {"change": 0.3},
    }
    assert market_bias(snapshot) == ("BULLISH", 65)


def test_market_bias_bearish():
    snapshot = {
        "SPY": {"change": -0.6},
        "DIA": {"change": -0.2},
        "QQQ": {"change": -0.4},
    }
    assert market_bias(snapshot) == ("BEARISH", 65)


def test_market_bias_neutral():
    snapshot = {
        "SPY": {"change": 0.2},
        "DIA": {"change": 0.1},
        "QQQ": {"change": -0.1},
    }
    assert market_bias(snapshot) == ("NEUTRAL", 55)


def test_opening_auction_risk_rules():
    snapshot = {
        "VIX": {"change": 6.0},
        "QQQ": {"change": 1.2},
    }
    assert opening_auction_risk(snapshot) == 7


def test_opportunity_score_rules():
    assert opportunity_score("NEUTRAL", 4) == 4
    assert opportunity_score("BULLISH", 4) == 7
    assert opportunity_score("BEARISH", 6) == 5
    assert opportunity_score("BULLISH", 8) == 3
