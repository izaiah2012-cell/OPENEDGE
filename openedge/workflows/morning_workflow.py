from __future__ import annotations

import json
import traceback
from datetime import datetime
from pathlib import Path

import pandas as pd

from openedge.data.market import get_market_snapshot
from openedge.engines.history_engine import get_historical_matches
from openedge.engines.intelligence import IntelligenceEngine
from openedge.engines.macro_engine import get_macro_events
from openedge.engines.market_internals import get_market_internals
from openedge.models.leadership_engine import evaluate_sector_leadership
from openedge.validation.journal import append_journal_entry
from openedge.workflows.exporters import HTMLExporter, JSONExporter, MarkdownExporter
from openedge.workflows.report_builder import ReportBuilder
from openedge.workflows.workflow_logger import WorkflowLogger


class MorningWorkflow:
    """Morning automation pipeline for generating OPENEDGE daily research artifacts."""

    def __init__(self, base_dir: Path | None = None, as_of: datetime | None = None):
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).resolve().parents[2]
        self.as_of = as_of or datetime.now().astimezone()

        self.csv_file = self.base_dir / "openedge_db.csv"
        self.reports_dir = self.base_dir / "reports"
        self.history_dir = self.base_dir / "database" / "history"
        self.logs_dir = self.base_dir / "logs"
        self.status_file = self.base_dir / "database" / "workflow_status.json"
        self.journal_file = self.base_dir / "research_journal.csv"
        self.logger = WorkflowLogger(self.logs_dir)
        self.report_builder = ReportBuilder()
        self.markdown_exporter = MarkdownExporter()
        self.json_exporter = JSONExporter()
        self.html_exporter = HTMLExporter()

        self._started_at: datetime | None = None
        self._ended_at: datetime | None = None
        self._duration_seconds: float = 0.0
        self._sources: list[str] = []

    def load_market_data(self):
        self._sources.append("openedge.data.market.get_market_snapshot")
        return get_market_snapshot()

    def load_macro_events(self):
        self._sources.append("openedge.engines.macro_engine.get_macro_events")
        return get_macro_events()

    def load_market_internals(self):
        self._sources.append("openedge.engines.market_internals.get_market_internals")
        return get_market_internals()

    def load_leadership(self):
        self._sources.append("openedge.models.leadership_engine.evaluate_sector_leadership")
        return evaluate_sector_leadership()

    def run_historical_match(self):
        self._sources.append("openedge.engines.history_engine.get_historical_matches")
        return get_historical_matches(self.csv_file, top_n=5)

    def run_intelligence_engine(self, market_snapshot, market_internals, leadership, macro_events, historical_matches):
        history_df = self._load_signal_history()
        latest_signal = self._load_latest_signal(history_df)

        engine = IntelligenceEngine(
            latest_signal=latest_signal,
            market_internals=market_internals,
            leadership=leadership,
            macro_events=macro_events,
            historical_matches=historical_matches,
            market_snapshot=market_snapshot,
            history_df=history_df,
        )
        return engine.build_report()

    def build_reports(self, intelligence_report, market_internals, leadership, macro_events, historical_match):
        return self.report_builder.build(
            as_of=self.as_of,
            intelligence_report=intelligence_report,
            market_internals=market_internals,
            macro_events=macro_events,
            leadership=leadership,
            historical_match=historical_match,
        )

    def export_reports(self, report):
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        date_slug = self.as_of.strftime("%Y-%m-%d")

        markdown_path = self.reports_dir / f"{date_slug}.md"
        json_path = self.reports_dir / f"{date_slug}.json"
        html_path = self.reports_dir / f"{date_slug}.html"

        self.markdown_exporter.export(report, markdown_path)
        self.json_exporter.export(report, json_path)
        self.html_exporter.export(report, html_path)

        return {"markdown": markdown_path, "json": json_path, "html": html_path}

    def update_dashboard(self, report_paths, success=True):
        self.status_file.parent.mkdir(parents=True, exist_ok=True)
        last_report = str(report_paths.get("markdown")) if report_paths else "N/A"

        payload = {
            "last_workflow_run": self._ended_at.isoformat() if self._ended_at else "N/A",
            "workflow_duration_seconds": round(self._duration_seconds, 2),
            "last_report_generated": last_report,
            "research_status": "SUCCESS" if success else "FAILURE",
            "research_generated": bool(success and report_paths),
            "report_files": {k: str(v) for k, v in (report_paths or {}).items()},
            "status": "SUCCESS" if success else "FAILURE",
        }
        self.status_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    def run(self):
        self._started_at = datetime.now().astimezone()
        report_paths = None
        success = False
        error_text = ""

        try:
            market_snapshot = self.load_market_data()
            macro_events = self.load_macro_events()
            market_internals = self.load_market_internals()
            leadership = self.load_leadership()
            historical_matches = self.run_historical_match()
            intelligence_report = self.run_intelligence_engine(
                market_snapshot=market_snapshot,
                market_internals=market_internals,
                leadership=leadership,
                macro_events=macro_events,
                historical_matches=historical_matches,
            )
            report = self.build_reports(
                intelligence_report=intelligence_report,
                market_internals=market_internals,
                leadership=leadership,
                macro_events=macro_events,
                historical_match=historical_matches,
            )
            report_paths = self.export_reports(report)
            self._save_history_snapshot(report)
            self._append_journal_entry(report)
            success = True
            return report
        except Exception as exc:
            error_text = "".join(traceback.format_exception_only(type(exc), exc)).strip()
            raise
        finally:
            self._ended_at = datetime.now().astimezone()
            self._duration_seconds = (self._ended_at - self._started_at).total_seconds() if self._started_at else 0.0
            self.update_dashboard(report_paths=report_paths, success=success)
            self._write_execution_log(success=success, error_text=error_text)

    def _save_history_snapshot(self, report):
        self.history_dir.mkdir(parents=True, exist_ok=True)
        path = self.history_dir / f"{self.as_of.strftime('%Y-%m-%d')}.json"
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return path

    def _write_execution_log(self, success, error_text=""):
        return self.logger.write(
            as_of=self.as_of,
            start_time=self._started_at or self.as_of,
            finish_time=self._ended_at or self.as_of,
            duration_seconds=self._duration_seconds,
            data_sources=self._sources,
            export_status="SUCCESS" if success else "FAILURE",
            errors=error_text,
        )

    def _append_journal_entry(self, report):
        outcome = report.get("Raw Engine Report", {}).get("latest_signal", {}).get("Actual", "N/A")
        bias = report.get("Bias", "N/A")
        confidence = report.get("Confidence", "")
        regime = report.get("Market Regime", "Unknown")

        correct_flag = report.get("Raw Engine Report", {}).get("latest_signal", {}).get("Correct")
        if correct_flag in (None, "", "N/A"):
            if outcome in ("UP", "DOWN", "NEUTRAL") and bias in ("UP", "DOWN", "NEUTRAL", "BULLISH", "BEARISH"):
                bias_map = {"BULLISH": "UP", "BEARISH": "DOWN", "NEUTRAL": "NEUTRAL", "UP": "UP", "DOWN": "DOWN"}
                correct_flag = 1 if bias_map.get(str(bias).upper(), str(bias).upper()) == str(outcome).upper() else 0
            else:
                correct_flag = ""

        append_journal_entry(
            self.journal_file,
            {
                "date": report.get("Date", self.as_of.strftime("%Y-%m-%d")),
                "market_regime": regime,
                "bias": bias,
                "confidence": confidence,
                "actual": outcome,
                "correct": correct_flag,
                "notes": "source=morning_workflow",
            },
        )

    def _load_signal_history(self):
        if not self.csv_file.exists():
            return None

        try:
            df = pd.read_csv(self.csv_file)
        except Exception:
            return None

        if df.empty:
            return None

        return df

    @staticmethod
    def _load_latest_signal(history_df):
        if not isinstance(history_df, pd.DataFrame) or history_df.empty:
            return None
        return history_df.iloc[-1].to_dict()

    # Compatibility shim for older callers/tests.
    def run_intelligence(self, market_snapshot, market_internals, leadership, macro_events, historical_matches):
        return self.run_intelligence_engine(
            market_snapshot=market_snapshot,
            market_internals=market_internals,
            leadership=leadership,
            macro_events=macro_events,
            historical_matches=historical_matches,
        )
