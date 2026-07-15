from __future__ import annotations

import io
from datetime import datetime

import pandas as pd
import streamlit as st

try:
    import plotly.graph_objects as go
except Exception:  # pragma: no cover
    go = None

from openedge.dashboard.components import inject_styles, render_metric_card, render_section_header
from openedge.validation.validation_engine import ValidationEngine


def _safe_plotly_chart(st_module, fig):
    plotly_chart = getattr(st_module, "plotly_chart", None)
    if callable(plotly_chart):
        plotly_chart(fig, width="stretch")
    else:
        st_module.write("Chart view unavailable in this environment.")


def _calibration_score(calibration_items: list[dict]) -> float:
    weighted_total = 0.0
    signals_total = 0
    for item in calibration_items:
        signals = int(item.get("signals", 0) or 0)
        accuracy = float(item.get("accuracy_percent", 0.0) or 0.0)
        weighted_total += signals * accuracy
        signals_total += signals

    if signals_total == 0:
        return 0.0
    return round(weighted_total / signals_total, 2)


def _research_quality_label(overall_accuracy: float) -> str:
    if overall_accuracy >= 70.0:
        return "Strong"
    if overall_accuracy >= 55.0:
        return "Moderate"
    return "Developing"


def _calibration_status(score: float) -> str:
    if score >= 70.0:
        return "Aligned"
    if score >= 55.0:
        return "Monitoring"
    return "Needs Improvement"


def _suggested_improvement(overall_accuracy: float, calibration_status: str, worst_regime: str) -> str:
    if overall_accuracy < 20.0:
        return "Continue collecting daily research sessions. Validation metrics become meaningful after approximately 20 completed sessions."
    if calibration_status == "Needs Improvement":
        return "Improve confidence calibration by tightening score discipline on low-confidence calls."
    if worst_regime and worst_regime != "N/A":
        return f"Focus review on the weakest regime: {worst_regime}."
    return "Maintain current process and monitor rolling accuracy for drift."


