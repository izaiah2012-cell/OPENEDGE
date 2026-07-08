from __future__ import annotations

import re

import pandas as pd


def correct_as_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def accuracy_percent(series: pd.Series) -> float:
    valid = correct_as_numeric(series).dropna()
    if valid.empty:
        return 0.0
    return round(float(valid.mean()) * 100.0, 2)


def extract_regime(notes: str) -> str:
    text = str(notes or "")
    match = re.search(r"regime=([^;]+)", text, flags=re.IGNORECASE)
    if not match:
        return "Unknown"
    return match.group(1).strip()


def regime_from_bias_and_vix(bias: str, vix_value) -> str:
    bias_text = str(bias or "").upper()
    try:
        vix = float(vix_value)
    except Exception:
        vix = None

    if bias_text == "UP" and (vix is not None and vix <= 5):
        return "Risk On"
    if bias_text == "DOWN" or (vix is not None and vix >= 7):
        return "Risk Off"
    return "Neutral"


def confidence_bucket(value) -> str:
    try:
        confidence = float(value)
    except Exception:
        return "Unknown"

    if confidence < 50:
        return "<50"
    if confidence < 60:
        return "50-59"
    if confidence < 70:
        return "60-69"
    if confidence < 80:
        return "70-79"
    return "80+"


def confidence_band(value) -> str:
    try:
        confidence = float(value)
    except Exception:
        return "Unknown"

    if confidence < 55:
        return "Low"
    if confidence < 70:
        return "Moderate"
    return "High"
