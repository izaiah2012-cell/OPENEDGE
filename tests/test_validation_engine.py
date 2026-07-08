from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path

import pandas as pd

from openedge.validation.journal import append_entry, backfill_from_db, dedupe_entries, load_entries, save_entry
from openedge.validation.validation_engine import ValidationEngine
from openedge.workflows.morning_workflow import MorningWorkflow


def test_validation_empty_dataset(tmp_path):
    db_path = tmp_path / "openedge_db.csv"
    journal_path = tmp_path / "research_journal.csv"
    db_path.write_text("date,risk,leadership,vix,gap_pct,range_5m,open_type,oar,oos,bias,actual,correct\n", encoding="utf-8")

    engine = ValidationEngine(db_path=db_path, journal_path=journal_path, reports_dir=tmp_path / "reports")

    overall = engine.overall_accuracy()
    assert overall["total_signals"] == 0
    assert overall["overall_accuracy"] == 0.0
    assert engine.rolling_accuracy(20)["points"] == []
    assert engine.accuracy_by_regime()["items"] == []
    assert engine.accuracy_by_confidence_band()["items"] == []


def test_validation_small_dataset_metrics(tmp_path):
    db_path = tmp_path / "openedge_db.csv"
    journal_path = tmp_path / "research_journal.csv"
    pd.DataFrame(
        [
            {"date": "2026-07-01", "risk": 0, "leadership": 0, "vix": 4.0, "gap_pct": 0, "range_5m": 0, "open_type": "NEUTRAL", "oar": 0, "oos": 0, "bias": "UP", "actual": "UP", "correct": 1},
            {"date": "2026-07-02", "risk": 0, "leadership": 0, "vix": 8.0, "gap_pct": 0, "range_5m": 0, "open_type": "NEUTRAL", "oar": 0, "oos": 0, "bias": "DOWN", "actual": "UP", "correct": 0},
            {"date": "2026-07-03", "risk": 0, "leadership": 0, "vix": 6.0, "gap_pct": 0, "range_5m": 0, "open_type": "NEUTRAL", "oar": 0, "oos": 0, "bias": "UP", "actual": "UP", "correct": 1},
        ]
    ).to_csv(db_path, index=False)

    append_entry(
        journal_path,
        {
            "date": "2026-07-01",
            "market_regime": "Risk On",
            "bias": "UP",
            "confidence": 72,
            "actual": "UP",
            "correct": 1,
            "notes": "source=test",
        },
    )
    save_entry(
        journal_path,
        {
            "date": "2026-07-02",
            "market_regime": "Risk Off",
            "bias": "DOWN",
            "confidence": 60,
            "actual": "UP",
            "correct": 0,
            "notes": "source=test",
        },
    )

    engine = ValidationEngine(db_path=db_path, journal_path=journal_path, reports_dir=tmp_path / "reports")

    overall = engine.overall_accuracy()
    assert overall["total_signals"] == 3
    assert overall["correct_signals"] == 2
    assert overall["incorrect_signals"] == 1
    assert overall["overall_accuracy"] == 66.67

    rolling = engine.rolling_accuracy(window=20)
    assert len(rolling["points"]) == 3

    by_regime = engine.accuracy_by_regime()
    regimes = {item["regime"]: item["accuracy"] for item in by_regime["items"]}
    assert "Risk On" in regimes
    assert "Risk Off" in regimes

    by_confidence = engine.accuracy_by_confidence_band()
    assert len(by_confidence["items"]) >= 1


def test_journal_append_and_load_entries(tmp_path):
    journal_path = tmp_path / "research_journal.csv"
    append_entry(
        journal_path,
        {
            "date": "2026-07-08",
            "market_regime": "Neutral",
            "bias": "UP",
            "confidence": 67,
            "actual": "DOWN",
            "correct": 0,
            "notes": "source=test",
        },
    )

    entries = load_entries(journal_path)
    assert len(entries) == 1
    assert entries.iloc[0]["market_regime"] == "Neutral"
    assert entries.iloc[0]["confidence"] == 67


def test_backfill_from_db_appends_missing_dates(tmp_path):
    db_path = tmp_path / "openedge_db.csv"
    journal_path = tmp_path / "research_journal.csv"
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(
        [
            {"date": "2026-07-01", "bias": "UP", "actual": "UP", "correct": 1, "vix": 4.0},
            {"date": "2026-07-02", "bias": "DOWN", "actual": "DOWN", "correct": 1, "vix": 8.0},
        ]
    ).to_csv(db_path, index=False)

    append_entry(
        journal_path,
        {
            "date": "2026-07-01",
            "market_regime": "Risk On",
            "bias": "UP",
            "confidence": 72,
            "actual": "UP",
            "correct": 1,
            "notes": "source=test",
        },
    )

    (reports_dir / "2026-07-02.json").write_text(
        json.dumps({"Date": "2026-07-02", "Confidence": 65}),
        encoding="utf-8",
    )

    added = backfill_from_db(db_path, journal_path, reports_dir=reports_dir)
    assert added == 1

    entries = load_entries(journal_path)
    assert len(entries) == 2
    added_row = entries[entries["date"] == "2026-07-02"].iloc[0]
    assert added_row["market_regime"] == "Risk Off"
    assert added_row["confidence"] == 65
    assert added_row["notes"] == "source=backfill"


