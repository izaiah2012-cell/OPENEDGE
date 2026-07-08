from openedge.engines.historical_analyzer import HistoricalAnalyzer


def test_historical_analyzer_best_match_and_confidence():
    analyzer = HistoricalAnalyzer(
        {
            "matches": [
                {
                    "rank": 1,
                    "date": "2026-06-12",
                    "similarity": 84.0,
                    "confidence_band": "Strong",
                    "actual": "UP",
                }
            ],
            "best_match": {"date": "2026-06-12", "similarity": 84.0, "confidence_band": "Strong"},
            "average_similarity": 84.0,
            "most_common_outcome": "UP",
            "message": "",
        }
    )

    assert analyzer.best_match()["date"] == "2026-06-12"
    assert analyzer.historical_confidence() == "Strong"
    assert analyzer.expected_outcome() == "UP"
    assert analyzer.rows()[0]["Date"] == "2026-06-12"


def test_historical_analyzer_handles_missing_data():
    analyzer = HistoricalAnalyzer({}, latest_signal={"actual": "DOWN"})

    assert analyzer.best_match() == {}
    assert analyzer.historical_confidence() == "Weak"
    assert analyzer.expected_outcome() == "DOWN"
