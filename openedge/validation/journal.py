from __future__ import annotations

import csv
import json
from pathlib import Path

import fcntl
import pandas as pd


LEGACY_FIELDS = ["date", "market_outcome", "openedge_bias", "correct", "confidence", "notes"]


def _extract_regime_from_notes(notes) -> str:
    text = str(notes or "")
    marker = "regime="
    if marker not in text:
        return "Neutral"
    try:
        value = text.split(marker, 1)[1].split(";", 1)[0].strip()
    except Exception:
        value = ""
    return value or "Neutral"


def _migrate_legacy_journal(path: Path) -> None:
    try:
        frame = pd.read_csv(path)
    except Exception:
        frame = pd.DataFrame(columns=LEGACY_FIELDS)

    for col in LEGACY_FIELDS:
        if col not in frame.columns:
            frame[col] = pd.NA

    migrated = pd.DataFrame(
        {
            "date": frame["date"],
            "market_regime": frame["notes"].map(_extract_regime_from_notes),
            "bias": frame["openedge_bias"],
            "confidence": frame["confidence"],
            "actual": frame["market_outcome"],
            "correct": frame["correct"],
            "notes": frame["notes"],
        }
    )
    migrated.to_csv(path, index=False, columns=JOURNAL_FIELDS)

JOURNAL_FIELDS = [
    "date",
    "market_regime",
    "bias",
    "confidence",
    "actual",
    "correct",
    "notes",
]


def ensure_journal(path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists() or path.stat().st_size == 0:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=JOURNAL_FIELDS)
            writer.writeheader()
        return path

    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader, [])

    if header == LEGACY_FIELDS:
        _migrate_legacy_journal(path)
    elif header != JOURNAL_FIELDS:
        # If schema is unknown, normalize to strict fields while preserving existing rows as possible.
        frame = pd.read_csv(path)
        for col in JOURNAL_FIELDS:
            if col not in frame.columns:
                frame[col] = pd.NA
        frame[JOURNAL_FIELDS].to_csv(path, index=False, columns=JOURNAL_FIELDS)

    return path


def append_entry(path: Path, entry: dict) -> Path:
    journal_path = ensure_journal(path)

    record = {field: entry.get(field, "") for field in JOURNAL_FIELDS}
    correct_value = record.get("correct")
    if correct_value in ("", None) or pd.isna(correct_value):
        record["correct"] = ""
    else:
        record["correct"] = int(float(correct_value))

    with journal_path.open("a+", newline="", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        writer = csv.DictWriter(handle, fieldnames=JOURNAL_FIELDS)
        writer.writerow(record)
        handle.flush()
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    return journal_path


def save_entry(path: Path, entry: dict) -> Path:
    # Save is append-only by design to preserve journal history.
    return append_entry(path, entry)


def load_entries(path: Path) -> pd.DataFrame:
    journal_path = ensure_journal(path)
    frame = pd.read_csv(journal_path)
    for col in JOURNAL_FIELDS:
        if col not in frame.columns:
            frame[col] = pd.NA
    return frame[JOURNAL_FIELDS]


def update_notes(path: Path, *, date: str, notes: str, bias: str | None = None) -> Path:
    # Append-only note updates: clone latest matching entry and append with updated notes.
    entries = load_entries(path)
    if entries.empty:
        return append_entry(
            path,
            {
                "date": date,
                "market_regime": "Neutral",
                "bias": bias or "",
                "confidence": "",
                "actual": "",
                "correct": "",
                "notes": notes,
            },
        )

    matches = entries[entries["date"].astype(str) == str(date)]
    if bias is not None:
        matches = matches[matches["bias"].astype(str) == str(bias)]

    if matches.empty:
        return append_entry(
            path,
            {
                "date": date,
                "market_regime": "Neutral",
                "bias": bias or "",
                "confidence": "",
                "actual": "",
                "correct": "",
                "notes": notes,
            },
        )

    latest = matches.iloc[-1].to_dict()
    latest["notes"] = notes
    return append_entry(path, latest)


def backfill_from_db(db_path: Path, journal_path: Path, reports_dir: Path | None = None) -> int:
    db_path = Path(db_path)
    if not db_path.exists():
        return 0

    try:
        db = pd.read_csv(db_path)
    except Exception:
        return 0

    if db.empty:
        return 0

    required = ["date", "bias", "actual", "correct", "vix"]
    for col in required:
        if col not in db.columns:
            db[col] = pd.NA

    db["date"] = db["date"].astype(str)
    journal = load_entries(journal_path)
    existing_dates = set(journal.get("date", pd.Series(dtype=str)).dropna().astype(str).tolist())

    confidence_by_date = {}
    if reports_dir:
        report_dir_path = Path(reports_dir)
        if report_dir_path.exists():
            for json_file in sorted(report_dir_path.glob("*.json")):
                try:
                    payload = json.loads(json_file.read_text(encoding="utf-8"))
                except Exception:
                    continue
                date_key = str(payload.get("Date") or "")
                if not date_key:
                    continue
                confidence_by_date[date_key] = payload.get("Confidence", "")

    added = 0
    for _, row in db.iterrows():
        date_value = str(row.get("date", ""))
        if not date_value or date_value in existing_dates:
            continue

        bias = row.get("bias", "")
        vix_value = pd.to_numeric(pd.Series([row.get("vix")]), errors="coerce").iloc[0]
        if str(bias).upper() == "UP" and pd.notna(vix_value) and float(vix_value) <= 5:
            regime = "Risk On"
        elif str(bias).upper() == "DOWN" or (pd.notna(vix_value) and float(vix_value) >= 7):
            regime = "Risk Off"
        else:
            regime = "Neutral"

        append_entry(
            journal_path,
            {
                "date": date_value,
                "market_regime": regime,
                "bias": bias,
                "confidence": confidence_by_date.get(date_value, ""),
                "actual": row.get("actual", ""),
                "correct": row.get("correct", ""),
                "notes": "source=backfill",
            },
        )
        existing_dates.add(date_value)
        added += 1

    return added


def dedupe_entries(path: Path, mode: str = "date") -> int:
    journal_path = ensure_journal(path)
    frame = pd.read_csv(journal_path)
    if frame.empty:
        return 0

    for col in JOURNAL_FIELDS:
        if col not in frame.columns:
            frame[col] = pd.NA

    if mode == "date":
        dedupe_keys = ["date"]
    elif mode == "date-bias":
        dedupe_keys = ["date", "bias"]
    else:
        raise ValueError(f"Unsupported dedupe mode: {mode}")

    before = len(frame)
    # Keep the most recent row per dedupe key based on file order.
    deduped = frame[JOURNAL_FIELDS].drop_duplicates(subset=dedupe_keys, keep="last")
    deduped.to_csv(journal_path, index=False, columns=JOURNAL_FIELDS)
    after = len(deduped)
    return max(0, before - after)


# Backward-compatible alias.
def append_journal_entry(path: Path, entry: dict) -> Path:
    return append_entry(path, entry)
