from __future__ import annotations

import json
from pathlib import Path


class MarkdownExporter:
    def render(self, report: dict) -> str:
        internals = report.get("Market Internals", {})
        if isinstance(internals, dict):
            internals_lines = [
                f"- {asset}: {values.get('price', 'N/A')} ({values.get('daily_change_percent', 'N/A')}%, {values.get('direction', 'N/A')})"
                for asset, values in internals.items()
            ]
        else:
            internals_lines = [
                f"- {row.get('Asset', 'N/A')}: {row.get('Price', 'N/A')} ({row.get('Daily %', 'N/A')}, {row.get('Direction', 'N/A')})"
                for row in internals
            ]
        if not internals_lines:
            internals_lines = ["- N/A"]

        leadership = report.get("Leadership", {})
        leadership_lines = [
            f"- {sector}: {values.get('status', 'Neutral')} (Score {values.get('score', 'N/A')})"
            for sector, values in leadership.items()
        ]
        if not leadership_lines:
            leadership_lines = ["- N/A"]

        macro_lines = [
            f"- {event.get('time', 'N/A')}: {event.get('event', 'N/A')} ({event.get('impact', 'Low')})"
            for event in report.get("Macro Events", [])
        ]
        if not macro_lines:
            macro_lines = ["- N/A"]

        historical = report.get("Historical Match", {})
        best_match = historical.get("best_match", {}) if isinstance(historical, dict) else {}

        return (
            "# OPENEDGE Daily Research\n\n"
            "## Executive Summary\n"
            f"{report.get('Morning Brief', 'N/A')}\n\n"
            "## Market Regime\n"
            f"- Market Regime: {report.get('Market Regime', 'N/A')}\n"
            f"- Bias: {report.get('Bias', 'N/A')}\n\n"
            "## Confidence\n"
            f"- Confidence: {report.get('Confidence', 'N/A')}/100\n"
            f"- Opening Style: {report.get('Opening Style', 'N/A')}\n"
            f"- Opportunity Score: {report.get('Opportunity Score', 'N/A')}/10\n\n"
            "## Market Internals\n"
            f"{"\n".join(internals_lines)}\n\n"
            "## Leadership\n"
            f"{"\n".join(leadership_lines)}\n\n"
            "## Macro Events\n"
            f"{"\n".join(macro_lines)}\n\n"
            "## Historical Match\n"
            f"- Best Match Date: {best_match.get('date', 'N/A')}\n"
            f"- Similarity: {best_match.get('similarity', 'N/A')}\n\n"
            "## Today's Focus\n"
            f"{report.get('Raw Engine Report', {}).get('summary', {}).get('todays_focus', 'N/A')}\n\n"
            "## Research Conclusion\n"
            f"{report.get('Research Conclusion', 'N/A')}\n"
        )

    def export(self, report: dict, path: Path) -> Path:
        path.write_text(self.render(report), encoding="utf-8")
        return path


class JSONExporter:
    def export(self, report: dict, path: Path) -> Path:
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return path


class HTMLExporter:
    def render(self, report: dict) -> str:
        md = MarkdownExporter().render(report)
        escaped = md.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return (
            "<!doctype html>\n"
            "<html lang='en'>\n"
            "<head><meta charset='utf-8'><title>OPENEDGE Daily Research</title></head>\n"
            "<body style='font-family: Segoe UI, sans-serif; line-height:1.5; max-width: 960px; margin: 24px auto;'>\n"
            f"{escaped.replace(chr(10), '<br>\\n')}\n"
            "</body>\n"
            "</html>\n"
        )

    def export(self, report: dict, path: Path) -> Path:
        path.write_text(self.render(report), encoding="utf-8")
        return path
