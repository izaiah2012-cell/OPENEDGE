from __future__ import annotations

from datetime import datetime

from openedge.services import refresh_service as refresh_module


class _FakeStorageSuccess:
    def __init__(self, base_dir):
        self.base_dir = base_dir
        self._refresh = {}
        self._workflow = {}

    def save_report(self, report, *, as_of=None):
        return {
            "markdown": self.base_dir / "reports" / "today.md",
            "json": self.base_dir / "reports" / "today.json",
            "html": self.base_dir / "reports" / "today.html",
        }

    def save_refresh_metadata(self, payload):
        self._refresh = payload
        return self.base_dir / "database" / "refresh_metadata.json"

    def load_refresh_metadata(self):
        return self._refresh

    def load_workflow_status(self):
        return self._workflow

    def load_latest_report(self):
        return {
            "Raw Engine Report": {
                "market": {
                    "internals_rows": [{"Asset": "SPY", "Price": "500", "Daily %": "+0.20%"}]
                }
            },
            "Market Internals": [{"Asset": "SPY", "Price": "500", "Daily %": "+0.20%", "Direction": "UP"}],
            "Macro Events": [{"Time": "08:30", "Event": "CPI", "Impact": "HIGH"}],
            "Leadership": {"rows": [{"Sector": "Technology", "Score (%)": "70", "Status": "Strong"}]},
            "Historical Match": {"rows": []},
        }


class _FakeWorkflowSuccess:
    def __init__(self, base_dir=None, as_of=None):
        self.base_dir = base_dir
        self.as_of = as_of or datetime.now().astimezone()
        self._ended_at = None
        self._duration_seconds = 0.0

    def run(self):
        return {"ok": True}

    def _save_history_snapshot(self, _report):
        return None

    def _append_journal_entry(self, _report):
        return None

    def update_dashboard(self, report_paths=None, success=True):
        return {"success": success, "report_paths": report_paths or {}}


class _FakeWorkflowFallback(_FakeWorkflowSuccess):
    def run(self):
        raise RuntimeError("primary workflow failed")

    def load_market_data(self):
        raise RuntimeError("Yahoo timeout")

    def load_macro_events(self):
        raise RuntimeError("macro unavailable")

    def load_market_internals(self):
        return {"SPY": {"price": 500, "daily_change_percent": 0.2, "direction": "UP"}}

    def load_leadership(self):
        return {"Technology": {"score": 70, "status": "Strong"}}

    def run_historical_match(self):
        return {"rows": []}

    def run_intelligence_engine(self, **_kwargs):
        return {"market": {"confidence": 70}, "summary": {}}

    def build_reports(self, **_kwargs):
        return {"Date": "2026-07-15", "Market Regime": "Bull", "Raw Engine Report": {"latest_signal": {"Actual": "UP"}}}


class _FakeWorkflowFailure(_FakeWorkflowSuccess):
    def run(self):
        raise RuntimeError("primary workflow failed")

    def load_market_data(self):
        raise RuntimeError("Yahoo timeout")

    def load_macro_events(self):
        raise RuntimeError("macro unavailable")

    def load_market_internals(self):
        raise RuntimeError("internals unavailable")

    def load_leadership(self):
        raise RuntimeError("leadership unavailable")

    def run_historical_match(self):
        raise RuntimeError("historical unavailable")


class _FakeStorageFailure(_FakeStorageSuccess):
    def load_latest_report(self):
        return {}


def test_refresh_success(tmp_path, monkeypatch):
    monkeypatch.setattr(refresh_module, "LocalStorage", _FakeStorageSuccess)
    monkeypatch.setattr(refresh_module, "MorningWorkflow", _FakeWorkflowSuccess)

    service = refresh_module.RefreshService(base_dir=tmp_path)
    result = service.run_refresh()

    assert result["success"] is True
    assert "timestamp" in result
    assert result["duration_seconds"] >= 0.0


def test_refresh_partial_data_failure_uses_stale_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(refresh_module, "LocalStorage", _FakeStorageSuccess)
    monkeypatch.setattr(refresh_module, "MorningWorkflow", _FakeWorkflowFallback)

    service = refresh_module.RefreshService(base_dir=tmp_path)
    result = service.run_refresh()

    assert result["success"] is True
    assert any("STALE" in warning for warning in result.get("warnings", []))


def test_refresh_total_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(refresh_module, "LocalStorage", _FakeStorageFailure)
    monkeypatch.setattr(refresh_module, "MorningWorkflow", _FakeWorkflowFailure)

    service = refresh_module.RefreshService(base_dir=tmp_path)
    result = service.run_refresh()

    assert result["success"] is False
    assert "failed" in result["message"].lower()
