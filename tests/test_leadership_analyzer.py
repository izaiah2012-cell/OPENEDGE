from openedge.engines.leadership_analyzer import LeadershipAnalyzer


def test_leadership_analyzer_finds_strongest_and_weakest():
    analyzer = LeadershipAnalyzer(
        {
            "Technology": {"status": "Strong", "score": 1.8},
            "Financials": {"status": "Neutral", "score": 0.2},
            "Energy": {"status": "Weak", "score": -1.2},
        }
    )

    strongest = analyzer.strongest_sector()
    weakest = analyzer.weakest_sector()

    assert strongest["sector"] == "Technology"
    assert weakest["sector"] == "Energy"
    assert "Leadership is led by" in analyzer.sector_summary()


def test_leadership_analyzer_handles_empty_input():
    analyzer = LeadershipAnalyzer({})

    assert analyzer.strongest_sector()["sector"] == "N/A"
    assert analyzer.weakest_sector()["sector"] == "N/A"
