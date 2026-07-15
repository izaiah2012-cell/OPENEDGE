from __future__ import annotations

import traceback
import sys
from datetime import datetime
from pathlib import Path
from time import perf_counter

from openedge.storage import LocalStorage
from openedge.utils.error_handling import safe_source_call
from openedge.workflows.morning_workflow import MorningWorkflow


class RefreshService:
    def __init__(self, base_dir: Path | None = None):
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).resolve().parents[2]
        self.storage = LocalStorage(self.base_dir)
        self.lock_file = self.base_dir / "database" / "refresh.lock"
        
        # Initialize metadata if it doesn't exist
        self._initialize_metadata_if_missing()

    def _initialize_metadata_if_missing(self) -> None:
        """Initialize refresh metadata file if it doesn't exist."""
        metadata = self.storage.load_refresh_metadata()
        if not metadata:
            default_metadata = {
                "success": None,
                "timestamp": datetime.now().astimezone().isoformat(),
                "last_successful_refresh": "Never",
                "duration_seconds": 0,
                "message": "No refresh run yet",
                "warnings": [],
            }
            self.storage.save_refresh_metadata(default_metadata)

    def run_refresh(self) -> dict:
        if self.lock_file.exists():
            status = self.get_refresh_status()
            return {
                "success": False,
                "timestamp": datetime.now().astimezone().isoformat(),
                "duration_seconds": 0.0,
                "message": "Refresh already in progress",
                "status": status,
            }

        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        self.lock_file.write_text(datetime.now().astimezone().isoformat(), encoding="utf-8")

        started_at = datetime.now().astimezone()
        timer_start = perf_counter()
        warnings: list[str] = []

        try:
            workflow = MorningWorkflow(base_dir=self.base_dir, as_of=started_at)
            try:
                report = workflow.run()
                report_paths = self.storage.save_report(report, as_of=workflow.as_of)
                workflow._save_history_snapshot(report)
                workflow._append_journal_entry(report)
                workflow._ended_at = datetime.now().astimezone()
                workflow._duration_seconds = round(perf_counter() - timer_start, 2)
                workflow.update_dashboard(report_paths=report_paths, success=True)
            except Exception:
                self._run_fallback_refresh(workflow=workflow, warnings=warnings)

            duration = round(perf_counter() - timer_start, 2)
            payload = {
                "success": True,
                "timestamp": datetime.now().astimezone().isoformat(),
                "last_successful_refresh": datetime.now().astimezone().isoformat(),
                "duration_seconds": duration,
                "message": "OPENEDGE refreshed successfully",
                "warnings": warnings,
                "report_files": self.storage.load_workflow_status().get("report_files", {}),
            }
            self.storage.save_refresh_metadata(payload)
            return payload
        except Exception:
            duration = round(perf_counter() - timer_start, 2)
            exc_type, exc_value, _ = sys.exc_info()
            payload = {
                "success": False,
                "timestamp": datetime.now().astimezone().isoformat(),
                "duration_seconds": duration,
                "message": "Refresh failed. The previous report is still available.",
                "error": "".join(traceback.format_exception_only(exc_type or Exception, exc_value or Exception("Unknown refresh failure"))).strip(),
            }
            self.storage.save_refresh_metadata(payload)
            return payload
        finally:
            if self.lock_file.exists():
                self.lock_file.unlink(missing_ok=True)

    def get_last_refresh(self) -> dict:
        return self.storage.load_refresh_metadata()

    def get_refresh_status(self) -> dict:
        payload = self.storage.load_refresh_metadata()
        return {
            "is_running": self.lock_file.exists(),
            "last_successful_refresh": payload.get("last_successful_refresh", "N/A"),
            "last_duration_seconds": payload.get("duration_seconds", "N/A"),
            "last_message": payload.get("message", "N/A"),
        }

    def _run_fallback_refresh(self, *, workflow: MorningWorkflow, warnings: list[str]) -> None:
        latest_report = self.storage.load_latest_report() or {}
        engine_payload = latest_report.get("Raw Engine Report", {}) if isinstance(latest_report, dict) else {}

        market_result = safe_source_call(
            "Market data",
            workflow.load_market_data,
            fallback_fn=lambda: _market_snapshot_from_report(engine_payload),
        )
        macro_result = safe_source_call(
            "Macro events",
            workflow.load_macro_events,
            fallback_fn=lambda: latest_report.get("Macro Events", []),
        )
        internals_result = safe_source_call(
            "Market internals",
            workflow.load_market_internals,
            fallback_fn=lambda: _internals_from_report(latest_report),
        )
        leadership_result = safe_source_call(
            "Leadership data",
            workflow.load_leadership,
            fallback_fn=lambda: _leadership_from_report(latest_report),
        )
        historical_result = safe_source_call(
            "Historical matches",
            workflow.run_historical_match,
            fallback_fn=lambda: latest_report.get("Historical Match", {}),
        )

        for result in (market_result, macro_result, internals_result, leadership_result, historical_result):
            if result.warning:
                warnings.append(result.warning)

        market_snapshot = market_result.value
        macro_events = macro_result.value or []
        market_internals = internals_result.value or {}
        leadership = leadership_result.value or {}
        historical_matches = historical_result.value or {}

        if market_snapshot is None or market_internals is None:
            raise RuntimeError("Unable to refresh: no live or cached market payload available.")

        intelligence_report = workflow.run_intelligence_engine(
            market_snapshot=market_snapshot,
            market_internals=market_internals,
            leadership=leadership,
            macro_events=macro_events,
            historical_matches=historical_matches,
        )

        report = workflow.build_reports(
            intelligence_report=intelligence_report,
            market_internals=market_internals,
            leadership=leadership,
            macro_events=macro_events,
            historical_match=historical_matches,
        )

        report_paths = self.storage.save_report(report, as_of=workflow.as_of)
        workflow._save_history_snapshot(report)
        workflow._append_journal_entry(report)
        workflow._ended_at = datetime.now().astimezone()
        workflow._duration_seconds = 0.0
        workflow.update_dashboard(report_paths=report_paths, success=True)


