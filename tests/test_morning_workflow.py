import json
from datetime import datetime, timezone

from openedge.workflows.morning_workflow import MorningWorkflow


def _sample_report():
    return {
        "status": "READY",
        "market": {
            "market_regime": "Risk On",
            "bias": "BULLISH",
            "risk_level": "LOW",
            "confidence": 72,
            "opening_risk": 4,
            "opportunity_score": 7,
            "internals_rows": [
                {"Asset": "SPY", "Price": "620.10", "Daily %": "+0.42%", "Direction": "UP"}
            ],
        },
        "macro": {
            "macro_risk": "MEDIUM",
            "today_events": [
                {"Time": "08:30 ET", "Event": "CPI", "Impact": "High"}
            ],
        },
        "leadership": {
            "rows": [
                {"Sector": "Technology", "Status": "Strong", "Score (%)": 1.2}
            ]
        },
        "historical": {
            "best_match": {"date": "2026-06-10", "similarity": 80.1},
            "historical_confidence": "Strong",
            "expected_outcome": "UP",
        },
        "summary": {
            "executive_summary": "Constructive backdrop with controlled risk.",
            "todays_focus": "Focus on relative strength continuation.",
            "research_conclusion": "Maintain disciplined execution into open.",
        },
    }


def test_morning_workflow_creates_reports_snapshot_and_log(monkeypatch, tmp_path):
    workflow = MorningWorkflow(
        base_dir=tmp_path,
        as_of=datetime(2026, 7, 8, 9, 30, tzinfo=timezone.utc),
    )

    monkeypatch.setattr(workflow, "load_market_data", lambda: {"SPY": {"change": 0.4}})
    monkeypatch.setattr(workflow, "load_market_internals", lambda: {"SPY": {"price": 620.1, "daily_change_percent": 0.42, "direction": "UP"}})
    monkeypatch.setattr(workflow, "load_macro_events", lambda: [{"time": "08:30 ET", "event": "CPI", "impact": "High"}])
    monkeypatch.setattr(workflow, "load_leadership", lambda: {"Technology": {"score": 1.2, "status": "Strong"}})
    monkeypatch.setattr(workflow, "run_historical_match", lambda: {"best_match": {"date": "2026-06-10", "similarity": 80.1}})
    monkeypatch.setattr(workflow, "run_intelligence_engine", lambda **kwargs: _sample_report())

    report = workflow.run()

    assert report["Market Regime"] == "Risk On"
    assert report["Confidence"] == 72

    report_date = "2026-07-08"
    markdown_file = tmp_path / "reports" / f"{report_date}.md"
    json_file = tmp_path / "reports" / f"{report_date}.json"
    html_file = tmp_path / "reports" / f"{report_date}.html"
    snapshot_file = tmp_path / "database" / "history" / f"{report_date}.json"
    log_file = tmp_path / "logs" / f"{report_date}.log"
    status_file = tmp_path / "database" / "workflow_status.json"

    assert markdown_file.exists()
    assert json_file.exists()
    assert html_file.exists()
    assert snapshot_file.exists()
    assert log_file.exists()
    assert status_file.exists()

    markdown = markdown_file.read_text(encoding="utf-8")
    assert "## Executive Summary" in markdown
    assert "## Market Regime" in markdown
    assert "## Confidence" in markdown
    assert "## Market Internals" in markdown
    assert "## Leadership" in markdown
    assert "## Macro Events" in markdown
    assert "## Historical Match" in markdown
    assert "## Today's Focus" in markdown
    assert "## Research Conclusion" in markdown

    snapshot_payload = json.loads(snapshot_file.read_text(encoding="utf-8"))
    assert snapshot_payload["Market Regime"] == "Risk On"

    log_text = log_file.read_text(encoding="utf-8")
    assert "Workflow Start:" in log_text
    assert "Workflow Finish:" in log_text
    assert "Duration:" in log_text
    assert "Data Sources:" in log_text
    assert "Export Status: SUCCESS" in log_text

    status_payload = json.loads(status_file.read_text(encoding="utf-8"))
    assert status_payload["research_generated"] is True
