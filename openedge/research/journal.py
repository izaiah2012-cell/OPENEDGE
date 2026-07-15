from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from datetime import datetime
from pathlib import Path
from typing import Any
import json

import pandas as pd

from openedge.validation.journal import load_entries


@dataclass
class ResearchDay:
    date: str
    morning_bias: str = ""
    morning_confidence: float | int | None = None
    morning_regime: str = ""
    opening_auction_risk: float | int | None = None
    opportunity_score: float | int | None = None
    historical_match: str = ""
    similarity: float | int | None = None
    morning_timestamp: str = ""
    first_hour_direction: str = ""
    close_direction: str = ""
    morning_correct: bool | None = None
    close_correct: bool | None = None
    bias_transition: str = ""
    transition_time: str = ""
    refresh_count: int = 0
    research_score: float | int | None = None
    grade: str = ""
    comments: str = ""
    lessons_learned: str = ""

    @classmethod
    def from_report(cls, report: dict, *, refresh_count: int = 1, comments: str = "", lessons_learned: str = "") -> "ResearchDay":
        historical = report.get("Historical Match", {}) if isinstance(report.get("Historical Match", {}), dict) else {}
        best_match = historical.get("best_match", {}) if isinstance(historical, dict) else {}
        market = report.get("market", {}) if isinstance(report.get("market", {}), dict) else {}
        raw = report.get("Raw Engine Report", {}) if isinstance(report.get("Raw Engine Report", {}), dict) else {}
        raw_market = raw.get("market", {}) if isinstance(raw.get("market", {}), dict) else {}

        morning_bias = report.get("Bias", market.get("bias", raw_market.get("bias", "")))
        morning_confidence = report.get("Confidence", market.get("confidence", raw_market.get("confidence", None)))
        morning_regime = report.get("Market Regime", market.get("market_regime", raw_market.get("market_regime", "")))
        opening_auction_risk = market.get("opening_risk", raw_market.get("opening_risk", report.get("Opening Auction Risk", None)))
        opportunity_score = market.get("opportunity_score", raw_market.get("opportunity_score", report.get("Opportunity Score", None)))
        similarity = best_match.get("similarity", historical.get("average_similarity", None))

        return cls(
            date=str(report.get("Date") or datetime.now().strftime("%Y-%m-%d")),
            morning_bias=str(morning_bias or ""),
            morning_confidence=morning_confidence,
            morning_regime=str(morning_regime or ""),
            opening_auction_risk=opening_auction_risk,
            opportunity_score=opportunity_score,
            historical_match=str(best_match.get("date", "")),
            similarity=similarity,
            morning_timestamp=str(report.get("Timestamp", report.get("Generated Timestamp", ""))),
            first_hour_direction=str(market.get("first_hour_direction", "")),
            close_direction=str(market.get("close_direction", "")),
            morning_correct=market.get("morning_correct"),
            close_correct=market.get("close_correct"),
            bias_transition=str(report.get("Bias Transition", "")),
            transition_time=str(report.get("Transition Time", "")),
            refresh_count=refresh_count,
            research_score=report.get("Research Score", None),
            grade=str(report.get("Grade", "")),
            comments=comments or str(report.get("Research Conclusion", "")),
            lessons_learned=lessons_learned,
        )

    def to_record(self) -> dict[str, Any]:
        record = asdict(self)
        for key in ("morning_confidence", "opening_auction_risk", "opportunity_score", "similarity", "research_score"):
            value = record.get(key)
            record[key] = "" if value in (None, "") else value
        for key in ("morning_correct", "close_correct"):
            value = record.get(key)
            record[key] = "" if value is None else int(bool(value))
        return record


