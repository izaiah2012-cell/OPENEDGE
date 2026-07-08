from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

FEATURE_COLUMNS = ["risk", "leadership", "vix", "oar", "oos"]


def _default_db_path():
    return Path(__file__).resolve().parents[2] / "openedge_db.csv"


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
        return []

    for col in FEATURE_COLUMNS:
        df[col] = pd.to_numeric(df.get(col), errors="coerce")

    complete_mask = df[FEATURE_COLUMNS].notna().all(axis=1)
    complete_mask &= pd.to_numeric(df.get("correct"), errors="coerce").notna()

    completed = df[complete_mask].copy()
    if len(completed) < 2:
        return []

    latest_idx = completed.index[-1]
    latest_row = completed.loc[latest_idx]
    latest_vector = latest_row[FEATURE_COLUMNS].to_numpy(dtype=float)

    candidates = completed.drop(index=latest_idx)
    if candidates.empty:
        return []

    matches = []
    for _, row in candidates.iterrows():
        candidate_vector = row[FEATURE_COLUMNS].to_numpy(dtype=float)
        distance = float(np.linalg.norm(candidate_vector - latest_vector))
        similarity = 100.0 / (1.0 + distance)

        matches.append(
            {
                "date": str(row.get("date", "N/A")),
                "similarity": round(similarity, 2),
                "bias": str(row.get("bias", "N/A")),
                "actual": str(row.get("actual", "N/A")),
                "correct": row.get("correct", "N/A"),
            }
        )

    matches.sort(key=lambda item: item["similarity"], reverse=True)
    top_matches = matches[:top_n]
    for rank, match in enumerate(top_matches, start=1):
        match["rank"] = rank

    return top_matches


def summarize_historical_matches(matches):
    if not matches:
        return {
            "most_similar_session": "N/A",
            "average_similarity": 0.0,
            "most_common_outcome": "N/A",
        }

    best = matches[0]
    average_similarity = round(sum(m["similarity"] for m in matches) / len(matches), 2)

    outcomes = [m.get("actual") for m in matches if m.get("actual") not in (None, "", "N/A")]
    most_common_outcome = Counter(outcomes).most_common(1)[0][0] if outcomes else "N/A"

    return {
        "most_similar_session": f"{best.get('date', 'N/A')} ({best.get('similarity', 0):.2f}%)",
        "average_similarity": average_similarity,
        "most_common_outcome": most_common_outcome,
    }