def test_validate_exports_json(monkeypatch, tmp_path):
    module_path = Path(__file__).resolve().parents[1] / "openedge.py"
    spec = importlib.util.spec_from_file_location("openedge_cli", module_path)
    openedge_cli = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(openedge_cli)

    export_path = tmp_path / "validation_summary.json"
    monkeypatch.setattr(openedge_cli, "DB_FILE", tmp_path / "openedge_db.csv")
    monkeypatch.setattr(openedge_cli, "BASE_DIR", tmp_path)
    monkeypatch.setattr(openedge_cli, "REPORTS_DIR", tmp_path / "reports")

    (tmp_path / "openedge_db.csv").write_text(
        "date,risk,leadership,vix,gap_pct,range_5m,open_type,oar,oos,bias,actual,correct\n"
        "2026-07-01,0,0,4,0,0,NEUTRAL,0,0,UP,UP,1\n",
        encoding="utf-8",
    )

    openedge_cli.validate(export_json=str(export_path), backfill_journal=False)

    assert export_path.exists()
    payload = json.loads(export_path.read_text(encoding="utf-8"))
    assert payload["total_signals"] == 1
    assert "overall_accuracy" in payload


def test_dedupe_entries_keeps_latest_by_date(tmp_path):
    journal_path = tmp_path / "research_journal.csv"
    append_entry(
        journal_path,
        {
            "date": "2026-07-08",
            "market_regime": "Risk On",
            "bias": "UP",
            "confidence": 60,
            "actual": "UP",
            "correct": 1,
            "notes": "source=first",
        },
    )
    append_entry(
        journal_path,
        {
            "date": "2026-07-08",
            "market_regime": "Risk Off",
            "bias": "DOWN",
            "confidence": 70,
            "actual": "DOWN",
            "correct": 1,
            "notes": "source=latest",
        },
    )

    removed = dedupe_entries(journal_path)
    assert removed == 1

    entries = load_entries(journal_path)
    assert len(entries) == 1
    assert entries.iloc[0]["notes"] == "source=latest"


def test_dedupe_entries_date_bias_mode_keeps_distinct_biases(tmp_path):
    journal_path = tmp_path / "research_journal.csv"
    append_entry(
        journal_path,
        {
            "date": "2026-07-08",
            "market_regime": "Risk On",
            "bias": "UP",
            "confidence": 60,
            "actual": "UP",
            "correct": 1,
            "notes": "source=up-old",
        },
    )
    append_entry(
        journal_path,
        {
            "date": "2026-07-08",
            "market_regime": "Risk On",
            "bias": "UP",
            "confidence": 62,
            "actual": "UP",
            "correct": 1,
            "notes": "source=up-new",
        },
    )
    append_entry(
        journal_path,
        {
            "date": "2026-07-08",
            "market_regime": "Risk Off",
            "bias": "DOWN",
            "confidence": 65,
            "actual": "DOWN",
            "correct": 1,
            "notes": "source=down",
        },
    )

    removed = dedupe_entries(journal_path, mode="date-bias")
    assert removed == 1

    entries = load_entries(journal_path)
    assert len(entries) == 2
    notes = sorted(entries["notes"].astype(str).tolist())
    assert notes == ["source=down", "source=up-new"]


