from openedge.engines.intelligence import build_openedge_intelligence


def _sample_payload(**overrides):
    payload = {
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
        "macro_risk": "MEDIUM",
        "historical_result": {
            "most_common_outcome": "UP",
            "best_match": {"confidence_band": "Strong"},
        },
        "bias": "BULLISH",
        "confidence": 72,
        "opening_auction_risk": 4,
        "opportunity_score": 7,
    }
    payload.update(overrides)
    return payload


def test_intelligence_engine_bullish_scenario():
    result = build_openedge_intelligence(**_sample_payload())

    assert result["market_regime"] == "Risk On"
    assert result["risk_level"] in {"LOW", "MEDIUM"}
    assert result["opening_style"] == "Trend Open"
    assert result["highest_probability"] == "UP"
    assert set(result.keys()) == {
        "market_regime",
        "risk_level",
        "confidence",
        "opening_style",
        "highest_probability",
        "key_risks",
        "strengths",
        "weaknesses",
        "focus_for_today",
        "summary",
    }


def test_intelligence_engine_bearish_scenario():
    payload = _sample_payload(
        market_internals={
            "SPY": {"price": 600.0, "daily_change_percent": -1.2, "direction": "DOWN"},
            "QQQ": {"price": 520.0, "daily_change_percent": -1.8, "direction": "DOWN"},
            "DIA": {"price": 430.0, "daily_change_percent": -0.9, "direction": "DOWN"},
            "VIX": {"price": 18.2, "daily_change_percent": 5.0, "direction": "UP"},
        },
        leadership={
            "Technology": {"status": "Weak"},
            "Financials": {"status": "Weak"},
            "Energy": {"status": "Neutral"},
        },
        macro_events=[{"event": "Payrolls", "impact": "High"}],
        macro_risk="HIGH",
        historical_result={
            "most_common_outcome": "DOWN",
            "best_match": {"confidence_band": "Moderate"},
        },
        bias="BEARISH",
        confidence=60,
        opening_auction_risk=8,
        opportunity_score=3,
    )

    result = build_openedge_intelligence(**payload)

    assert result["market_regime"] == "Risk Off"
    assert result["risk_level"] == "HIGH"
    assert result["opening_style"] == "Defensive Open"
    assert result["highest_probability"] == "DOWN"
    assert any("macro" in risk.lower() or "risk" in risk.lower() for risk in result["key_risks"])


def test_intelligence_engine_neutral_scenario():
    payload = _sample_payload(
        market_internals={
            "SPY": {"price": 610.0, "daily_change_percent": 0.0, "direction": "UP"},
            "QQQ": {"price": 530.0, "daily_change_percent": 0.05, "direction": "UP"},
            "DIA": {"price": 438.0, "daily_change_percent": -0.04, "direction": "DOWN"},
            "VIX": {"price": 15.0, "daily_change_percent": 0.3, "direction": "UP"},
        },
        leadership={
            "Technology": {"status": "Neutral"},
            "Financials": {"status": "Neutral"},
        },
        macro_events=[{"event": "Jobless Claims", "impact": "Low"}],
        macro_risk="LOW",
        historical_result={
            "most_common_outcome": "N/A",
            "best_match": {"confidence_band": "Weak"},
        },
        bias="NEUTRAL",
        confidence=55,
        opening_auction_risk=5,
        opportunity_score=4,
    )

    result = build_openedge_intelligence(**payload)

    assert result["market_regime"] in {"Balanced", "Risk Off", "Risk On"}
    assert result["opening_style"] in {"Neutral Open", "Defensive Open", "Trend Open"}
    assert result["highest_probability"] == "NEUTRAL"
    assert isinstance(result["summary"], str)
    assert len(result["summary"]) > 20
