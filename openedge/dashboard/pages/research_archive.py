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

from openedge.dashboard.components import inject_styles, render_footer, render_section_header

BASE_DIR = Path(__file__).resolve().parents[3]
REPORTS_DIR = BASE_DIR / "reports"
CSV_FILE = BASE_DIR / "openedge_db.csv"

DISPLAY_VERSION = "v1.1.0"


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
    if not market and isinstance(raw_report.get("market", {}), dict):
        market = raw_report.get("market", {})
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
    if isinstance(leadership, dict) and not leadership.get("summary"):
        leadership_summary = raw_report.get("leadership", {}).get("summary") if isinstance(raw_report.get("leadership", {}), dict) else None
        if leadership_summary:
            leadership = {**leadership, "summary": leadership_summary}

    macro = report_data.get("macro", {}) if isinstance(report_data.get("macro", {}), dict) else {}
    if not macro:
        macro = raw_report.get("macro", {}) if isinstance(raw_report.get("macro", {}), dict) else {"today_events": report_data.get("Macro Events", [])}
    if isinstance(macro, dict) and not macro.get("macro_summary"):
        macro_summary = raw_report.get("macro", {}).get("macro_summary") if isinstance(raw_report.get("macro", {}), dict) else None
        if macro_summary:
            macro = {**macro, "macro_summary": macro_summary}

    return {
        "market": market,
        "summary": summary,
        "historical": historical,
        "leadership": leadership,
        "macro": macro,
        "metadata": report_data.get("Report Metadata", {}) if isinstance(report_data.get("Report Metadata", {}), dict) else {},
    }


