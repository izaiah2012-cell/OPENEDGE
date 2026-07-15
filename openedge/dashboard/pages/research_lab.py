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
DISPLAY_VERSION = "v1.0.0-beta"


def _safe_plotly_chart(st_module, fig):
    plotly_chart = getattr(st_module, "plotly_chart", None)
    if callable(plotly_chart):
        plotly_chart(fig, width="stretch")
    else:
        st_module.write("Chart view unavailable in this environment.")


def main():
    try:
        st.set_page_config(page_title="OPENEDGE Research Lab", page_icon="🔬", layout="wide")
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

    # Summary metrics at top
    summary = validation_engine.summary()
    m1, m2, m3, m4, m5 = st.columns(5)
    render_metric_card(m1, "Total Signals", summary.get("total_signals", 0))
    render_metric_card(m2, "Overall Accuracy", f"{float(summary.get('overall_accuracy', 0.0)):.2f}%")
    render_metric_card(m3, "Rolling 20 Accuracy", f"{float(summary.get('rolling_20_accuracy', 0.0)):.2f}%")
    render_metric_card(m4, "Average Confidence", f"{float(summary.get('average_confidence', 0.0)):.2f}")
    render_metric_card(m5, "Avg Historical Similarity", f"{float(summary.get('average_historical_similarity', 0.0)):.2f}%")

    # Rolling Accuracy
    render_section_header(st, "Rolling Accuracy", "20-session and 50-session rolling windows")
    rolling_20 = validation_engine.rolling_accuracy(window=20)
    rolling_50 = validation_engine.rolling_accuracy(window=50)

    if rolling_20.get("points"):
        rolling_frame = pd.DataFrame(rolling_20.get("points", []))
        if go is not None:
            fig = go.Figure(
                go.Scatter(
                    x=rolling_frame["date"],
                    y=rolling_frame["accuracy"],
                    mode="lines+markers",
                    name="20-session",
                    line=dict(color="#0ea5e9", width=2),
                    marker=dict(size=6),
                )
            )
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
            st.dataframe(rolling_frame, hide_index=True, width="stretch")
    else:
        st.info("Insufficient data for rolling accuracy charts.")

    # Accuracy by Regime
    render_section_header(st, "Accuracy by Market Regime")
    by_regime = validation_engine.accuracy_by_market_regime().get("items", [])
    if by_regime:
        regime_frame = pd.DataFrame(by_regime)
        if go is not None:
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
            st.dataframe(regime_frame, hide_index=True, width="stretch")
    else:
        st.info("No regime-level accuracy data available.")

    # Confidence Calibration
    render_section_header(st, "Confidence Calibration", "Accuracy by confidence band")
    calibration = validation_engine.confidence_calibration().get("items", [])
    if calibration:
        calibration_frame = pd.DataFrame(calibration)
        if go is not None:
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

    # Monthly Accuracy
    render_section_header(st, "Monthly Performance")
    monthly = validation_engine.monthly_accuracy().get("items", [])
    if monthly:
        monthly_frame = pd.DataFrame(monthly)
        if go is not None:
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
            st.dataframe(monthly_frame, hide_index=True, width="stretch")
    else:
        st.info("No monthly accuracy data available.")

    # Research Journal
    render_section_header(st, "Research Journal", "Latest 20 trading session records")
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

    render_footer(st, DISPLAY_VERSION, datetime.now().astimezone())


if __name__ == "__main__":
    main()
