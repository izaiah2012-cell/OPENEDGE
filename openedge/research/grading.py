from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from openedge.research.journal import ResearchDay


@dataclass
class GradeResult:
    score: float
    grade: str
    stars: int
    factors: dict[str, float]


class ResearchGrader:
    """Grade a research day using post-session outcomes and supporting signals."""

    def grade_day(self, day: ResearchDay) -> GradeResult:
        factors = {
            "morning_accuracy": self._morning_accuracy(day),
            "close_accuracy": self._close_accuracy(day),
            "refresh_success": self._refresh_success(day),
            "historical_match_quality": self._historical_match_quality(day),
            "confidence_quality": self._confidence_quality(day),
        }
        score = round(sum(factors.values()) / len(factors), 1)
        stars = self._stars(score)
        return GradeResult(score=score, grade=self._grade(score), stars=stars, factors=factors)

    def grade_frame(self, rows: list[ResearchDay]) -> list[dict[str, Any]]:
        results = []
        for row in rows:
            graded = self.grade_day(row)
            results.append({
                **row.to_record(),
                "research_score": graded.score,
                "grade": graded.grade,
                "stars": graded.stars,
            })
        return results

    @staticmethod
    def _morning_accuracy(day: ResearchDay) -> float:
        if day.morning_correct is True:
            return 100.0
        if day.morning_correct is False:
            return 0.0
        return 50.0

    @staticmethod
    def _close_accuracy(day: ResearchDay) -> float:
        if day.close_correct is True:
            return 100.0
        if day.close_correct is False:
            return 0.0
        return 50.0

    @staticmethod
    def _refresh_success(day: ResearchDay) -> float:
        return 100.0 if int(day.refresh_count or 0) > 0 else 0.0

    @staticmethod
    def _historical_match_quality(day: ResearchDay) -> float:
        try:
            return max(0.0, min(100.0, float(day.similarity or 0.0)))
        except Exception:
            return 0.0

    @staticmethod
    def _confidence_quality(day: ResearchDay) -> float:
        try:
            confidence = float(day.morning_confidence or 0.0)
        except Exception:
            confidence = 0.0
        if 60.0 <= confidence <= 75.0:
            return 100.0
        if 50.0 <= confidence < 60.0 or 75.0 < confidence <= 85.0:
            return 75.0
        if 40.0 <= confidence < 50.0 or 85.0 < confidence <= 90.0:
            return 50.0
        return 25.0

    @staticmethod
    def _grade(score: float) -> str:
        if score >= 90:
            return "A"
        if score >= 80:
            return "B"
        if score >= 70:
            return "C"
        if score >= 60:
            return "D"
        return "F"

    @staticmethod
    def _stars(score: float) -> int:
        if score >= 90:
            return 5
        if score >= 80:
            return 4
        if score >= 70:
            return 3
        if score >= 60:
            return 2
        return 1
