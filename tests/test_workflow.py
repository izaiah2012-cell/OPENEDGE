import json
from datetime import datetime, timezone

from openedge.workflows.morning_workflow import MorningWorkflow


def _engine_report():
    return {
        "status": "READY",
        "market": {
            "market_regime": "Risk On",
            "confidence": 74,
            "bias": "BULLISH",
            "opening_style": "Trend Open",
            "opportunity_score": 8,
            "internals_rows": [
                {"Asset": "SPY", "Price": "620.10", "Daily %": "+0.42%", "Direction": "UP"}
            ],
        },
        "summary": {
            "executive_summary": "Constructive setup with healthy participation.",
            "research_conclusion": "Favorable continuation path if breadth holds.",
            "todays_focus": "Focus on high-relative-strength leaders.",
        },
        "performance": {"signals_tracked": 10, "historical_accuracy": 70.0},
    }


def test_workflow_pipeline_exports_and_updates_metadata(monkeypatch, tmp_path):
    workflow = MorningWorkflow(
        base_dir=tmp_path,
        as_of=datetime(2026, 7, 8, 9, 30, tzinfo=timezone.utc),
    )

    monkeypatch.setattr(workflow, "load_market_data", lambda: {"SPY": {"change": 0.4}})
    monkeypatch.setattr(workflow, "load_market_internals", lambda: {"SPY": {"price": 620.1, "daily_change_percent": 0.42, "direction": "UP"}})
    monkeypatch.setattr(workflow, "load_macro_events", lambda: [{"time": "08:30 ET", "event": "CPI", "impact": "High"}])
    monkeypatch.setattr(workflow, "load_leadership", lambda: {"Technology": {"score": 1.2, "status": "Strong"}})
    monkeypatch.setattr(workflow, "run_historical_match", lambda: {"best_match": {"date": "2026-06-10", "similarity": 82.4}})
    monkeypatch.setattr(workflow, "run_intelligence_engine", lambda **kwargs: _engine_report())

    report = workflow.run()

    assert report["Market Regime"] == "Risk On"
    assert report["Confidence"] == 74

    date_key = "2026-07-08"
    assert (tmp_path / "reports" / f"{date_key}.md").exists()
    assert (tmp_path / "reports" / f"{date_key}.json").exists()
    assert (tmp_path / "reports" / f"{date_key}.html").exists()

    snapshot_file = tmp_path / "database" / "history" / f"{date_key}.json"
    assert snapshot_file.exists()
    snapshot_payload = json.loads(snapshot_file.read_text(encoding="utf-8"))
    assert snapshot_payload["Market Regime"] == "Risk On"

    log_file = tmp_path / "logs" / f"{date_key}.log"
    assert log_file.exists()
    log_text = log_file.read_text(encoding="utf-8")
    assert "Workflow Start:" in log_text
    assert "Workflow Finish:" in log_text
    assert "Duration:" in log_text
    assert "Data Sources:" in log_text
    assert "Export Status:" in log_text

    status_file = tmp_path / "database" / "workflow_status.json"
    assert status_file.exists()
    status_payload = json.loads(status_file.read_text(encoding="utf-8"))
    assert status_payload["research_status"] == "SUCCESS"
    assert status_payload["last_report_generated"].endswith(f"{date_key}.md")
    assert "workflow_duration_seconds" in status_payload
