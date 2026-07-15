from __future__ import annotations

from datetime import datetime
from pathlib import Path

from openedge.data.market import get_market_snapshot
from openedge.storage import LocalStorage
from openedge.utils.error_handling import safe_source_call


class HealthService:
    def __init__(self, base_dir: Path | None = None):
        self.base_dir = Path(base_dir) if base_dir else Path(__file__).resolve().parents[2]
        self.storage = LocalStorage(self.base_dir)

    def get_health(self) -> dict:
        market_status = safe_source_call("Market provider", get_market_snapshot)
        latest_report = self.storage.load_latest_report()
        workflow_status = self.storage.load_workflow_status()

        storage_ok = True
        try:
            storage_probe = {
                "timestamp": datetime.now().astimezone().isoformat(),
                "probe": "ok",
            }
            storage_path = self.storage.save_refresh_metadata(storage_probe)
            storage_ok = storage_path.exists()
        except Exception:
            storage_ok = False

        degraded = bool(market_status.warning)
        if not latest_report:
            degraded = True
        if not storage_ok:
            degraded = True

        return {
            "application_status": "degraded" if degraded else "healthy",
            "market_provider_status": "degraded" if market_status.warning else "healthy",
            "market_provider_warning": market_status.warning,
            "latest_report_available": bool(latest_report),
            "storage_status": "healthy" if storage_ok else "degraded",
            "latest_workflow_status": workflow_status.get("research_status", "N/A"),
            "latest_workflow_run": workflow_status.get("last_workflow_run", "N/A"),
        }
