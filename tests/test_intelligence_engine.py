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
            "Technology": {"status": "Strong", "score": 1.5},
            "Financials": {"status": "Strong", "score": 0.9},
            "Energy": {"status": "Neutral", "score": 0.1},
        },
        "macro_events": [{"time": "08:30 ET", "event": "CPI", "impact": "Medium"}],
        "historical_matches": {
            "matches": [
                {
                    "rank": 1,
                    "date": "2026-06-12",
                    "similarity": 81.2,
                    "confidence_band": "Strong",
                    "actual": "UP",
                }
            ],
            "most_common_outcome": "UP",
            "best_match": {"date": "2026-06-12", "similarity": 81.2, "confidence_band": "Strong"},
            "average_similarity": 81.2,
        },
        "latest_signal": {"actual": "UP"},
    }
    payload.update(overrides)
    return IntelligenceEngine(**payload)


def test_build_report_contains_modular_sections():
    report = _engine().build_report()

    assert report["status"] == "READY"
    assert set(report.keys()) >= {"status", "market", "macro", "leadership", "historical", "summary"}


def test_bullish_market_report():
    report = _engine().build_report()

    assert report["market"]["bias"] == "BULLISH"
    assert report["market"]["market_regime"] == "Risk On"
    assert report["market"]["opening_style"] == "Trend Open"
    assert report["market"]["confidence"] >= 65


def test_bearish_market_report():
    report = _engine(
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
            "Technology": {"status": "Weak", "score": -1.5},
            "Financials": {"status": "Weak", "score": -0.9},
        },
        macro_events=[{"event": "Payrolls", "impact": "High"}],
        historical_matches={"most_common_outcome": "DOWN", "best_match": {"confidence_band": "Moderate"}},
    ).build_report()

    assert report["market"]["bias"] == "BEARISH"
    assert report["market"]["market_regime"] == "Risk Off"
    assert report["market"]["risk_level"] == "HIGH"
    assert report["macro"]["macro_risk"] == "MEDIUM" or report["macro"]["macro_risk"] == "HIGH"


def test_neutral_market_report():
    report = _engine(
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
        leadership={"Technology": {"status": "Neutral", "score": 0.0}},
        macro_events=[{"event": "Claims", "impact": "Low"}],
        historical_matches={"most_common_outcome": "N/A", "best_match": {"confidence_band": "Weak"}},
        latest_signal={},
    ).build_report()

    assert report["market"]["bias"] == "NEUTRAL"
    assert report["market"]["market_regime"] in {"Balanced", "Risk Off"}


def test_missing_historical_data_is_safe():
    report = _engine(historical_matches={}, latest_signal={}).build_report()

    assert report["status"] == "READY"
    assert isinstance(report["summary"]["executive_summary"], str)
    assert len(report["summary"]["executive_summary"]) > 20


def test_legacy_historical_match_constructor_remains_supported():
    report = _engine(
        historical_matches=None,
        historical_match={
            "most_common_outcome": "DOWN",
            "best_match": {"confidence_band": "Moderate"},
        },
    ).build_report()

    assert report["historical"]["most_common_outcome"] == "DOWN"
    assert report["historical"]["best_match"]["confidence_band"] == "Moderate"
