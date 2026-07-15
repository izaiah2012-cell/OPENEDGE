from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4

from openedge.research.grading import ResearchGrader
from openedge.research.journal import ResearchJournal
from openedge.research.statistics import ResearchStatistics


@dataclass
class ResearchReviewer:
    base_dir: Path

    def __post_init__(self):
        self.base_dir = Path(self.base_dir)
        self.reports_dir = self.base_dir / "reports"
        self.reviews_dir = self.reports_dir / "reviews"
        self.journal = ResearchJournal(self.base_dir)
        self.grader = ResearchGrader()

    def maybe_generate_reviews(self, *, as_of: datetime, report: dict) -> list[Path]:
        outputs: list[Path] = []
        frame = self.journal.load_days()
        if frame.empty:
            return outputs

        if as_of.weekday() == 4:
            outputs.append(self._write_review("weekly", as_of, frame, report))
        if self._is_first_trading_day(as_of.date()):
            outputs.append(self._write_review("monthly", as_of, frame, report))
        return [path for path in outputs if path is not None]

    def _write_review(self, review_type: str, as_of: datetime, frame, report: dict) -> Path:
        stats = ResearchStatistics(frame)
        summary = stats.summary()
        insights = []
        try:
            from openedge.research.insights import ResearchInsightsEngine

            insights = ResearchInsightsEngine(frame).generate()
        except Exception:
            insights = []

        self.reviews_dir.mkdir(parents=True, exist_ok=True)
        slug = f"{review_type}_{as_of.strftime('%Y-%m-%d')}_{uuid4().hex[:8]}"
        path = self.reviews_dir / f"{slug}.md"
        lines = [
            f"# OPENEDGE {review_type.title()} Review",
            f"Generated: {as_of.isoformat()}",
            "",
            f"- Total Days: {summary.get('total_days', 0)}",
            f"- Average Score: {summary.get('average_score', 0.0)}",
            f"- Average Similarity: {summary.get('average_similarity', 0.0)}",
            f"- Average Confidence: {summary.get('average_confidence', 0.0)}",
            f"- Top Grade: {summary.get('top_grade', 'N/A')}",
            "",
            "## Observations",
        ]
        if insights:
            lines.extend([f"- {item}" for item in insights])
        else:
            lines.append("- No notable observations yet.")
        lines.extend([
            "",
            "## Current Report",
            f"- Bias: {report.get('Bias', 'N/A')}",
            f"- Confidence: {report.get('Confidence', 'N/A')}",
            f"- Regime: {report.get('Market Regime', 'N/A')}",
        ])
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    @staticmethod
    def _is_first_trading_day(day: date) -> bool:
        if day.weekday() >= 5:
            return False
        candidate = day.replace(day=1)
        while candidate.weekday() >= 5:
            candidate = date.fromordinal(candidate.toordinal() + 1)
        return day == candidate
