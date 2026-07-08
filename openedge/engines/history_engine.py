from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

FEATURE_COLUMNS = ["risk", "leadership", "vix", "oar", "oos"]
FEATURE_WEIGHTS = {
    "risk": 1.1,
    "leadership": 1.0,
    "vix": 1.2,
    "oar": 1.15,
    "oos": 1.15,
}
MAX_RECENCY_BOOST = 0.12


def _empty_result(message):
    return {
        "matches": [],
        "best_match": {},
        "average_similarity": 0.0,
        "most_common_outcome": "N/A",
        "message": message,
    }


def _default_db_path():
    return Path(__file__).resolve().parents[2] / "openedge_db.csv"


def _confidence_band(similarity):
    if similarity >= 75:
        return "Strong"
    if similarity >= 55:
        return "Moderate"
    return "Weak"


def _why_similar_text(feature_deltas):
    ordered = sorted(feature_deltas.items(), key=lambda item: item[1])[:2]
    labels = ", ".join(name.upper() for name, _ in ordered)
    return f"Closest on {labels}" if labels else "No diagnostics"


def _load_history(csv_path):
    file_path = Path(csv_path)
    if not file_path.exists():
        return None

    try:
        df = pd.read_csv(file_path)
    except Exception:
        return None

    if df.empty:
        return None

    return df


def get_historical_matches(csv_path=None, top_n=5):
    df = _load_history(csv_path or _default_db_path())
    if df is None:
        return _empty_result("Historical file not found or unreadable.")

    for col in FEATURE_COLUMNS:
        df[col] = pd.to_numeric(df.get(col), errors="coerce")

    complete_mask = df[FEATURE_COLUMNS].notna().all(axis=1)
    complete_mask &= pd.to_numeric(df.get("correct"), errors="coerce").notna()

    completed = df[complete_mask].copy()
    if len(completed) < 2:
        return _empty_result("Not enough historical data yet. Keep collecting sessions.")

    latest_idx = completed.index[-1]
    latest_row = completed.loc[latest_idx]
    latest_vector = latest_row[FEATURE_COLUMNS].to_numpy(dtype=float)

    candidates = completed.drop(index=latest_idx)
    if candidates.empty:
        return _empty_result("Not enough historical data yet. Keep collecting sessions.")

    matches = []
    total_candidates = len(candidates)
    for position, (_, row) in enumerate(candidates.iterrows(), start=1):
        candidate_vector = row[FEATURE_COLUMNS].to_numpy(dtype=float)
        deltas = np.abs(candidate_vector - latest_vector)
        weighted_components = [
            FEATURE_WEIGHTS[col] * (delta ** 2)
            for col, delta in zip(FEATURE_COLUMNS, deltas)
        ]
        distance = float(np.sqrt(np.sum(weighted_components)))

        base_similarity = 100.0 / (1.0 + distance)
        recency_ratio = position / total_candidates
        recency_factor = 1.0 + (MAX_RECENCY_BOOST * recency_ratio)
        similarity = min(100.0, base_similarity * recency_factor)

        feature_deltas = {
            col: round(float(delta), 4)
            for col, delta in zip(FEATURE_COLUMNS, deltas)
        }

        matches.append(
            {
                "date": str(row.get("date", "N/A")),
                "similarity": round(similarity, 2),
                "bias": str(row.get("bias", "N/A")),
                "actual": str(row.get("actual", "N/A")),
                "correct": row.get("correct", "N/A"),
                "confidence_band": _confidence_band(similarity),
                "recency_factor": round(recency_factor, 3),
                "feature_deltas": feature_deltas,
                "why_similar": _why_similar_text(feature_deltas),
            }
        )

    matches.sort(key=lambda item: item["similarity"], reverse=True)
    top_matches = matches[:top_n]
    for rank, match in enumerate(top_matches, start=1):
        match["rank"] = rank

    best_match = top_matches[0] if top_matches else {}
    average_similarity = round(sum(m["similarity"] for m in top_matches) / len(top_matches), 2) if top_matches else 0.0

    outcomes = [m.get("actual") for m in top_matches if m.get("actual") not in (None, "", "N/A")]
    most_common_outcome = Counter(outcomes).most_common(1)[0][0] if outcomes else "N/A"

    return {
        "matches": top_matches,
        "best_match": best_match,
        "average_similarity": average_similarity,
        "most_common_outcome": most_common_outcome,
        "message": "",
    }