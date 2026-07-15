from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path

from openedge.services import health_service as health_module
from openedge.storage.base import StorageBackend
from openedge.storage.local_storage import LocalStorage
from openedge.utils.error_handling import safe_source_call


def _load_openedge_cli_module():
    module_path = Path(__file__).resolve().parents[1] / "openedge.py"
    spec = importlib.util.spec_from_file_location("openedge_cli_cloud_test", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeStorage:
    def __init__(self, base_dir):
        self.base_dir = base_dir

    def load_latest_report(self):
        return {"ok": True}

    def load_workflow_status(self):
        return {"research_status": "SUCCESS", "last_workflow_run": "2026-07-15T00:00:00+00:00"}

    def save_refresh_metadata(self, payload):
        path = self.base_dir / "database" / "refresh_metadata.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}", encoding="utf-8")
        return path


def test_stale_data_fallback_result():
    result = safe_source_call(
        "Yahoo market data",
        lambda: (_ for _ in ()).throw(RuntimeError("ticker failed")),
        fallback_fn=lambda: {"cached": True},
    )

    assert result.stale is True
    assert result.value == {"cached": True}
    assert "STALE" in result.warning


def test_health_service_reports_healthy(tmp_path, monkeypatch):
    monkeypatch.setattr(health_module, "LocalStorage", _FakeStorage)
    monkeypatch.setattr(health_module, "get_market_snapshot", lambda: {"SPY": {"price": 500}})

    health = health_module.HealthService(base_dir=tmp_path).get_health()

    assert health["application_status"] == "healthy"
    assert health["latest_report_available"] is True


def test_storage_interface_and_local_backend(tmp_path):
    storage = LocalStorage(base_dir=tmp_path)
    assert isinstance(storage, StorageBackend)

    report = {
        "Date": "2026-07-15",
        "Market Regime": "Bull",
        "Raw Engine Report": {"summary": {}},
        "Market Internals": [],
        "Leadership": {},
        "Macro Events": [],
        "Historical Match": {},
    }
    paths = storage.save_report(report)
    assert paths["json"].exists()

    entry_path = storage.save_journal_entry(
        {
            "date": "2026-07-15",
            "market_regime": "Bull",
            "bias": "UP",
            "confidence": 80,
            "actual": "UP",
            "correct": 1,
            "notes": "test",
        }
    )
    assert entry_path.exists()
    assert not storage.load_journal().empty


def test_dashboard_module_imports():
    module = importlib.import_module("openedge.dashboard.app")
    assert hasattr(module, "main")


def test_workflow_command_morning(monkeypatch):
    cli = _load_openedge_cli_module()

    called = {"run": 0, "open": 0}

    class _FakeWorkflow:
        def run(self):
            called["run"] += 1
            return {}

    monkeypatch.setattr(cli, "MorningWorkflow", lambda: _FakeWorkflow())
    monkeypatch.setattr(cli, "open_latest_morning_report", lambda: called.__setitem__("open", called["open"] + 1))
    monkeypatch.setattr(cli.sys, "argv", ["openedge.py", "morning"])

    cli.main()

    assert called["run"] == 1
    assert called["open"] == 1