def main():
    try:
        st.set_page_config(page_title="OPENEDGE Validation", page_icon="📊", layout="wide")
    except Exception:
        pass

    inject_styles(st)

    engine = ValidationEngine()
    summary = engine.summary()
    rolling_20_payload = engine.rolling_accuracy(window=20)
    rolling_50_payload = engine.rolling_accuracy(window=50)
    rolling = rolling_20_payload.get("points", [])
    by_regime = engine.accuracy_by_market_regime().get("items", [])
    calibration = engine.confidence_calibration().get("items", [])
    monthly = engine.monthly_accuracy().get("items", [])
    journal_entries = engine.journal_path
    journal_frame = pd.DataFrame()
    if journal_entries.exists():
        try:
            journal_frame = pd.read_csv(journal_entries)
        except Exception:
            journal_frame = pd.DataFrame()

    overall_accuracy = float(summary.get("overall_accuracy", 0.0) or 0.0)
    rolling_20_accuracy = float(summary.get("rolling_20_accuracy", 0.0) or 0.0)
    total_signals = int(summary.get("total_signals", 0) or 0)
    rolling_50_accuracy_value = rolling_50_payload.get("latest_accuracy")
    rolling_50_available = total_signals >= 50 and rolling_50_accuracy_value is not None
    average_confidence = float(summary.get("average_confidence", 0.0) or 0.0)
    average_similarity = float(summary.get("average_historical_similarity", 0.0) or 0.0)
    best_regime = summary.get("best_performing_regime", "N/A")
    worst_regime = summary.get("worst_performing_regime", "N/A")
    calibration_score = _calibration_score(calibration)
    calibration_status = _calibration_status(calibration_score)
    suggested_improvement = _suggested_improvement(overall_accuracy, calibration_status, worst_regime)

    st.markdown(
        "<div class='oe-shell'><div class='oe-kicker'>Dedicated Validation Dashboard</div>"
        "<h1 class='oe-title'>Research Validation</h1>"
        "<p class='oe-subtitle'>Measure. Learn. Improve.</p></div>",
        unsafe_allow_html=True,
    )

    if total_signals < 20:
        st.info(
            "Continue collecting daily research sessions. Validation metrics become meaningful after approximately 20 completed sessions."
        )

    k1, k2, k3, k4 = st.columns(4)
    render_metric_card(k1, "Overall Accuracy", f"{overall_accuracy:.2f}%")
    render_metric_card(k2, "Rolling 20 Accuracy", f"{rolling_20_accuracy:.2f}%")
    rolling_50_text = f"{float(rolling_50_accuracy_value):.2f}%" if rolling_50_available else "N/A"
    rolling_50_help = None if rolling_50_available else "Requires at least 50 tracked signals."
    render_metric_card(k3, "Rolling 50 Accuracy", rolling_50_text, help_text=rolling_50_help)
    render_metric_card(k4, "Average Confidence", f"{average_confidence:.2f}")

    k5, k6, k7 = st.columns(3)
    render_metric_card(k5, "Average Similarity", f"{average_similarity:.2f}%")
    render_metric_card(k6, "Best Performing Regime", best_regime)
    render_metric_card(k7, "Worst Performing Regime", worst_regime)

    if not rolling_50_available:
        st.info("Rolling 50 Accuracy will appear automatically once 50 or more signals are available.")

    render_section_header(st, "Validation Summary Card")
    quality = _research_quality_label(overall_accuracy)
    st.markdown(
        "<div class='oe-shell'>"
        f"<div class='oe-cell'><div class='oe-cell-label'>Research Quality</div><div class='oe-cell-value'>{quality}</div></div>"
        f"<div class='oe-cell'><div class='oe-cell-label'>Calibration Status</div><div class='oe-cell-value'>{calibration_status}</div></div>"
        f"<div class='oe-cell'><div class='oe-cell-label'>Strongest Regime</div><div class='oe-cell-value'>{best_regime}</div></div>"
        f"<div class='oe-cell'><div class='oe-cell-label'>Weakest Regime</div><div class='oe-cell-value'>{worst_regime}</div></div>"
        f"<div class='oe-cell'><div class='oe-cell-label'>Suggested Improvement</div><div class='oe-cell-value'>{suggested_improvement}</div></div>"
        "</div>",
        unsafe_allow_html=True,
    )

    render_section_header(st, "Rolling Accuracy")
    if rolling:
        rolling_frame = pd.DataFrame(rolling)
        if go is None:
            st.dataframe(rolling_frame, hide_index=True, width="stretch")
        else:
            fig = go.Figure(
                go.Scatter(
                    x=rolling_frame["date"],
                    y=rolling_frame["accuracy"],
                    mode="lines+markers",
                    line=dict(color="#0ea5e9", width=2),
                    marker=dict(size=6),
                )
            )
            fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10), yaxis=dict(range=[0, 100]), showlegend=False)
            _safe_plotly_chart(st, fig)
    else:
        st.info("No rolling accuracy data available yet.")

    render_section_header(st, "Accuracy by Market Regime")
    if by_regime:
        regime_frame = pd.DataFrame(by_regime)
        if go is None:
            st.dataframe(regime_frame, hide_index=True, width="stretch")
        else:
            fig = go.Figure(go.Bar(x=regime_frame["regime"], y=regime_frame["accuracy"], marker_color="#10b981"))
            fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10), yaxis=dict(range=[0, 100]), showlegend=False)
            _safe_plotly_chart(st, fig)
    else:
        st.info("No market regime accuracy data available yet.")

    render_section_header(st, "Confidence Calibration")
    if calibration:
        calibration_frame = pd.DataFrame(calibration)
        if go is None:
            st.dataframe(calibration_frame, hide_index=True, width="stretch")
        else:
            fig = go.Figure(go.Bar(x=calibration_frame["band"], y=calibration_frame["accuracy_percent"], marker_color="#f59e0b"))
            fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10), yaxis=dict(range=[0, 100]), showlegend=False)
            _safe_plotly_chart(st, fig)
    else:
        st.info("No confidence calibration data available yet.")

    render_section_header(st, "Monthly Accuracy")
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
            fig.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10), yaxis=dict(range=[0, 100]), showlegend=False)
            _safe_plotly_chart(st, fig)
    else:
        st.info("No monthly accuracy data available yet.")

    render_section_header(st, "Research Journal")
    if journal_frame.empty:
        st.info("No research journal entries available yet.")
    else:
        latest_entries = journal_frame.copy()
        for column in ["date", "bias", "actual", "correct", "confidence", "notes"]:
            if column not in latest_entries.columns:
                latest_entries[column] = pd.NA
        latest_entries = latest_entries[["date", "bias", "actual", "correct", "confidence", "notes"]]
        latest_entries = latest_entries.sort_values("date", ascending=False).head(10)
        display_entries = latest_entries.rename(
            columns={
                "date": "Date",
                "bias": "Bias",
                "actual": "Actual",
                "correct": "Correct",
                "confidence": "Confidence",
                "notes": "Notes",
            }
        )
        display_entries["Confidence"] = pd.to_numeric(display_entries["Confidence"], errors="coerce").astype("Int64")

        export_buffer = io.StringIO()
        display_entries.to_csv(export_buffer, index=False)
        st.download_button(
            "Export Journal to CSV",
            export_buffer.getvalue(),
            file_name="openedge_research_journal.csv",
            mime="text/csv",
        )
        st.dataframe(display_entries, hide_index=True, width="stretch")

    st.caption(f"Updated: {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}")


if __name__ == "__main__":
    main()
