from __future__ import annotations

import pandas as pd


CONFIDENCE_BANDS = ["90-100", "80-89", "70-79", "60-69", "Below 60"]


def confidence_to_band(value) -> str:
    try:
        confidence = float(value)
    except Exception:
        return "Below 60"

    if confidence >= 90:
        return "90-100"
    if confidence >= 80:
        return "80-89"
    if confidence >= 70:
        return "70-79"
    if confidence >= 60:
        return "60-69"
    return "Below 60"


def build_confidence_calibration(frame: pd.DataFrame) -> dict:
    if frame.empty:
        return {
            "average_confidence": 0.0,
            "items": [
                {"band": band, "signals": 0, "correct": 0, "accuracy_percent": 0.0}
                for band in CONFIDENCE_BANDS
            ],
        }

    working = frame.copy()
    working["confidence"] = pd.to_numeric(working.get("confidence"), errors="coerce")
    working["correct"] = pd.to_numeric(working.get("correct"), errors="coerce")
    working = working.dropna(subset=["correct"])

    if working.empty:
        return {
            "average_confidence": 0.0,
            "items": [
                {"band": band, "signals": 0, "correct": 0, "accuracy_percent": 0.0}
                for band in CONFIDENCE_BANDS
            ],
        }

    working["band"] = working["confidence"].map(confidence_to_band)
    grouped = working.groupby("band").agg(
        signals=("correct", "count"),
        correct=("correct", lambda s: int((s == 1).sum())),
        accuracy_percent=("correct", lambda s: round(float(s.mean()) * 100.0, 2)),
    )

    items = []
    for band in CONFIDENCE_BANDS:
        if band in grouped.index:
            row = grouped.loc[band]
            items.append(
                {
                    "band": band,
                    "signals": int(row["signals"]),
                    "correct": int(row["correct"]),
                    "accuracy_percent": float(row["accuracy_percent"]),
                }
            )
        else:
            items.append({"band": band, "signals": 0, "correct": 0, "accuracy_percent": 0.0})

    avg_confidence = working["confidence"].dropna()
    return {
        "average_confidence": round(float(avg_confidence.mean()), 2) if not avg_confidence.empty else 0.0,
        "items": items,
    }