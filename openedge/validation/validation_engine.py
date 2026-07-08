from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from openedge.validation.journal import JOURNAL_FIELDS, load_entries
from openedge.validation.metrics import accuracy_percent, confidence_band, regime_from_bias_and_vix


class ValidationEngine:
    """Computes OPENEDGE research-quality metrics from historical signal data."""

    def __init__(self, db_path: Path | None = None, journal_path: Path | None = None, reports_dir: Path | None = None):
        base_dir = Path(__file__).resolve().parents[2]
        self.db_path = Path(db_path) if db_path else base_dir / "openedge_db.csv"
        self.journal_path = Path(journal_path) if journal_path else base_dir / "research_journal.csv"
        self.reports_dir = Path(reports_dir) if reports_dir else base_dir / "reports"

    def _load(self) -> pd.DataFrame:
        if not self.db_path.exists():
            return pd.DataFrame(columns=["date", "bias", "actual", "correct", "vix", "confidence", "market_regime"])

        frame = pd.read_csv(self.db_path)
        if frame.empty:
            return pd.DataFrame(columns=["date", "bias", "actual", "correct", "vix", "confidence", "market_regime"])

        for col in ["date", "bias", "actual", "correct", "vix"]:
            if col not in frame.columns:
                frame[col] = pd.NA

        frame["date"] = frame["date"].astype(str)
        frame["correct"] = pd.to_numeric(frame.get("correct"), errors="coerce")
        frame["vix"] = pd.to_numeric(frame.get("vix"), errors="coerce")

        frame["market_regime"] = [
            regime_from_bias_and_vix(row.get("bias"), row.get("vix"))
            for _, row in frame.iterrows()
        ]

        journal = load_entries(self.journal_path)
        if not journal.empty:
            journal = journal.copy()
            journal["confidence"] = pd.to_numeric(journal.get("confidence"), errors="coerce")
            journal = journal.sort_values("date").drop_duplicates(subset=["date"], keep="last")
            merged = frame.merge(
                journal[["date", "market_regime", "confidence"]],
                on="date",
                how="left",
                suffixes=("", "_journal"),
            )
            merged["market_regime"] = merged["market_regime_journal"].combine_first(merged["market_regime"])
            if "confidence_journal" in merged.columns:
                merged["confidence"] = merged["confidence_journal"]
            elif "confidence" not in merged.columns:
                merged["confidence"] = pd.NA
            frame = merged.drop(columns=["market_regime_journal", "confidence_journal"], errors="ignore")
        else:
            frame["confidence"] = pd.NA

        frame["confidence"] = pd.to_numeric(frame.get("confidence"), errors="coerce")
        frame["confidence_band"] = frame.get("confidence", pd.Series(dtype=float)).map(confidence_band)
        frame["month"] = pd.to_datetime(frame["date"], errors="coerce").dt.to_period("M").astype(str)
        return frame

    def overall_accuracy(self) -> dict:
        frame = self._load()
        valid = frame.get("correct", pd.Series(dtype=float)).dropna()
        total = int(len(valid))
        correct = int((valid == 1).sum())
        incorrect = int((valid == 0).sum())
        return {
            "total_signals": total,
            "correct_signals": correct,
            "incorrect_signals": incorrect,
            "overall_accuracy": accuracy_percent(valid),
        }

    def rolling_accuracy(self, window: int = 20) -> dict:
        frame = self._load()
        if frame.empty:
            return {"window": window, "latest_accuracy": None, "points": []}

        valid = frame.dropna(subset=["correct"]).copy()
        if valid.empty:
            return {"window": window, "latest_accuracy": None, "points": []}

        valid["rolling_accuracy"] = valid["correct"].rolling(
            window=min(window, len(valid)),
            min_periods=1,
        ).mean() * 100.0
        valid["rolling_accuracy"] = valid["rolling_accuracy"].round(2)
        points = [
            {"date": str(row["date"]), "accuracy": float(row["rolling_accuracy"])}
            for _, row in valid.iterrows()
            if pd.notna(row["rolling_accuracy"])
        ]
        latest = points[-1]["accuracy"] if points else None
        return {"window": window, "latest_accuracy": latest, "points": points}

    def accuracy_by_regime(self) -> dict:
        frame = self._load()
        if frame.empty:
            return {"items": [], "best_regime": "N/A", "worst_regime": "N/A"}

        grouped = frame.dropna(subset=["correct"]).groupby("market_regime").agg(
            sessions=("correct", "count"),
            accuracy=("correct", "mean"),
        )
        if grouped.empty:
            return {"items": [], "best_regime": "N/A", "worst_regime": "N/A"}

        grouped["accuracy"] = (grouped["accuracy"] * 100.0).round(2)
        grouped = grouped.reset_index().rename(columns={"market_regime": "regime"})
        items = grouped.to_dict(orient="records")
        sorted_items = sorted(items, key=lambda item: item["accuracy"], reverse=True)
        return {
            "items": items,
            "best_regime": sorted_items[0]["regime"],
            "worst_regime": sorted_items[-1]["regime"],
        }

    def accuracy_by_confidence_band(self) -> dict:
        frame = self._load()
        if frame.empty:
            return {"items": []}

        grouped = frame.dropna(subset=["correct"]).groupby("confidence_band").agg(
            sessions=("correct", "count"),
            accuracy=("correct", "mean"),
            average_confidence=("confidence", "mean"),
        )
        if grouped.empty:
            return {"items": []}

        grouped["accuracy"] = (grouped["accuracy"] * 100.0).round(2)
        grouped["average_confidence"] = grouped["average_confidence"].round(2)
        grouped = grouped.reset_index().rename(columns={"confidence_band": "band"})
        return {"items": grouped.to_dict(orient="records")}

    def accuracy_by_bias(self) -> dict:
        frame = self._load()
        if frame.empty:
            return {"items": []}

        grouped = frame.dropna(subset=["correct"]).groupby("bias").agg(
            sessions=("correct", "count"),
            accuracy=("correct", "mean"),
        )
        if grouped.empty:
            return {"items": []}

        grouped["accuracy"] = (grouped["accuracy"] * 100.0).round(2)
        grouped = grouped.reset_index()
        return {"items": grouped.to_dict(orient="records")}

    def monthly_accuracy(self) -> dict:
        frame = self._load()
        if frame.empty:
            return {"items": []}

        valid = frame.dropna(subset=["correct"])
        if valid.empty:
            return {"items": []}

        grouped = valid.groupby("month").agg(
            sessions=("correct", "count"),
            accuracy=("correct", "mean"),
        )
        grouped["accuracy"] = (grouped["accuracy"] * 100.0).round(2)
        grouped = grouped.reset_index().rename(columns={"month": "month"})
        return {"items": grouped.to_dict(orient="records")}

    def confidence_calibration(self) -> dict:
        bands = self.accuracy_by_confidence_band().get("items", [])
        overall_confidence = self._load().get("confidence", pd.Series(dtype=float)).dropna()
        return {
            "average_confidence": round(float(overall_confidence.mean()), 2) if not overall_confidence.empty else 0.0,
            "items": [
                {
                    "band": row.get("band", "Unknown"),
                    "expected_confidence": row.get("average_confidence", 0.0),
                    "realized_accuracy": row.get("accuracy", 0.0),
                    "sessions": row.get("sessions", 0),
                }
                for row in bands
            ],
        }

    def summary_metrics(self) -> dict:
        overall = self.overall_accuracy()
        roll20 = self.rolling_accuracy(20)
        roll50 = self.rolling_accuracy(50)
        regimes = self.accuracy_by_regime()
        calibration = self.confidence_calibration()

        return {
            "total_signals": overall["total_signals"],
            "correct_signals": overall["correct_signals"],
            "incorrect_signals": overall["incorrect_signals"],
            "overall_accuracy": overall["overall_accuracy"],
            "rolling_20_accuracy": roll20.get("latest_accuracy") or 0.0,
            "rolling_50_accuracy": roll50.get("latest_accuracy") or 0.0,
            "average_confidence": calibration.get("average_confidence", 0.0),
            "best_performing_regime": regimes.get("best_regime", "N/A"),
            "worst_performing_regime": regimes.get("worst_regime", "N/A"),
            "average_historical_similarity": self._average_historical_similarity(),
        }

    def _average_historical_similarity(self) -> float:
        similarities = []
        if not self.reports_dir.exists():
            return 0.0

        for file_path in sorted(self.reports_dir.glob("*.json")):
            try:
                payload = json.loads(file_path.read_text(encoding="utf-8"))
            except Exception:
                continue

            try:
                value = payload.get("Raw Engine Report", {}).get("historical", {}).get("average_similarity")
            except Exception:
                value = None

            if value is not None:
                try:
                    similarities.append(float(value))
                except Exception:
                    continue

        if not similarities:
            return 0.0
        return round(sum(similarities) / len(similarities), 2)