class ResearchJournal:
    def __init__(self, base_dir: Path | None = None):
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).resolve().parents[2]
        self.memory_dir = self.base_dir / "database"
        self.memory_path = self.memory_dir / "research_memory.csv"
        self.reports_dir = self.base_dir / "reports"
        self.legacy_journal = self.base_dir / "research_journal.csv"

    def append_day(self, day: ResearchDay) -> Path:
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        frame = self.load_days()
        row = pd.DataFrame([day.to_record()])
        if frame.empty:
            frame = row
        else:
            frame = pd.concat([frame, row], ignore_index=True)

        frame = frame.drop_duplicates(subset=["date"], keep="last")
        frame.to_csv(self.memory_path, index=False)
        return self.memory_path

    def load_days(self) -> pd.DataFrame:
        if self.memory_path.exists():
            try:
                frame = pd.read_csv(self.memory_path)
            except Exception:
                frame = pd.DataFrame()
        else:
            frame = pd.DataFrame()

        if frame.empty and self.reports_dir.exists():
            frame = self._backfill_from_reports()

        if frame.empty and self.legacy_journal.exists():
            try:
                legacy = load_entries(self.legacy_journal)
                frame = self._convert_legacy_journal(legacy)
            except Exception:
                frame = pd.DataFrame()

        return self._normalize_frame(frame)

    def search(
        self,
        query: str = "",
        *,
        grade: str = "",
        bias: str = "",
        start_date: str = "",
        end_date: str = "",
    ) -> pd.DataFrame:
        frame = self.load_days()
        if frame.empty:
            return frame

        if query:
            needle = query.lower()
            mask = frame.apply(lambda row: needle in " ".join(str(value).lower() for value in row.values), axis=1)
            frame = frame[mask]
        if grade:
            frame = frame[frame["grade"].astype(str).str.upper() == grade.upper()]
        if bias:
            frame = frame[frame["morning_bias"].astype(str).str.upper() == bias.upper()]
        if start_date:
            frame = frame[frame["date"].astype(str) >= start_date]
        if end_date:
            frame = frame[frame["date"].astype(str) <= end_date]
        return frame

    def export_csv(self, path: Path | None = None) -> Path:
        path = Path(path) if path else self.memory_dir / "research_memory_export.csv"
        frame = self.load_days()
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(path, index=False)
        return path

    def export_json(self, path: Path | None = None) -> Path:
        path = Path(path) if path else self.memory_dir / "research_memory_export.json"
        frame = self.load_days()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(frame.to_dict(orient="records"), indent=2), encoding="utf-8")
        return path

    def _backfill_from_reports(self) -> pd.DataFrame:
        rows: list[dict[str, Any]] = []
        for report_file in sorted(self.reports_dir.glob("*.json")):
            try:
                report = json.loads(report_file.read_text(encoding="utf-8"))
            except Exception:
                continue
            date_value = str(report.get("Date") or report_file.stem)
            day = ResearchDay.from_report(report)
            day.date = date_value
            rows.append(day.to_record())
        return pd.DataFrame(rows)

    def _convert_legacy_journal(self, frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty:
            return frame
        rows = []
        for _, row in frame.iterrows():
            rows.append(
                ResearchDay(
                    date=str(row.get("date", "")),
                    morning_bias=str(row.get("bias", "")),
                    morning_confidence=row.get("confidence", ""),
                    morning_regime=str(row.get("market_regime", "")),
                    morning_correct=self._truthy(row.get("correct")),
                    comments=str(row.get("notes", "")),
                ).to_record()
            )
        return pd.DataFrame(rows)

    def _normalize_frame(self, frame: pd.DataFrame) -> pd.DataFrame:
        columns = [field.name for field in fields(ResearchDay)]
        if frame.empty:
            return pd.DataFrame(columns=columns)
        for column in columns:
            if column not in frame.columns:
                frame[column] = pd.NA
        frame = frame[columns].copy()
        frame = frame.sort_values("date", ascending=False, kind="stable")
        return frame.reset_index(drop=True)

    @staticmethod
    def _truthy(value: Any) -> bool | None:
        if value is None:
            return None
        try:
            if pd.isna(value):
                return None
        except Exception:
            pass
        if value == "":
            return None
        try:
            return bool(int(float(value)))
        except Exception:
            return bool(value)
