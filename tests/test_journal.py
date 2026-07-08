import pandas as pd

from openedge.validation.journal import append_entry, load_entries, update_notes


def test_journal_append_and_load(tmp_path):
    journal_path = tmp_path / "research_journal.csv"

    append_entry(
        journal_path,
        {
            "date": "2026-07-08",
            "market_regime": "Risk Off",
            "bias": "DOWN",
            "confidence": 67,
            "actual": "DOWN",
            "correct": 1,
            "notes": "source=test",
        },
    )

    entries = load_entries(journal_path)
    assert len(entries) == 1
    assert entries.iloc[0]["date"] == "2026-07-08"
    assert entries.iloc[0]["correct"] == 1


def test_update_notes_append_only(tmp_path):
    journal_path = tmp_path / "research_journal.csv"

    append_entry(
        journal_path,
        {
            "date": "2026-07-08",
            "market_regime": "Risk On",
            "bias": "UP",
            "confidence": 72,
            "actual": "UP",
            "correct": 1,
            "notes": "initial",
        },
    )

    update_notes(journal_path, date="2026-07-08", bias="UP", notes="updated")

    entries = pd.read_csv(journal_path)
    assert len(entries) == 2
    assert entries.iloc[-1]["notes"] == "updated"
