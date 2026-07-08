from openedge.engines.intelligence import IntelligenceEngine


def _engine(**overrides):
    payload = {
        "market_snapshot": {
            "SPY": {"change": 0.8},
            "QQQ": {"change": 1.1},
            "DIA": {"change": 0.4},
            "VIX": {"change": -2.0},
        },
        "market_internals": {
            "SPY": {"price": 620.0, "daily_change_percent": 0.8, "direction": "UP"},
            "QQQ": {"price": 540.0, "daily_change_percent": 1.1, "direction": "UP"},
            "DIA": {"price": 445.0, "daily_change_percent": 0.4, "direction": "UP"},
            "VIX": {"price": 14.5, "daily_change_percent": -2.0, "direction": "DOWN"},
        },
        "leadership": {
            "Technology": {"status": "Strong"},
            "Financials": {"status": "Strong"},
            "Energy": {"status": "Neutral"},
        },
        "macro_events": [{"event": "CPI", "impact": "Medium"}],
        "historical_match": {
            "most_common_outcome": "UP",
            "best_match": {"confidence_band": "Strong"},
        },
        "latest_signal": {"actual": "UP"},
    }
    payload.update(overrides)
    return IntelligenceEngine(**payload)


def test_bullish_scenario_report():
    report = _engine().build_report()

    assert report["status"] == "READY"
    assert report["bias"] == "BULLISH"
    assert report["market_regime"] == "Risk On"
    assert report["opening_style"] == "Trend Open"
    assert report["confidence"] >= 65


def test_bearish_scenario_report():
    engine = _engine(
        market_snapshot={
            "SPY": {"change": -1.1},
            "QQQ": {"change": -1.6},
            "DIA": {"change": -0.8},
            "VIX": {"change": 5.2},
        },
        market_internals={
            "SPY": {"price": 600.0, "daily_change_percent": -1.1, "direction": "DOWN"},
            "QQQ": {"price": 520.0, "daily_change_percent": -1.6, "direction": "DOWN"},
            "DIA": {"price": 430.0, "daily_change_percent": -0.8, "direction": "DOWN"},
            "VIX": {"price": 18.2, "daily_change_percent": 5.0, "direction": "UP"},
        },
        leadership={
            "Technology": {"status": "Weak"},
            "Financials": {"status": "Weak"},
        },
        macro_events=[{"event": "Payrolls", "impact": "High"}],
        historical_match={"most_common_outcome": "DOWN", "best_match": {"confidence_band": "Moderate"}},
    )
    report = engine.build_report()

    assert report["bias"] == "BEARISH"
    assert report["market_regime"] == "Risk Off"
    assert report["risk_level"] == "HIGH"
    assert report["opening_style"] == "Defensive Open"


def test_neutral_scenario_report():
    engine = _engine(
        market_snapshot={
            "SPY": {"change": 0.04},
            "QQQ": {"change": -0.01},
            "DIA": {"change": 0.03},
            "VIX": {"change": 0.8},
        },
        market_internals={
            "SPY": {"price": 610.0, "daily_change_percent": 0.04, "direction": "UP"},
            "QQQ": {"price": 530.0, "daily_change_percent": -0.01, "direction": "DOWN"},
            "DIA": {"price": 438.0, "daily_change_percent": 0.03, "direction": "UP"},
            "VIX": {"price": 15.1, "daily_change_percent": 0.3, "direction": "UP"},
        },
        leadership={"Technology": {"status": "Neutral"}, "Financials": {"status": "Neutral"}},
        macro_events=[{"event": "Claims", "impact": "Low"}],
        historical_match={"most_common_outcome": "N/A", "best_match": {"confidence_band": "Weak"}},
        latest_signal={},
    )
    report = engine.build_report()

    assert report["bias"] == "NEUTRAL"
    assert report["market_regime"] in {"Balanced", "Risk Off"}
    assert report["opening_style"] in {"Neutral Open", "Defensive Open"}


def test_high_macro_risk():
    engine = _engine(
        macro_events=[
            {"event": "CPI", "impact": "High"},
            {"event": "FOMC", "impact": "High"},
        ]
    )
    report = engine.build_report()

    assert report["risk_level"] == "HIGH"
    assert any("macro" in item.lower() for item in report["key_risks"])


def test_low_macro_risk():
    engine = _engine(
        macro_events=[{"event": "Small Survey", "impact": "Low"}],
        market_internals={
            "SPY": {"price": 620.0, "daily_change_percent": 0.8, "direction": "UP"},
            "QQQ": {"price": 540.0, "daily_change_percent": 1.1, "direction": "UP"},
            "DIA": {"price": 445.0, "daily_change_percent": 0.4, "direction": "UP"},
            "VIX": {"price": 14.2, "daily_change_percent": -2.5, "direction": "DOWN"},
        },
        leadership={"Technology": {"status": "Strong"}, "Financials": {"status": "Strong"}},
    )
    report = engine.build_report()

    assert report["risk_level"] in {"LOW", "MEDIUM"}


def test_missing_historical_data():
    engine = _engine(historical_match={}, latest_signal={})
    report = engine.build_report()

    assert report["status"] == "READY"
    assert isinstance(report["summary"], str)
    assert len(report["summary"]) > 20