def test_validate_dedupes_journal(monkeypatch, tmp_path):
    module_path = Path(__file__).resolve().parents[1] / "openedge.py"
    spec = importlib.util.spec_from_file_location("openedge_cli", module_path)
    openedge_cli = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(openedge_cli)

    monkeypatch.setattr(openedge_cli, "DB_FILE", tmp_path / "openedge_db.csv")
    monkeypatch.setattr(openedge_cli, "BASE_DIR", tmp_path)
    monkeypatch.setattr(openedge_cli, "REPORTS_DIR", tmp_path / "reports")

    (tmp_path / "openedge_db.csv").write_text(
        "date,risk,leadership,vix,gap_pct,range_5m,open_type,oar,oos,bias,actual,correct\n"
        "2026-07-08,0,0,4,0,0,NEUTRAL,0,0,UP,UP,1\n",
        encoding="utf-8",
    )

    journal_path = tmp_path / "research_journal.csv"
    append_entry(
        journal_path,
        {
            "date": "2026-07-08",
            "market_regime": "Risk On",
            "bias": "UP",
            "confidence": 60,
            "actual": "UP",
            "correct": 1,
            "notes": "source=first",
        },
    )
    append_entry(
        journal_path,
        {
            "date": "2026-07-08",
            "market_regime": "Risk On",
            "bias": "UP",
            "confidence": 61,
            "actual": "UP",
            "correct": 1,
            "notes": "source=second",
        },
    )

    openedge_cli.validate(dedupe_journal=True)

    entries = load_entries(journal_path)
    assert len(entries) == 1
    assert entries.iloc[0]["notes"] == "source=second"


def test_validate_dedupes_journal_date_bias_mode(monkeypatch, tmp_path):
    module_path = Path(__file__).resolve().parents[1] / "openedge.py"
    spec = importlib.util.spec_from_file_location("openedge_cli", module_path)
    openedge_cli = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(openedge_cli)

    monkeypatch.setattr(openedge_cli, "DB_FILE", tmp_path / "openedge_db.csv")
    monkeypatch.setattr(openedge_cli, "BASE_DIR", tmp_path)
    monkeypatch.setattr(openedge_cli, "REPORTS_DIR", tmp_path / "reports")

    (tmp_path / "openedge_db.csv").write_text(
        "date,risk,leadership,vix,gap_pct,range_5m,open_type,oar,oos,bias,actual,correct\n"
        "2026-07-08,0,0,4,0,0,NEUTRAL,0,0,UP,UP,1\n",
        encoding="utf-8",
    )

    journal_path = tmp_path / "research_journal.csv"
    append_entry(
        journal_path,
        {
            "date": "2026-07-08",
            "market_regime": "Risk On",
            "bias": "UP",
            "confidence": 60,
            "actual": "UP",
            "correct": 1,
            "notes": "source=up-old",
        },
    )
    append_entry(
        journal_path,
        {
            "date": "2026-07-08",
            "market_regime": "Risk On",
            "bias": "UP",
            "confidence": 61,
            "actual": "UP",
            "correct": 1,
            "notes": "source=up-new",
        },
    )
    append_entry(
        journal_path,
        {
            "date": "2026-07-08",
            "market_regime": "Risk Off",
            "bias": "DOWN",
            "confidence": 62,
            "actual": "DOWN",
            "correct": 1,
            "notes": "source=down",
        },
    )

    openedge_cli.validate(dedupe_journal=True, dedupe_mode="date-bias")

    entries = load_entries(journal_path)
    assert len(entries) == 2
    notes = sorted(entries["notes"].astype(str).tolist())
    assert notes == ["source=down", "source=up-new"]


def test_morning_workflow_appends_journal_entry(monkeypatch, tmp_path):
    workflow = MorningWorkflow(
        base_dir=tmp_path,
        as_of=datetime(2026, 7, 8, 9, 30, tzinfo=timezone.utc),
    )

    monkeypatch.setattr(workflow, "load_market_data", lambda: {"SPY": {"change": 0.3}})
    monkeypatch.setattr(workflow, "load_market_internals", lambda: {"SPY": {"price": 620.0, "daily_change_percent": 0.4, "direction": "UP"}})
    monkeypatch.setattr(workflow, "load_macro_events", lambda: [])
    monkeypatch.setattr(workflow, "load_leadership", lambda: {"Technology": {"score": 1.2, "status": "Strong"}})
    monkeypatch.setattr(workflow, "run_historical_match", lambda: {"best_match": {"date": "2026-07-07", "similarity": 80.0}})
    monkeypatch.setattr(
        workflow,
        "run_intelligence_engine",
        lambda **kwargs: {
            "status": "READY",
            "market": {
                "market_regime": "Risk On",
                "confidence": 71,
                "bias": "BULLISH",
                "opening_style": "Trend Open",
                "opportunity_score": 8,
                "internals_rows": [],
            },
            "summary": {
                "executive_summary": "Constructive.",
                "research_conclusion": "Proceed with discipline.",
            },
            "latest_signal": {"Actual": "UP", "Correct": 1},
            "performance": {},
        },
    )

    workflow.run()

    journal_df = pd.read_csv(tmp_path / "research_journal.csv")
    assert len(journal_df) == 1
    assert journal_df.iloc[0]["bias"] == "BULLISH"
    assert journal_df.iloc[0]["market_regime"] == "Risk On"
    assert journal_df.iloc[0]["actual"] == "UP"
    assert journal_df.iloc[0]["confidence"] == 71
