from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class ResearchStatistics:
    frame: pd.DataFrame

    def summary(self) -> dict:
        if self.frame.empty:
            return {
                "total_days": 0,
                "average_score": 0.0,
                "average_similarity": 0.0,
                "average_confidence": 0.0,
                "top_grade": "N/A",
            }

        score = pd.to_numeric(self.frame.get("research_score"), errors="coerce").fillna(0.0)
        similarity = pd.to_numeric(self.frame.get("similarity"), errors="coerce").fillna(0.0)
        confidence = pd.to_numeric(self.frame.get("morning_confidence"), errors="coerce").fillna(0.0)
        grades = self.frame.get("grade", pd.Series(dtype=str)).astype(str)

        return {
            "total_days": int(len(self.frame)),
            "average_score": round(float(score.mean()), 1),
            "average_similarity": round(float(similarity.mean()), 1),
            "average_confidence": round(float(confidence.mean()), 1),
            "top_grade": grades.mode().iloc[0] if not grades.mode().empty else "N/A",
        }

    def grade_distribution(self) -> pd.Series:
        if self.frame.empty or "grade" not in self.frame.columns:
            return pd.Series(dtype=int)
        return self.frame["grade"].astype(str).value_counts().sort_index()

    def weekly_trend(self) -> pd.DataFrame:
        if self.frame.empty:
            return pd.DataFrame(columns=["week", "score"])
        frame = self.frame.copy()
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        frame = frame.dropna(subset=["date"])
        if frame.empty:
            return pd.DataFrame(columns=["week", "score"])
        frame["week"] = frame["date"].dt.to_period("W").astype(str)
        score = pd.to_numeric(frame.get("research_score"), errors="coerce")
        trend = frame.assign(research_score=score).groupby("week", as_index=False)["research_score"].mean()
        return trend.rename(columns={"research_score": "score"})
