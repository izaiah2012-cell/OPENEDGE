from openedge.engines.market_analyzer import MarketAnalyzer


def _analyzer(**overrides):
    payload = {
        "market_snapshot": {
            "SPY": {"change": 0.8},
            "QQQ": {"change": 1.0},
            "DIA": {"change": 0.4},
            "VIX": {"change": -1.8},
        },
        "market_internals": {
            "VIX": {"direction": "DOWN"},
        },
        "leadership": {
            "Technology": {"status": "Strong"},
            "Financials": {"status": "Strong"},
        },
        "macro_events": [{"event": "CPI", "impact": "Medium"}],
        "historical_matches": {"best_match": {"confidence_band": "Strong"}},
    }
    payload.update(overrides)
    return MarketAnalyzer(**payload)


def test_market_analyzer_bullish_path():
    analyzer = _analyzer()

    assert analyzer.bias() == "BULLISH"
    assert analyzer.market_regime() == "Risk On"
    assert analyzer.opening_style() == "Trend Open"


def test_market_analyzer_bearish_path():
    analyzer = _analyzer(
        market_snapshot={
            "SPY": {"change": -1.1},
            "QQQ": {"change": -1.4},
            "DIA": {"change": -0.7},
            "VIX": {"change": 5.5},
        },
        market_internals={"VIX": {"direction": "UP"}},
        leadership={"Technology": {"status": "Weak"}, "Financials": {"status": "Weak"}},
        macro_events=[{"event": "FOMC", "impact": "High"}],
    )

    assert analyzer.bias() == "BEARISH"
    assert analyzer.market_regime() == "Risk Off"
    assert analyzer.risk_level() == "HIGH"
    assert analyzer.opening_style() == "Defensive Open"


def test_market_analyzer_neutral_bias_possible():
    analyzer = _analyzer(
        market_snapshot={
            "SPY": {"change": 0.02},
            "QQQ": {"change": 0.01},
            "DIA": {"change": -0.01},
            "VIX": {"change": 0.1},
        },
    )

    assert analyzer.bias() == "NEUTRAL"
