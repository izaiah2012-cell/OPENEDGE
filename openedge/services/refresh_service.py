from __future__ import annotations

import traceback
import sys
from datetime import datetime
from pathlib import Path
from time import perf_counter

from openedge.storage import LocalStorage
from openedge.utils.error_handling import safe_source_call
from openedge.utils.timeline_monitor import BiasTransitionMonitor, DecisionTimeline
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
            report = {}
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
                report = self.storage.load_latest_report() or {}

            duration = round(perf_counter() - timer_start, 2)
            current_bias, current_confidence, current_regime = self._extract_report_signals(report)
            previous_payload = self.storage.load_refresh_metadata()
            previous_bias = previous_payload.get("current_bias", current_bias)
            previous_confidence = self._coerce_float(previous_payload.get("current_confidence", current_confidence))

            self._record_decision_timeline(workflow=workflow, report=report, duration=duration)
            self._record_bias_transition(
                previous_bias=previous_bias,
                current_bias=current_bias,
                previous_confidence=previous_confidence,
                current_confidence=current_confidence,
                reason=self._transition_reason(report),
            )

            payload = {
                "success": True,
                "timestamp": datetime.now().astimezone().isoformat(),
                "last_successful_refresh": datetime.now().astimezone().isoformat(),
                "duration_seconds": duration,
                "message": "OPENEDGE refreshed successfully",
                "warnings": warnings,
                "report_files": self.storage.load_workflow_status().get("report_files", {}),
                "workflow_id": workflow.as_of.strftime("%Y%m%d%H%M%S"),
                "report_id": report.get("Report ID", self._fallback_report_id(workflow.as_of)),
                "current_bias": current_bias,
                "current_confidence": current_confidence,
                "market_regime": current_regime,
                "version": report.get("Version", "v1.1.0"),
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

    def _record_decision_timeline(self, *, workflow: MorningWorkflow, report: dict, duration: float) -> None:
        timeline = DecisionTimeline(self.base_dir / "database" / "decision_timeline.json")
        payload = {
            "workflow_id": workflow.as_of.strftime("%Y%m%d%H%M%S"),
            "report_id": report.get("Report ID", self._fallback_report_id(workflow.as_of)),
            "bias": report.get("Bias", "N/A"),
            "confidence": report.get("Confidence", "N/A"),
            "market_regime": report.get("Market Regime", "N/A"),
            "duration_seconds": duration,
            "status": "READY",
        }
        timeline.add_event("Morning Workflow", payload, timestamp=workflow.as_of)
        timeline.add_event("Latest Refresh", payload, timestamp=datetime.now().astimezone())

    def _record_bias_transition(self, *, previous_bias, current_bias, previous_confidence, current_confidence, reason: str) -> None:
        if current_bias is None:
            return

        monitor = BiasTransitionMonitor(self.base_dir / "database" / "bias_transitions.json")
        monitor.add_transition(
            timestamp=datetime.now().astimezone(),
            bias_before=str(previous_bias or current_bias),
            bias_after=str(current_bias),
            confidence_before=float(previous_confidence or 0.0),
            confidence_after=float(current_confidence or 0.0),
            reason=reason,
        )

    @staticmethod
    def _fallback_report_id(as_of: datetime) -> str:
        return f"OE-{as_of.strftime('%Y%m%d')}-{as_of.strftime('%H%M%S')}"

    @staticmethod
    def _coerce_float(value):
        try:
            if value in (None, "", "N/A"):
                return None
            return float(value)
        except Exception:
            return None

    @staticmethod
    def _extract_report_signals(report: dict) -> tuple[str | None, float | None, str | None]:
        if not isinstance(report, dict):
            return None, None, None

        raw = report.get("Raw Engine Report", {}) if isinstance(report.get("Raw Engine Report", {}), dict) else {}
        market = report.get("market", {}) if isinstance(report.get("market", {}), dict) else {}

        bias = report.get("Bias") or market.get("bias") or raw.get("market", {}).get("bias")
        confidence = report.get("Confidence") or market.get("confidence") or raw.get("market", {}).get("confidence")
        regime = report.get("Market Regime") or market.get("market_regime") or raw.get("market", {}).get("market_regime")
        return (
            str(bias) if bias is not None else None,
            RefreshService._coerce_float(confidence),
            str(regime) if regime is not None else None,
        )

    @staticmethod
    def _transition_reason(report: dict) -> str:
        if not isinstance(report, dict):
            return "Refresh completed"

        summary = report.get("summary", {}) if isinstance(report.get("summary", {}), dict) else {}
        if not summary:
            raw = report.get("Raw Engine Report", {}) if isinstance(report.get("Raw Engine Report", {}), dict) else {}
            summary = raw.get("summary", {}) if isinstance(raw.get("summary", {}), dict) else {}

        risks = summary.get("key_risks", []) if isinstance(summary, dict) else []
        if risks:
            return "; ".join(str(item) for item in risks[:2])
        return str(summary.get("research_conclusion", "Refresh completed") if isinstance(summary, dict) else "Refresh completed")

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