def _internals_from_report(report: dict) -> dict:
    raw = report.get("Market Internals", [])
    if isinstance(raw, dict):
        return raw

    converted = {}
    for row in raw or []:
        asset = row.get("Asset")
        if not asset:
            continue
        converted[asset] = {
            "price": _coerce_float(row.get("Price")),
            "daily_change_percent": _coerce_percent(row.get("Daily %")),
            "direction": row.get("Direction", "N/A"),
        }
    return converted


def _market_snapshot_from_report(engine_payload: dict) -> dict:
    market = engine_payload.get("market", {}) if isinstance(engine_payload, dict) else {}
    internals_rows = market.get("internals_rows", [])
    snapshot = {}
    for row in internals_rows:
        symbol = row.get("Asset")
        if not symbol:
            continue
        snapshot[symbol] = {
            "price": _coerce_float(row.get("Price")),
            "change": _coerce_percent(row.get("Daily %")),
        }
    return snapshot


def _leadership_from_report(report: dict) -> dict:
    raw = report.get("Leadership", {})
    if isinstance(raw, dict) and raw:
        if "rows" in raw:
            rows = raw.get("rows", [])
            converted = {}
            for row in rows:
                sector = row.get("Sector")
                if not sector:
                    continue
                converted[sector] = {
                    "score": _coerce_float(row.get("Score (%)")),
                    "status": row.get("Status", "Neutral"),
                }
            return converted
        return raw
    return {}


def _coerce_float(value):
    try:
        if value in (None, "", "N/A"):
            return None
        if isinstance(value, str):
            value = value.replace(",", "")
        return float(value)
    except Exception:
        return None


def _coerce_percent(value):
    try:
        if value in (None, "", "N/A"):
            return None
        if isinstance(value, str):
            value = value.replace("%", "")
        return float(value)
    except Exception:
        return None
