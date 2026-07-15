from __future__ import annotations

from datetime import datetime
from uuid import uuid4


class ReportBuilder:
    """Build a normalized morning workflow report dictionary from engine outputs."""

    def build(
        self,
        *,
        as_of: datetime,
        intelligence_report: dict,
        market_internals: dict,
        macro_events: list,
        leadership: dict,
        historical_match: dict,
        version: str = "v1.1.0",
        workflow_id: str | None = None,
        report_id: str | None = None,
        historical_database_version: str = "unknown",
    ) -> dict:
        market = intelligence_report.get("market", {})
        summary = intelligence_report.get("summary", {})
        report_date = as_of.strftime("%Y-%m-%d")
        workflow_id = workflow_id or as_of.strftime("%Y%m%d%H%M%S")
        report_id = report_id or f"OE-{as_of.strftime('%Y%m%d')}-{uuid4().hex[:8]}"
        metadata = {
            "Version": version,
            "Generated Timestamp": as_of.isoformat(),
            "Workflow ID": workflow_id,
            "Report ID": report_id,
            "Historical Database Version": historical_database_version,
        }

        return {
            "Date": report_date,
            "Timestamp": as_of.isoformat(),
            **metadata,
            "Report Metadata": metadata,
            "Market Regime": market.get("market_regime", "N/A"),
            "Confidence": market.get("confidence", "N/A"),
            "Bias": market.get("bias", "N/A"),
            "Opening Style": market.get("opening_style", "N/A"),
            "Opportunity Score": market.get("opportunity_score", "N/A"),
            "Morning Brief": summary.get("executive_summary", "N/A"),
            "Market Internals": market.get("internals_rows") or market_internals or {},
            "Leadership": leadership,
            "Macro Events": macro_events,
            "Historical Match": historical_match,
            "Performance Summary": intelligence_report.get("performance", {}),
            "Research Conclusion": summary.get("research_conclusion", "N/A"),
            "Raw Engine Report": intelligence_report,
        }
