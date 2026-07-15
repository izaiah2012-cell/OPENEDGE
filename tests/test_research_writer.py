from openedge.engines.research_writer import generate_research_summary


def test_generate_research_summary_returns_string():
    data = {
        "market_regime": "Risk On",
        "confidence": 65,
        "opening_auction_risk": 4,
        "opportunity_score": 7,
        "bias": "BULLISH",
        "leadership": {"Technology": {"score": 1.2, "status": "Strong"}},
        "macro_events": [{"time": "08:30 ET", "event": "CPI", "impact": "High"}],
        "macro_risk": "MEDIUM",
        "historical_match": {"date": "2024-07-01", "bias": "UP", "actual": "UP", "correct": 1},
        "historical_similarity": 82.4,
    }

    report = generate_research_summary(data)
    assert isinstance(report, str)


def test_generate_research_summary_has_expected_headings():
    report = generate_research_summary({
        "market_regime": "Neutral",
        "confidence": 55,
        "opening_auction_risk": 5,
        "opportunity_score": 4,
        "bias": "NEUTRAL",
        "leadership": {},
        "macro_events": [],
        "macro_risk": "LOW",
        "historical_match": {},
        "historical_similarity": 0.0,
    })

    assert "## Executive Summary" in report
    assert "## Market Regime" in report
    assert "## Sector Leadership" in report
    assert "## Macro Events" in report
    assert "## Historical Comparison" in report
    assert "## Research Conclusion" in report


def test_generate_research_summary_handles_missing_values_gracefully():
    report = generate_research_summary({})

    assert "N/A" in report
    assert "does not provide trade instruction" in report
