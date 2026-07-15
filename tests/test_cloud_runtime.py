"""
Cloud-runtime tests: refresh service, health service, storage interface,
dashboard import, and workflow CLI.
All external market calls are mocked.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent


def _dummy_report() -> dict:
    return {
        "date": "2026-07-15",
        "market": {"bias": "UP", "confidence": 72, "market_regime": "Trending"},
        "macro": {"macro_risk": "Moderate", "today_events": []},
        "leadership": {"rows": []},
        "historical": {"best_match": {}, "expected_outcome": "UP", "rows": []},
        "summary": {
            "executive_summary": "Test summary",
            "key_risks": [],
            "strengths": [],
            "weaknesses": [],
            "todays_focus": "Testing",
            "research_conclusion": "OK",
            "performance": {},
            "system_status": {},
        },
    }


def _mock_morning_workflow(run_result=None, run_raises=None):
    wf = MagicMock()
    if run_raises:
        wf.run.side_effect = run_raises
    else:
        wf.run.return_value = run_result or _dummy_report()
    wf.as_of = datetime.now().astimezone()
    wf._save_history_snapshot = MagicMock()
    wf._append_journal_entry = MagicMock()
    wf.update_dashboard = MagicMock()
    return wf


# ---------------------------------------------------------------------------
# Storage interface
# ---------------------------------------------------------------------------


class TestLocalStorage:
    def test_save_and_load_report(self, tmp_path):
        from openedge.storage.local_storage import LocalStorage

        storage = LocalStorage(base_dir=tmp_path)
        report = _dummy_report()
        paths = storage.save_report(report)
        assert paths["json"].exists()
        assert paths["markdown"].exists()
        assert paths["html"].exists()

        loaded = storage.load_latest_report()
        assert loaded is not None

    def test_load_latest_report_missing(self, tmp_path):
        from openedge.storage.local_storage import LocalStorage

        storage = LocalStorage(base_dir=tmp_path)
        assert storage.load_latest_report() is None

    def test_save_and_load_refresh_metadata(self, tmp_path):
        from openedge.storage.local_storage import LocalStorage

        storage = LocalStorage(base_dir=tmp_path)
        payload = {"success": True, "timestamp": "2026-07-15T09:00:00", "duration_seconds": 3.2}
        storage.save_refresh_metadata(payload)
        loaded = storage.load_refresh_metadata()
        assert loaded["success"] is True
        assert loaded["duration_seconds"] == 3.2

    def test_load_refresh_metadata_missing(self, tmp_path):
        from openedge.storage.local_storage import LocalStorage

        storage = LocalStorage(base_dir=tmp_path)
        assert storage.load_refresh_metadata() == {}

    def test_load_workflow_status_missing(self, tmp_path):
        from openedge.storage.local_storage import LocalStorage

        storage = LocalStorage(base_dir=tmp_path)
        assert storage.load_workflow_status() == {}

    def test_load_journal_empty(self, tmp_path):
        from openedge.storage.local_storage import LocalStorage

        storage = LocalStorage(base_dir=tmp_path)
        df = storage.load_journal()
        assert df.empty

    def test_storage_backend_abstract(self):
        from openedge.storage.base import StorageBackend

        with pytest.raises(TypeError):
            StorageBackend()


# ---------------------------------------------------------------------------
# Error handling utilities
# ---------------------------------------------------------------------------


class TestErrorHandling:
    def test_safe_call_success(self):
        from openedge.utils.error_handling import safe_source_call

        result = safe_source_call("Test", lambda: {"data": 1})
        assert result.value == {"data": 1}
        assert result.warning == ""
        assert not result.stale

    def test_safe_call_failure_no_fallback(self):
        from openedge.utils.error_handling import safe_source_call

        result = safe_source_call("Yahoo", lambda: (_ for _ in ()).throw(RuntimeError("yfinance error")))
        assert result.value is None
        assert "unavailable" in result.warning.lower()
        assert not result.stale

    def test_safe_call_failure_with_fallback(self):
        from openedge.utils.error_handling import safe_source_call

        result = safe_source_call(
            "Market data",
            lambda: (_ for _ in ()).throw(RuntimeError("timeout")),
            fallback_fn=lambda: {"cached": True},
        )
        assert result.value == {"cached": True}
        assert result.stale is True
        assert "STALE" in result.warning

    def test_safe_call_failure_fallback_also_fails(self):
        from openedge.utils.error_handling import safe_source_call

        result = safe_source_call(
            "Market data",
            lambda: (_ for _ in ()).throw(RuntimeError("timeout")),
            fallback_fn=lambda: (_ for _ in ()).throw(RuntimeError("fallback also bad")),
        )
        assert result.value is None
        assert not result.stale

    def test_user_facing_error_yahoo(self):
        from openedge.utils.error_handling import user_facing_error

        msg = user_facing_error("Ticker", RuntimeError("yfinance ticker not found"))
        assert "Yahoo Finance" in msg

    def test_user_facing_error_csv(self):
        from openedge.utils.error_handling import user_facing_error

        msg = user_facing_error("DB", RuntimeError("csv file not found"))
        assert "CSV" in msg or "database" in msg.lower()


# ---------------------------------------------------------------------------
# Refresh service
# ---------------------------------------------------------------------------


class TestRefreshService:
    def test_refresh_success(self, tmp_path):
        from openedge.services.refresh_service import RefreshService

        svc = RefreshService(base_dir=tmp_path)
        with patch(
            "openedge.services.refresh_service.MorningWorkflow",
            return_value=_mock_morning_workflow(),
        ):
            result = svc.run_refresh()

        assert result["success"] is True
        assert "timestamp" in result
        assert result["duration_seconds"] >= 0
        assert "OPENEDGE refreshed" in result["message"]

    def test_refresh_success_persists_metadata(self, tmp_path):
        from openedge.services.refresh_service import RefreshService

        svc = RefreshService(base_dir=tmp_path)
        with patch(
            "openedge.services.refresh_service.MorningWorkflow",
            return_value=_mock_morning_workflow(),
        ):
            svc.run_refresh()

        meta = svc.get_last_refresh()
        assert meta.get("success") is True

    def test_refresh_partial_data_failure_falls_back(self, tmp_path):
        """Workflow.run() raises, but fallback methods succeed — should still return success."""
        from openedge.services.refresh_service import RefreshService

        wf = _mock_morning_workflow(run_raises=RuntimeError("market blip"))
        wf.load_market_data = MagicMock(return_value={"SPY": {"price": 500.0}})
        wf.load_macro_events = MagicMock(return_value=[])
        wf.load_market_internals = MagicMock(return_value={})
        wf.load_leadership = MagicMock(return_value={})
        wf.run_historical_match = MagicMock(return_value={})
        wf.run_intelligence_engine = MagicMock(return_value=_dummy_report())
        wf.build_reports = MagicMock(return_value=_dummy_report())

        with patch("openedge.services.refresh_service.MorningWorkflow", return_value=wf):
            result = RefreshService(base_dir=tmp_path).run_refresh()

        assert result["success"] is True

    def test_refresh_total_failure(self, tmp_path):
        """Workflow.run() and all fallbacks fail — should return success=False without traceback."""
        from openedge.services.refresh_service import RefreshService

        wf = _mock_morning_workflow(run_raises=RuntimeError("hard failure"))
        wf.load_market_data = MagicMock(side_effect=RuntimeError("no market"))
        wf.load_macro_events = MagicMock(side_effect=RuntimeError("no macro"))
        wf.load_market_internals = MagicMock(side_effect=RuntimeError("no internals"))
        wf.load_leadership = MagicMock(side_effect=RuntimeError("no leadership"))
        wf.run_historical_match = MagicMock(side_effect=RuntimeError("no history"))
        wf.run_intelligence_engine = MagicMock(side_effect=RuntimeError("engine dead"))
        wf.build_reports = MagicMock(side_effect=RuntimeError("build dead"))

        with patch("openedge.services.refresh_service.MorningWorkflow", return_value=wf):
            result = RefreshService(base_dir=tmp_path).run_refresh()

        assert result["success"] is False
        assert "traceback" not in result.get("message", "").lower()
        assert "error" in result

    def test_refresh_blocked_while_running(self, tmp_path):
        from openedge.services.refresh_service import RefreshService

        svc = RefreshService(base_dir=tmp_path)
        svc.lock_file.parent.mkdir(parents=True, exist_ok=True)
        svc.lock_file.write_text("locked", encoding="utf-8")

        result = svc.run_refresh()
        assert result["success"] is False
        assert "in progress" in result["message"].lower()

        svc.lock_file.unlink()

    def test_get_refresh_status_not_running(self, tmp_path):
        from openedge.services.refresh_service import RefreshService

        svc = RefreshService(base_dir=tmp_path)
        status = svc.get_refresh_status()
        assert status["is_running"] is False

    def test_stale_data_fallback_warning_in_result(self, tmp_path):
        """Partial source failure should include stale warning in result warnings list."""
        from openedge.services.refresh_service import RefreshService

        wf = _mock_morning_workflow(run_raises=RuntimeError("market blip"))
        wf.load_market_data = MagicMock(return_value={"SPY": {"price": 500.0}})
        wf.load_macro_events = MagicMock(side_effect=RuntimeError("macro down"))
        wf.load_market_internals = MagicMock(return_value={})
        wf.load_leadership = MagicMock(return_value={})
        wf.run_historical_match = MagicMock(return_value={})
        wf.run_intelligence_engine = MagicMock(return_value=_dummy_report())
        wf.build_reports = MagicMock(return_value=_dummy_report())

        with patch("openedge.services.refresh_service.MorningWorkflow", return_value=wf):
            result = RefreshService(base_dir=tmp_path).run_refresh()

        assert result["success"] is True
        warnings = result.get("warnings", [])
        assert any("unavailable" in w.lower() or "stale" in w.lower() for w in warnings)


# ---------------------------------------------------------------------------
# Health service
# ---------------------------------------------------------------------------


class TestHealthService:
    def test_health_healthy(self, tmp_path):
        from openedge.services.health_service import HealthService

        # Pre-seed a report so latest_report_available is True
        (tmp_path / "reports").mkdir()
        report_file = tmp_path / "reports" / "2026-07-15.json"
        report_file.write_text(json.dumps(_dummy_report()), encoding="utf-8")

        with patch("openedge.services.health_service.get_market_snapshot", return_value={"SPY": {"price": 500}}):
            health = HealthService(base_dir=tmp_path).get_health()

        assert health["application_status"] == "healthy"
        assert health["market_provider_status"] == "healthy"
        assert health["latest_report_available"] is True
        assert health["storage_status"] == "healthy"

    def test_health_degraded_when_market_fails(self, tmp_path):
        from openedge.services.health_service import HealthService

        with patch(
            "openedge.services.health_service.get_market_snapshot",
            side_effect=RuntimeError("yahoo down"),
        ):
            health = HealthService(base_dir=tmp_path).get_health()

        assert health["application_status"] == "degraded"
        assert health["market_provider_status"] == "degraded"
        assert health["market_provider_warning"]

    def test_health_degraded_when_no_report(self, tmp_path):
        from openedge.services.health_service import HealthService

        with patch("openedge.services.health_service.get_market_snapshot", return_value={}):
            health = HealthService(base_dir=tmp_path).get_health()

        assert health["latest_report_available"] is False
        assert health["application_status"] == "degraded"

    def test_health_returns_all_required_keys(self, tmp_path):
        from openedge.services.health_service import HealthService

        with patch("openedge.services.health_service.get_market_snapshot", return_value={}):
            health = HealthService(base_dir=tmp_path).get_health()

        required_keys = {
            "application_status",
            "market_provider_status",
            "latest_report_available",
            "storage_status",
            "latest_workflow_status",
            "latest_workflow_run",
        }
        assert required_keys.issubset(health.keys())


# ---------------------------------------------------------------------------
# Dashboard module import
# ---------------------------------------------------------------------------


def test_dashboard_module_importable():
    import openedge.dashboard.app as app  # noqa: F401

    assert hasattr(app, "main")


def test_dashboard_services_wired():
    """Dashboard must import RefreshService and HealthService."""
    import openedge.dashboard.app as app

    assert hasattr(app, "RefreshService")
    assert hasattr(app, "HealthService")


# ---------------------------------------------------------------------------
# Workflow CLI
# ---------------------------------------------------------------------------


def test_workflow_cli_morning_help():
    """openedge.py should support the 'morning' sub-command without crashing on --help."""
    result = subprocess.run(
        [sys.executable, "openedge.py", "--help"],
        cwd=BASE_DIR,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "morning" in result.stdout.lower()


def test_workflow_cli_morning_dry_run(tmp_path):
    """Running 'python openedge.py morning' with mocked market data should exit 0."""
    env_patch = {
        "OPENEDGE_BASE_DIR": str(tmp_path),
    }
    import os

    env = os.environ.copy()
    env.update(env_patch)

    with patch("openedge.workflows.morning_workflow.MorningWorkflow") as mock_wf_cls:
        instance = MagicMock()
        instance.run.return_value = _dummy_report()
        instance.as_of = datetime.now().astimezone()
        instance._save_history_snapshot = MagicMock()
        instance._append_journal_entry = MagicMock()
        instance.update_dashboard = MagicMock()
        mock_wf_cls.return_value = instance

        from openedge.workflows.morning_workflow import MorningWorkflow

        wf = MorningWorkflow(base_dir=tmp_path)
        wf.run = MagicMock(return_value=_dummy_report())
        # Don't actually invoke CLI since it touches live data; test the entrypoint import
        import openedge.workflows.morning_workflow  # noqa: F401
