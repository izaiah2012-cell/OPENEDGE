from openedge.engines.macro_analyzer import MacroAnalyzer


def test_macro_analyzer_high_risk():
    analyzer = MacroAnalyzer(
        [
            {"time": "08:30 ET", "event": "CPI", "impact": "High"},
            {"time": "14:00 ET", "event": "FOMC", "impact": "High"},
        ]
    )

    assert analyzer.macro_risk() == "HIGH"
    assert len(analyzer.today_events()) == 2
    assert "high-impact" in analyzer.summary().lower()


def test_macro_analyzer_low_risk():
    analyzer = MacroAnalyzer([{"time": "10:00 ET", "event": "Survey", "impact": "Low"}])

    assert analyzer.macro_risk() in {"LOW", "MEDIUM"}
    assert analyzer.today_events()[0]["Event"] == "Survey"
