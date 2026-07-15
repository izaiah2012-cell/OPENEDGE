from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from openedge.validation.journal import append_entry, load_entries
from openedge.workflows.exporters import HTMLExporter, JSONExporter, MarkdownExporter
from .base import StorageBackend


class LocalStorage(StorageBackend):
    def __init__(self, base_dir: Path | None = None):
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).resolve().parents[2]
        self.reports_dir = self.base_dir / "reports"
        self.database_dir = self.base_dir / "database"
        self.journal_path = self.base_dir / "research_journal.csv"
        self.refresh_metadata_path = self.database_dir / "refresh_metadata.json"

        self.markdown_exporter = MarkdownExporter()
        self.json_exporter = JSONExporter()
        self.html_exporter = HTMLExporter()

    def save_report(self, report: dict, *, as_of: datetime | None = None) -> dict[str, Path]:
        run_time = as_of or datetime.now().astimezone()
        date_slug = run_time.strftime("%Y-%m-%d")

        self.reports_dir.mkdir(parents=True, exist_ok=True)

        markdown_path = self.reports_dir / f"{date_slug}.md"
        json_path = self.reports_dir / f"{date_slug}.json"
        html_path = self.reports_dir / f"{date_slug}.html"

        self.markdown_exporter.export(report, markdown_path)
        self.json_exporter.export(report, json_path)
        self.html_exporter.export(report, html_path)

        return {"markdown": markdown_path, "json": json_path, "html": html_path}

    def load_latest_report(self) -> dict | None:
        if not self.reports_dir.exists():
            return None

        report_files = sorted(self.reports_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
        if not report_files:
            return None

        try:
            return json.loads(report_files[0].read_text(encoding="utf-8"))
        except Exception:
            return None

    def save_journal_entry(self, entry: dict) -> Path:
        return append_entry(self.journal_path, entry)

    def load_journal(self) -> pd.DataFrame:
        return load_entries(self.journal_path)

    def save_refresh_metadata(self, payload: dict) -> Path:
        self.database_dir.mkdir(parents=True, exist_ok=True)
        self.refresh_metadata_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return self.refresh_metadata_path

    def load_refresh_metadata(self) -> dict:
        if not self.refresh_metadata_path.exists():
            return {}
        try:
            return json.loads(self.refresh_metadata_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def load_workflow_status(self) -> dict:
        status_path = self.database_dir / "workflow_status.json"
        if not status_path.exists():
            return {}
        try:
            return json.loads(status_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