def _load_reports() -> list[dict]:
    """Discover and load all JSON reports from reports directory."""
    if not REPORTS_DIR.exists():
        return []
    
    reports = []
    for report_file in sorted(REPORTS_DIR.glob("*.json"), reverse=True):
        try:
            report_data = json.loads(report_file.read_text(encoding="utf-8"))
            date_str = _extract_report_date(report_file)
            if not date_str:
                continue
            
            # Extract key metrics
            market = report_data.get("market", {})
            reports.append({
                "filename": report_file.name,
                "date": date_str,
                "bias": market.get("bias", "N/A"),
                "confidence": market.get("confidence", 0),
                "market_regime": market.get("market_regime", "N/A"),
                "opportunity_score": market.get("opportunity_score", 0),
                "opening_risk": market.get("opening_risk", 0),
                "raw_path": report_file,
            })
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

    # Filters
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

    # Search box
    search_term = st.text_input("Search reports", placeholder="Search by date, bias, or regime...")

    # Apply filters
    filtered = []
    for report in all_reports:
        try:
            report_date = datetime.strptime(report["date"], "%Y-%m-%d").date()
            
            if report_date < date_start or report_date > date_end:
                continue
            
            if bias_filter != "All" and report["bias"].upper() != bias_filter.upper():
                continue
            
            if search_term:
                search_lower = search_term.lower()
                if not (search_lower in report["date"].lower() or 
                        search_lower in report["bias"].lower() or
                        search_lower in report["market_regime"].lower()):
                    continue
            
            filtered.append(report)
        except Exception:
            continue

    # Display results summary
    st.markdown(f"### Found {len(filtered)} reports")

    if not filtered:
        st.info("No reports match the selected filters.")
    else:
        # Display as table
        display_data = []
        for report in filtered:
            report_payload = {}
            try:
                report_payload = json.loads(report["raw_path"].read_text(encoding="utf-8"))
            except Exception:
                report_payload = {}

            raw_report = report_payload.get("Raw Engine Report", {}) if isinstance(report_payload, dict) else {}
            nested_market = raw_report.get("market", {}) if isinstance(raw_report.get("market", {}), dict) else {}
            historical = report_payload.get("Historical Match", {}) if isinstance(report_payload, dict) else {}
            best_match = historical.get("best_match", {}) if isinstance(historical, dict) else {}
            similarity = float(best_match.get("similarity", historical.get("average_similarity", 0.0)) or 0.0)
            confidence_value = report_payload.get("Confidence", 0)
            bias_value = report_payload.get("Bias", report.get("bias", "N/A"))
            regime_value = report_payload.get("Market Regime", report.get("market_regime", "N/A"))
            opportunity_value = report_payload.get("Opportunity Score", nested_market.get("opportunity_score", report.get("opportunity_score", 0)))
            opening_risk_value = nested_market.get("opening_risk", report.get("opening_risk", 0))
            display_data.append({
                "📅 Date": report["date"],
                "📊 Bias": bias_value,
                "🎯 Confidence": f"{int(float(confidence_value or 0))}%",
                "🌍 Regime": regime_value,
                "🎪 Opportunity": f"{opportunity_value}/10",
                "📈 Risk": f"{opening_risk_value}/10",
                "🔗 Similarity": f"{similarity:.1f}%",
            })
        
        df_display = pd.DataFrame(display_data)
        st.dataframe(df_display, hide_index=True, width="stretch")

        # Click to view report
        st.markdown("---")
        st.markdown("### View Full Report")
        
        selected_date = st.selectbox(
            "Select a report to view",
            options=[r["date"] for r in filtered],
            format_func=lambda x: f"{x} – {next((r['bias'] for r in filtered if r['date'] == x), 'N/A')}"
        )
        
        if st.button("📖 Open Report"):
            # Find the selected report
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
                    
                    # Summary metrics
                    market = snapshot.get("market", {})
                    summary = snapshot.get("summary", {})
                    
                    m1, m2, m3, m4, m5 = st.columns(5)
                    m1.metric("Bias", market.get("bias", "N/A"))
                    m2.metric("Confidence", f"{int(market.get('confidence', 0))}%")
                    m3.metric("Market Regime", market.get("market_regime", "N/A"))
                    m4.metric("Opportunity", f"{market.get('opportunity_score', 0)}/10")
                    m5.metric("Opening Risk", f"{market.get('opening_risk', 0)}/10")
                    
                    # Morning Brief
                    st.markdown("### 📋 Morning Brief")
                    st.write(summary.get("executive_summary", report_data.get("Morning Brief", "N/A")))
                    
                    # AI Summary
                    st.markdown("### 🔬 AI Summary")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**Market Regime**")
                        st.write(market.get("market_regime", "N/A"))
                        st.markdown("**Leadership Summary**")
                        st.write(snapshot.get("leadership", {}).get("summary", report_data.get("Leadership", {}).get("summary", "N/A")))
                    
                    with col2:
                        st.markdown("**Macro Summary**")
                        st.write(snapshot.get("macro", {}).get("macro_summary", report_data.get("Macro Summary", "N/A")))
                        st.markdown("**Today's Focus**")
                        st.write(summary.get("todays_focus", "N/A"))
                    
                    # Historical Match
                    st.markdown("### 📈 Historical Analysis")
                    historical = snapshot.get("historical", {})
                    best_match = historical.get("best_match", {})
                    h1, h2, h3, h4 = st.columns(4)
                    h1.metric("Best Match", best_match.get("date", "N/A"))
                    h2.metric("Similarity", f"{float(best_match.get('similarity', 0.0)):.1f}%")
                    h3.metric("Expected Outcome", historical.get("expected_outcome", "N/A"))
                    h4.metric("Historical Confidence", historical.get("historical_confidence", "N/A"))
                    
                    # Research Conclusion
                    st.markdown("### 🎯 Research Conclusion")
                    st.write(summary.get("research_conclusion", "N/A"))
                    
                except Exception as e:
                    st.error(f"Error loading report: {e}")

    render_footer(st, DISPLAY_VERSION, datetime.now().astimezone())


if __name__ == "__main__":
    main()
