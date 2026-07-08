from __future__ import annotations

from datetime import datetime
from pathlib import Path


class WorkflowLogger:
    """File logger for morning workflow execution metadata."""

    def __init__(self, logs_dir: Path):
        self.logs_dir = Path(logs_dir)

    def write(
        self,
        *,
        as_of: datetime,
        start_time: datetime,
        finish_time: datetime,
        duration_seconds: float,
        data_sources: list[str],
        export_status: str,
        errors: str = "",
    ) -> Path:
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        log_path = self.logs_dir / f"{as_of.strftime('%Y-%m-%d')}.log"

        lines = [
            f"Workflow Start: {start_time.isoformat()}",
            f"Workflow Finish: {finish_time.isoformat()}",
            f"Duration: {round(duration_seconds, 2)}s",
            "Data Sources:",
        ]

        if data_sources:
            lines.extend(f"- {source}" for source in data_sources)
        else:
            lines.append("- N/A")

        lines.append(f"Export Status: {export_status}")
        if errors:
            lines.append(f"Errors: {errors}")

        log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return log_path
