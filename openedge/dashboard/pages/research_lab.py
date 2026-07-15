"""
Research Lab – Detailed analytics and validation metrics.
Moved from the main Morning Terminal to keep it focused on pre-market decisions.
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_repo_root = str(_Path(__file__).resolve().parents[3])
if _repo_root not in _sys.path:
    _sys.path.insert(0, _repo_root)

from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

try:
    import plotly.graph_objects as go
except Exception:  # pragma: no cover
    go = None

from openedge.dashboard.components import inject_styles, render_footer, render_metric_card, render_section_header
from openedge.validation.validation_engine import ValidationEngine

BASE_DIR = Path(__file__).resolve().parents[3]
CSV_FILE = BASE_DIR / "openedge_db.csv"
JOURNAL_FILE = BASE_DIR / "research_journal.csv"
DISPLAY_VERSION = "v1.2.0"


def _safe_plotly_chart(st_module, fig):
    plotly_chart = getattr(st_module, "plotly_chart", None)
    if callable(plotly_chart):
        plotly_chart(fig, width="stretch")
    else:
        st_module.write("Chart view unavailable in this environment.")


def main():
    try:
        st.set_page_config(page_title="OPENEDGE Research Lab", page_icon="🧪", layout="wide")
    except Exception:
        pass

    inject_styles(st)

    validation_engine = ValidationEngine(db_path=CSV_FILE, journal_path=JOURNAL_FILE, reports_dir=BASE_DIR / "reports")

    st.markdown(
        "<div class='oe-shell'><div class='oe-kicker'>Research & Analytics</div>"
        "<h1 class='oe-title'>Research Lab</h1>"
        "<p class='oe-subtitle'>Deep-dive validation metrics and performance analysis.</p></div>",
        unsafe_allow_html=True,
    )

    # Create tabs
    tab1, tab2, tab3, tab4 = st.tabs(["📊 Overview", "📈 Performance", "✅ Validation", "🕐 History"])

    validation_summary = validation_engine.summary()
    rolling_20 = validation_engine.rolling_accuracy(window=20)
    rolling_50 = validation_engine.rolling_accuracy(window=50)
    by_regime = validation_engine.accuracy_by_market_regime().get("items", [])
    confidence_calibration = validation_engine.confidence_calibration().get("items", [])
    monthly = validation_engine.monthly_accuracy().get("items", [])

    # ═════════════════════════════════════════════════════════════════════════════════════
    # TAB 1: OVERVIEW
    # ═════════════════════════════════════════════════════════════════════════════════════
    with tab1:
        render_section_header(st, "📊 Research Metrics Overview")
        
        m1, m2, m3, m4, m5 = st.columns(5)
        render_metric_card(m1, "Total Signals", validation_summary.get("total_signals", 0))
        render_metric_card(m2, "Overall Accuracy", f"{float(validation_summary.get('overall_accuracy', 0.0)):.2f}%")
        render_metric_card(m3, "Rolling 20 Accuracy", f"{float(validation_summary.get('rolling_20_accuracy', 0.0)):.2f}%")
        render_metric_card(m4, "Average Confidence", f"{float(validation_summary.get('average_confidence', 0.0)):.2f}")
        render_metric_card(m5, "Avg Historical Similarity", f"{float(validation_summary.get('average_historical_similarity', 0.0)):.2f}%")
        
        st.markdown("")
        
        col1, col2 = st.columns(2)
        
        with col1:
            render_section_header(st, "Best & Worst Regimes")
            r1, r2 = st.columns(2)
            render_metric_card(r1, "Best Regime", validation_summary.get("best_performing_regime", "N/A"))
            render_metric_card(r2, "Worst Regime", validation_summary.get("worst_performing_regime", "N/A"))
        
        with col2:
            render_section_header(st, "Signal Distribution")
            r1, r2, r3 = st.columns(3)
            render_metric_card(r1, "Correct Signals", validation_summary.get("correct_signals", 0))
            render_metric_card(r2, "Incorrect Signals", validation_summary.get("incorrect_signals", 0))
            accuracy_pct = float(validation_summary.get('overall_accuracy', 0.0))
            render_metric_card(r3, "Hit Rate", f"{accuracy_pct:.1f}%")
        
        st.markdown("")
        render_section_header(st, "Research Journal (Latest 20 Entries)")
        journal_frame = validation_engine.journal_path
        if journal_frame.exists():
            try:
                df = pd.read_csv(journal_frame)
                if not df.empty:
                    df = df.sort_values("date", ascending=False).head(20)
                    st.dataframe(df, hide_index=True, width="stretch")
                else:
                    st.info("No journal entries yet.")
            except Exception:
                st.info("Unable to load journal.")
        else:
            st.info("No journal file available.")

    # ═════════════════════════════════════════════════════════════════════════════════════
    # TAB 2: PERFORMANCE
    # ═════════════════════════════════════════════════════════════════════════════════════
    with tab2:
        render_section_header(st, "📈 Performance Analysis")
        
        # Rolling Accuracy
        render_section_header(st, "Rolling Accuracy (20 & 50-session)", subtitle="Performance trend over time")
        if rolling_20.get("points"):
            rolling_frame = pd.DataFrame(rolling_20.get("points", []))
            if go is None:
                st.dataframe(rolling_frame, hide_index=True, width="stretch")
            else:
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=rolling_frame["date"],
                    y=rolling_frame["accuracy"],
                    mode="lines+markers",
                    name="20-session",
                    line=dict(color="#0ea5e9", width=2),
                    marker=dict(size=6),
                ))
                fig.update_layout(
                    height=350,
                    margin=dict(l=10, r=10, t=10, b=10),
                    yaxis=dict(range=[0, 100]),
                    showlegend=True,
                    xaxis_title="Date",
                    yaxis_title="Accuracy %",
                )
                _safe_plotly_chart(st, fig)
        else:
            st.info("Insufficient data for rolling accuracy charts.")
        
        st.markdown("")
        
        # Monthly Accuracy
        render_section_header(st, "Monthly Performance", subtitle="Accuracy trends by month")
        if monthly:
            monthly_frame = pd.DataFrame(monthly)
            if go is None:
                st.dataframe(monthly_frame, hide_index=True, width="stretch")
            else:
                fig = go.Figure(
                    go.Scatter(
                        x=monthly_frame["month"],
                        y=monthly_frame["accuracy"],
                        mode="lines+markers",
                        line=dict(color="#6366f1", width=2),
                        marker=dict(size=7),
                    )
                )
                fig.update_layout(
                    height=320,
                    margin=dict(l=10, r=10, t=10, b=10),
                    yaxis=dict(range=[0, 100]),
                    showlegend=False,
                    xaxis_title="Month",
                    yaxis_title="Accuracy %",
                )
                _safe_plotly_chart(st, fig)
        else:
            st.info("No monthly accuracy data available.")

    # ═════════════════════════════════════════════════════════════════════════════════════
    # TAB 3: VALIDATION
    # ═════════════════════════════════════════════════════════════════════════════════════
    with tab3:
        render_section_header(st, "✅ Validation & Calibration")
        
        # Accuracy by Regime
        render_section_header(st, "Accuracy by Market Regime", subtitle="Performance breakdown by regime")
        if by_regime:
            regime_frame = pd.DataFrame(by_regime)
            if go is None:
                st.dataframe(regime_frame, hide_index=True, width="stretch")
            else:
                fig = go.Figure(
                    go.Bar(
                        x=regime_frame["regime"],
                        y=regime_frame["accuracy"],
                        marker_color="#10b981",
                        text=regime_frame["accuracy"],
                        textposition="auto",
                    )
                )
                fig.update_layout(
                    height=320,
                    margin=dict(l=10, r=10, t=10, b=10),
                    yaxis=dict(range=[0, 100]),
                    showlegend=False,
                    xaxis_title="Market Regime",
                    yaxis_title="Accuracy %",
                )
                _safe_plotly_chart(st, fig)
        else:
            st.info("No regime-level accuracy data available.")
        
        st.markdown("")
        
        # Confidence Calibration
        render_section_header(st, "Confidence Calibration", subtitle="Accuracy by confidence band")
        if confidence_calibration:
            calibration_frame = pd.DataFrame(confidence_calibration)
            if go is None:
                st.dataframe(calibration_frame, hide_index=True, width="stretch")
            else:
                fig = go.Figure(
                    go.Bar(
                        x=calibration_frame["band"],
                        y=calibration_frame["accuracy_percent"],
                        marker_color="#f59e0b",
                        text=calibration_frame["accuracy_percent"],
                        textposition="auto",
                    )
                )
                fig.update_layout(
                    height=320,
                    margin=dict(l=10, r=10, t=10, b=10),
                    yaxis=dict(range=[0, 100]),
                    showlegend=False,
                    xaxis_title="Confidence Band",
                    yaxis_title="Accuracy %",
                )
                _safe_plotly_chart(st, fig)

            st.dataframe(calibration_frame, hide_index=True, width="stretch")
        else:
            st.info("No confidence calibration data available.")

    # ═════════════════════════════════════════════════════════════════════════════════════
    # TAB 4: HISTORY
    # ═════════════════════════════════════════════════════════════════════════════════════
    with tab4:
        render_section_header(st, "🕐 Historical Analysis")
        
        st.markdown("### Historical Similarity & Match Analysis")
        st.info("This tab shows historical pattern matching quality and similar market conditions from the past.")
        
        # Display overall similarity score
        avg_similarity = float(validation_summary.get("average_historical_similarity", 0.0))
        col1, col2 = st.columns(2)
        render_metric_card(col1, "Average Historical Similarity", f"{avg_similarity:.2f}%")
        render_metric_card(col2, "Total Days Analyzed", validation_summary.get("total_signals", 0))
        
        st.markdown("")
        st.markdown("**What this means:**")
        st.markdown("""
        - **90%+**: Today strongly matches a historical day – high confidence in pattern continuation
        - **70-90%**: Good match with historical conditions – useful precedent available
        - **50-70%**: Moderate similarity – some historical relevance
        - **<50%**: Unique conditions – limited historical guidance
        """)

    render_footer(st, DISPLAY_VERSION, datetime.now().astimezone())


if __name__ == "__main__":
    main()
