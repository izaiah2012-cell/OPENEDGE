"""
Research Archive – Historical reports and report search.
Automatically discovers and displays previous research reports.
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_repo_root = str(_Path(__file__).resolve().parents[3])
if _repo_root not in _sys.path:
    _sys.path.insert(0, _repo_root)

import json
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from openedge.dashboard.components import inject_styles, render_footer

BASE_DIR = Path(__file__).resolve().parents[3]
REPORTS_DIR = BASE_DIR / "reports"
DISPLAY_VERSION = "v1.2.0"


def _extract_report_date(report_file: Path) -> str | None:
    stem = report_file.stem
    if re.match(r"^\d{4}-\d{2}-\d{2}$", stem):
        return stem
    if stem.endswith("_research"):
        candidate = stem.removesuffix("_research")
        if re.match(r"^\d{4}-\d{2}-\d{2}$", candidate):
            return candidate
    return None


def _report_snapshot(report_data: dict) -> dict:
    raw_report = report_data.get("Raw Engine Report", {}) if isinstance(report_data.get("Raw Engine Report", {}), dict) else {}

    market = report_data.get("market", {}) if isinstance(report_data.get("market", {}), dict) else {}
    if not market:
        market = raw_report.get("market", {}) if isinstance(raw_report.get("market", {}), dict) else {}
    if not market:
        market = {
            "bias": report_data.get("Bias", "N/A"),
            "confidence": report_data.get("Confidence", 0),
            "market_regime": report_data.get("Market Regime", "N/A"),
            "opportunity_score": report_data.get("Opportunity Score", 0),
            "opening_risk": report_data.get("Opening Auction Risk", report_data.get("Opening Risk", 0)),
        }

    summary = report_data.get("summary", {}) if isinstance(report_data.get("summary", {}), dict) else {}
    if not summary:
        summary = raw_report.get("summary", {}) if isinstance(raw_report.get("summary", {}), dict) else {}

    historical = report_data.get("historical", {}) if isinstance(report_data.get("historical", {}), dict) else {}
    if not historical:
        historical = report_data.get("Historical Match", {}) if isinstance(report_data.get("Historical Match", {}), dict) else {}

    leadership = report_data.get("leadership", {}) if isinstance(report_data.get("leadership", {}), dict) else {}
    if not leadership:
        leadership = raw_report.get("leadership", {}) if isinstance(raw_report.get("leadership", {}), dict) else {}

    macro = report_data.get("macro", {}) if isinstance(report_data.get("macro", {}), dict) else {}
    if not macro:
        macro = raw_report.get("macro", {}) if isinstance(raw_report.get("macro", {}), dict) else {}

    return {
        "market": market,
        "summary": summary,
        "historical": historical,
        "leadership": leadership,
        "macro": macro,
        "metadata": report_data.get("Report Metadata", {}) if isinstance(report_data.get("Report Metadata", {}), dict) else {},
    }


def _report_list_row(report_data: dict, report_file: Path, date_str: str) -> dict:
    snapshot = _report_snapshot(report_data)
    market = snapshot.get("market", {})
    historical = snapshot.get("historical", {})
    best_match = historical.get("best_match", {}) if isinstance(historical, dict) else {}

    return {
        "filename": report_file.name,
        "date": date_str,
        "bias": report_data.get("Bias", market.get("bias", "N/A")),
        "confidence": report_data.get("Confidence", market.get("confidence", 0)),
        "market_regime": report_data.get("Market Regime", market.get("market_regime", "N/A")),
        "opportunity_score": report_data.get("Opportunity Score", market.get("opportunity_score", 0)),
        "opening_risk": market.get("opening_risk", report_data.get("Opening Auction Risk", report_data.get("Opening Risk", 0))),
        "similarity": float(best_match.get("similarity", historical.get("average_similarity", 0.0)) or 0.0),
        "raw_path": report_file,
    }


def _load_reports() -> list[dict]:
    if not REPORTS_DIR.exists():
        return []

    reports = []
    for report_file in sorted(REPORTS_DIR.glob("*.json"), reverse=True):
        try:
            date_str = _extract_report_date(report_file)
            if not date_str:
                continue
            report_data = json.loads(report_file.read_text(encoding="utf-8"))
            reports.append(_report_list_row(report_data, report_file, date_str))
        except Exception:
            continue
    return reports


def main():
    try:
        st.set_page_config(page_title="OPENEDGE Research Archive", page_icon="📚", layout="wide")
    except Exception:
        pass

    inject_styles(st)

    st.markdown(
        "<div class='oe-shell'><div class='oe-kicker'>Historical Research</div>"
        "<h1 class='oe-title'>Research Archive</h1>"
        "<p class='oe-subtitle'>Discover and explore historical research reports.</p></div>",
        unsafe_allow_html=True,
    )

    all_reports = _load_reports()

    if all_reports:
        parsed_dates = []
        for report in all_reports:
            try:
                parsed_dates.append(datetime.strptime(report["date"], "%Y-%m-%d").date())
            except Exception:
                continue
        if parsed_dates:
            min_date = min(parsed_dates)
            max_date = max(parsed_dates)
        else:
            today = datetime.now().date()
            min_date = today
            max_date = today
    else:
        today = datetime.now().date()
        min_date = today
        max_date = today

    col1, col2, col3 = st.columns(3)
    with col1:
        date_start = st.date_input("Start Date", value=min_date)
    with col2:
        date_end = st.date_input("End Date", value=max_date)
    with col3:
        bias_filter = st.selectbox("Bias Filter", options=["All", "Bullish", "Bearish", "Neutral"])

    search_term = st.text_input("Search reports", placeholder="Search by date, bias, or regime...")

    filtered = []
    for report in all_reports:
        try:
            report_date = datetime.strptime(report["date"], "%Y-%m-%d").date()
            if report_date < date_start or report_date > date_end:
                continue

            if bias_filter != "All" and str(report.get("bias", "")).upper() != bias_filter.upper():
                continue

            if search_term:
                search_lower = search_term.lower()
                text = f"{report.get('date','')} {report.get('bias','')} {report.get('market_regime','')}"
                if search_lower not in text.lower():
                    continue

            filtered.append(report)
        except Exception:
            continue

    st.markdown(f"### Found {len(filtered)} reports")

    if not filtered:
        st.info("No reports match the selected filters.")
    else:
        display_data = []
        for report in filtered:
            display_data.append(
                {
                    "📅 Date": report["date"],
                    "📊 Bias": report.get("bias", "N/A"),
                    "🎯 Confidence": f"{int(float(report.get('confidence', 0) or 0))}%",
                    "🌍 Regime": report.get("market_regime", "N/A"),
                    "🎪 Opportunity": f"{report.get('opportunity_score', 0)}/10",
                    "📈 Risk": f"{report.get('opening_risk', 0)}/10",
                    "🔗 Similarity": f"{float(report.get('similarity', 0.0)):.1f}%",
                }
            )

        st.dataframe(pd.DataFrame(display_data), hide_index=True, width="stretch")

        st.markdown("---")
        st.markdown("### View Full Report")

        selected_date = st.selectbox(
            "Select a report to view",
            options=[r["date"] for r in filtered],
            format_func=lambda x: f"{x} - {next((r['bias'] for r in filtered if r['date'] == x), 'N/A')}",
        )

        if st.button("📖 Open Report"):
            selected_report = next((r for r in filtered if r["date"] == selected_date), None)
            if selected_report:
                try:
                    report_data = json.loads(selected_report["raw_path"].read_text(encoding="utf-8"))
                    snapshot = _report_snapshot(report_data)

                    st.markdown("---")
                    st.markdown(f"## Report for {selected_date}")

                    metadata = snapshot.get("metadata", {})
                    if metadata:
                        st.caption(
                            f"Version {metadata.get('Version', 'N/A')} | Workflow {metadata.get('Workflow ID', 'N/A')} | Report {metadata.get('Report ID', 'N/A')} | Historical DB {metadata.get('Historical Database Version', 'N/A')}"
                        )

                    market = snapshot.get("market", {})
                    summary = snapshot.get("summary", {})

                    m1, m2, m3, m4, m5 = st.columns(5)
                    m1.metric("Bias", report_data.get("Bias", market.get("bias", "N/A")))
                    m2.metric("Confidence", f"{int(float(report_data.get('Confidence', market.get('confidence', 0)) or 0))}%")
                    m3.metric("Market Regime", report_data.get("Market Regime", market.get("market_regime", "N/A")))
                    m4.metric("Opportunity", f"{report_data.get('Opportunity Score', market.get('opportunity_score', 0))}/10")
                    m5.metric("Opening Risk", f"{market.get('opening_risk', 0)}/10")

                    st.markdown("### 📋 Morning Brief")
                    st.write(summary.get("executive_summary", report_data.get("Morning Brief", "N/A")))

                    st.markdown("### 🔬 AI Summary")
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown("**Market Regime**")
                        st.write(report_data.get("Market Regime", market.get("market_regime", "N/A")))
                        st.markdown("**Leadership Summary**")
                        st.write(snapshot.get("leadership", {}).get("summary", "N/A"))
                    with c2:
                        st.markdown("**Macro Summary**")
                        st.write(snapshot.get("macro", {}).get("macro_summary", "N/A"))
                        st.markdown("**Today's Focus**")
                        st.write(summary.get("todays_focus", "N/A"))

                    st.markdown("### 📈 Historical Analysis")
                    historical = snapshot.get("historical", {})
                    best_match = historical.get("best_match", {}) if isinstance(historical, dict) else {}
                    h1, h2, h3, h4 = st.columns(4)
                    h1.metric("Best Match", best_match.get("date", "N/A"))
                    h2.metric("Similarity", f"{float(best_match.get('similarity', historical.get('average_similarity', 0.0)) or 0.0):.1f}%")
                    h3.metric("Expected Outcome", historical.get("expected_outcome", "N/A"))
                    h4.metric("Historical Confidence", historical.get("historical_confidence", "N/A"))

                    st.markdown("### 🎯 Research Conclusion")
                    st.write(summary.get("research_conclusion", report_data.get("Research Conclusion", "N/A")))
                except Exception as exc:
                    st.error(f"Error loading report: {exc}")

    render_footer(st, DISPLAY_VERSION, datetime.now().astimezone())


if __name__ == "__main__":
    main()
