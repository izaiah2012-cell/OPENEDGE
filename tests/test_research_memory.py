from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from openedge.research import ResearchDay, ResearchGrader, ResearchJournal, ResearchReviewer, ResearchStatistics


def _sample_report() -> dict:
    return {
        "Date": "2026-07-15",
        "Timestamp": "2026-07-15T13:30:00+00:00",
        "Bias": "BULLISH",
        "Confidence": 73,
        "Market Regime": "Risk On",
        "Opportunity Score": 6,
        "Historical Match": {
            "best_match": {"date": "2026-06-10", "similarity": 88.2},
            "average_similarity": 84.1,
        },
        "Raw Engine Report": {
            "market": {
                "opening_risk": 5,
                "bias": "BULLISH",
                "confidence": 73,
                "market_regime": "Risk On",
            },
            "summary": {
                "research_conclusion": "Constructive trend environment.",
                "todays_focus": "Watch breadth confirmation.",
            },
        },
        "Research Conclusion": "Constructive trend environment.",
    }


def test_research_day_from_report_maps_fields():
    day = ResearchDay.from_report(_sample_report(), refresh_count=2)

    assert day.date == "2026-07-15"
    assert day.morning_bias == "BULLISH"
    assert day.morning_confidence == 73
    assert day.morning_regime == "Risk On"
    assert day.opening_auction_risk == 5
    assert day.opportunity_score == 6
    assert day.historical_match == "2026-06-10"
    assert day.similarity == 88.2
    assert day.refresh_count == 2


def test_research_journal_append_search_and_export(tmp_path: Path):
    journal = ResearchJournal(tmp_path)
    day = ResearchDay.from_report(_sample_report(), refresh_count=1)
    day.grade = "B"
    day.research_score = 82.0
    day.comments = "Good alignment"

    journal.append_day(day)

    loaded = journal.load_days()
    assert not loaded.empty
    assert "grade" in loaded.columns

    searched = journal.search(query="alignment", grade="B", bias="BULLISH")
    assert len(searched) == 1

    csv_path = journal.export_csv()
    json_path = journal.export_json()
    assert csv_path.exists()
    assert json_path.exists()

    exported = json.loads(json_path.read_text(encoding="utf-8"))
    assert isinstance(exported, list)
    assert exported[0]["date"] == "2026-07-15"


def test_research_grader_scores_day():
    day = ResearchDay.from_report(_sample_report(), refresh_count=1)
    day.morning_correct = True
    day.close_correct = False

    result = ResearchGrader().grade_day(day)
    assert 0.0 <= result.score <= 100.0
    assert result.grade in {"A", "B", "C", "D", "F"}
    assert 1 <= result.stars <= 5


def test_research_statistics_summary_handles_frame():
    frame = pd.DataFrame(
        [
            {
                "date": "2026-07-14",
                "research_score": 80,
                "similarity": 85,
                "morning_confidence": 70,
                "grade": "B",
            },
            {
                "date": "2026-07-15",
                "research_score": 90,
                "similarity": 88,
                "morning_confidence": 74,
                "grade": "A",
            },
        ]
    )
    stats = ResearchStatistics(frame)
    summary = stats.summary()

    assert summary["total_days"] == 2
    assert summary["average_score"] == 85.0
    assert summary["average_similarity"] == 86.5
    assert summary["average_confidence"] == 72.0


def test_reviewer_first_trading_day_logic():
    # Tuesday and first calendar day
    assert ResearchReviewer._is_first_trading_day(date(2026, 9, 1)) is True
    # Weekend cannot be first trading day
    assert ResearchReviewer._is_first_trading_day(date(2026, 8, 1)) is False


def test_research_pages_importable():
    import openedge.dashboard.app as app_module
    import openedge.dashboard.pages.operations as operations_page
    import openedge.dashboard.pages.research_archive as archive_page
    import openedge.dashboard.pages.research_journal as journal_page
    import openedge.dashboard.pages.research_lab as lab_page

    assert hasattr(app_module, "main")
    assert hasattr(operations_page, "main")
    assert hasattr(archive_page, "main")
    assert hasattr(journal_page, "main")
    assert hasattr(lab_page, "main")
