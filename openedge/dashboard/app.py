from pathlib import Path
from datetime import datetime
import json

import pandas as pd
import streamlit as st

try:
    import plotly.graph_objects as go
except Exception:  # pragma: no cover
    go = None

try:
    from streamlit_autorefresh import st_autorefresh
except Exception:  # pragma: no cover
    st_autorefresh = None

from openedge.dashboard.components import (
    inject_styles,
    render_footer,
    render_metric_card,
    render_section_header,
    render_status_badge,
)
from openedge.data.market import get_market_snapshot
from openedge.engines.history_engine import get_historical_matches
from openedge.engines.intelligence import IntelligenceEngine
from openedge.engines.macro_engine import get_macro_events
from openedge.engines.market_internals import get_market_internals
from openedge.models.leadership_engine import evaluate_sector_leadership
from openedge.services import HealthService, RefreshService
from openedge.storage import LocalStorage
from openedge.utils import safe_source_call
from openedge.validation.validation_engine import ValidationEngine

LEADERSHIP_SECTORS = ["Technology", "Financials", "Industrials", "Healthcare", "Consumer", "Energy"]

BASE_DIR = Path(__file__).resolve().parents[2]
CSV_FILE = BASE_DIR / "openedge_db.csv"
VERSION_FILE = BASE_DIR / "VERSION"
DISPLAY_VERSION = "v1.0.0-beta"
WORKFLOW_STATUS_FILE = BASE_DIR / "database" / "workflow_status.json"
JOURNAL_FILE = BASE_DIR / "research_journal.csv"
STORAGE = LocalStorage(BASE_DIR)


def _toast_success(message):
    toast = getattr(st, "toast", None)
    if callable(toast):
        toast(message, icon="✅")
    else:
        st.success(message)


def _toast_error(message):
    toast = getattr(st, "toast", None)
    if callable(toast):
        toast(message, icon="⚠️")
    else:
        st.error(message)


def _safe_plotly_chart(st_module, fig):
    plotly_chart = getattr(st_module, "plotly_chart", None)
    if callable(plotly_chart):
        plotly_chart(fig, width="stretch")
    else:
        st_module.write("Chart view unavailable in this environment.")


def market_internals_table(rows):
    if not rows:
        return pd.DataFrame(columns=["Asset", "Price", "Daily %", "Direction"])

    if isinstance(rows, dict):
        normalized = []
        for asset, values in rows.items():
            price = values.get("price")
            daily_change = values.get("daily_change_percent")
            if daily_change is None:
                daily_change_text = "N/A"
            elif abs(daily_change) < 1e-12:
                daily_change_text = "0.00%"
            else:
                daily_change_text = f"{daily_change:+.2f}%"

            normalized.append(
                {
                    "Asset": asset,
                    "Price": "N/A" if price is None else f"{price:,.2f}",
                    "Daily %": daily_change_text,
                    "Direction": values.get("direction", "N/A"),
                }
            )
        rows = normalized

    frame = pd.DataFrame(rows)

    def style_direction(value):
        if value == "UP":
            return "color: #15803d; font-weight: 700;"
        if value == "DOWN":
            return "color: #b91c1c; font-weight: 700;"
        return "color: #94a3b8;"

    def style_change(value):
        if value == "N/A":
            return "color: #94a3b8;"
        if value.startswith("+"):
            return "color: #15803d; font-weight: 700;"
        if value.startswith("-"):
            return "color: #b91c1c; font-weight: 700;"
        return "color: #d97706; font-weight: 700;"

    return frame.style.map(style_change, subset=["Daily %"]).map(style_direction, subset=["Direction"])


def get_market_internals_with_cache():
    cache_data = getattr(st, "cache_data", None)
    if cache_data is None:
        return get_market_internals(), datetime.now()

    @cache_data(ttl=60, show_spinner=False)
    def _cached_fetch():
        return get_market_internals(), datetime.now()

    return _cached_fetch()


def get_market_snapshot_with_cache():
    cache_data = getattr(st, "cache_data", None)
    if cache_data is None:
        return get_market_snapshot(), datetime.now()

    @cache_data(ttl=60, show_spinner=False)
    def _cached_fetch():
        return get_market_snapshot(), datetime.now()

    return _cached_fetch()


def _render_bullet_lines(st_module, values):
    if not values:
        st_module.write("- N/A")
        return

    for value in values:
        st_module.write(f"- {value}")


def load_signal_history():
    if not CSV_FILE.exists():
        return None

    try:
        df = pd.read_csv(CSV_FILE, on_bad_lines="skip")
    except Exception:
        return None

    if df.empty:
        return None

    return df


def load_latest_signal():
    df = load_signal_history()
    if df is None:
        return None

    return df.iloc[-1].to_dict()


def _fetch_leadership_cached():
    cache_data = getattr(st, "cache_data", None)
    if cache_data is None:
        return evaluate_sector_leadership()

    @cache_data(ttl=300, show_spinner=False)
    def _cached_fetch():
        return evaluate_sector_leadership()

    return _cached_fetch()


def get_leadership_with_fallback():
    fetched_at = datetime.now()
    leadership = _fetch_leadership_cached()
    used_fallback = False

    missing = [sector for sector in LEADERSHIP_SECTORS if sector not in leadership]
    session_state = getattr(st, "session_state", None)
    if missing and session_state is not None and "leadership_last" in session_state:
        prior = session_state.get("leadership_last", {})
        for sector in missing:
            if sector in prior:
                leadership[sector] = prior[sector]
                used_fallback = True

    if session_state is not None:
        session_state["leadership_last"] = leadership
        session_state["leadership_fetched_at"] = fetched_at

    return leadership, fetched_at, used_fallback


def leadership_chart(rows):
    if not rows:
        return None

    frame = pd.DataFrame(rows)
    if frame.empty or "Sector" not in frame.columns:
        return None

    frame["Score (%)"] = pd.to_numeric(frame.get("Score (%)", 0), errors="coerce").fillna(0.0)

    colors = []
    for status in frame.get("Status", []):
        if status == "Strong":
            colors.append("#16a34a")
        elif status == "Weak":
            colors.append("#dc2626")
        else:
            colors.append("#d97706")

    if go is None:
        return frame

    fig = go.Figure(go.Bar(x=frame["Score (%)"], y=frame["Sector"], orientation="h", marker_color=colors))
    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        height=300,
        xaxis_title="Strength",
        yaxis_title="",
        showlegend=False,
    )
    return fig


def macro_events_table(rows):
    if not rows:
        return pd.DataFrame(columns=["Time", "Event", "Impact"])

    return pd.DataFrame(rows)


def macro_events_styled_table(rows):
    frame = macro_events_table(rows)
    if frame.empty:
        return frame

    def style_impact(value):
        text = str(value).upper()
        if text == "HIGH":
            return "color: #dc2626; font-weight: 700;"
        if text == "MEDIUM":
            return "color: #d97706; font-weight: 700;"
        return "color: #16a34a; font-weight: 700;"

    return frame.style.map(style_impact, subset=["Impact"])


def historical_match_table(rows):
    if not rows:
        return pd.DataFrame(
            columns=[
                "Rank",
                "Date",
                "Similarity %",
                "Confidence Band",
                "Bias",
                "Actual",
                "Correct",
                "Why Similar",
            ]
        )

    frame = pd.DataFrame(rows)

    def style_row(row):
        row_style = [""] * len(row)
        if row["Rank"] == 1:
            row_style = ["background-color: #ecfdf5; font-weight: 700;"] * len(row)

        band_idx = frame.columns.get_loc("Confidence Band")
        band = row["Confidence Band"]
        if band == "Strong":
            row_style[band_idx] = row_style[band_idx] + "color: #15803d;"
        elif band == "Moderate":
            row_style[band_idx] = row_style[band_idx] + "color: #d97706;"
        else:
            row_style[band_idx] = row_style[band_idx] + "color: #b91c1c;"

        return row_style

    return frame.style.apply(style_row, axis=1)


def historical_matches_chart(rows):
    if not rows:
        return None

    frame = pd.DataFrame(rows).head(5).copy()
    if frame.empty:
        return None

    frame["Similarity %"] = pd.to_numeric(frame.get("Similarity %", 0), errors="coerce").fillna(0.0)
    frame["Date"] = frame.get("Date", "N/A").astype(str)

    if go is None:
        return frame[["Date", "Similarity %"]]

    fig = go.Figure(go.Bar(x=frame["Date"], y=frame["Similarity %"], marker_color="#2563eb"))
    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        height=320,
        xaxis_title="Session Date",
        yaxis_title="Similarity %",
        showlegend=False,
    )
    return fig


def rolling_accuracy_chart(points):
    if not points:
        return None

    frame = pd.DataFrame(points)
    if frame.empty or "date" not in frame.columns or "accuracy" not in frame.columns:
        return None

    frame["accuracy"] = pd.to_numeric(frame["accuracy"], errors="coerce")
    frame = frame.dropna(subset=["accuracy"])
    if frame.empty:
        return None

    if go is None:
        return frame[["date", "accuracy"]]

    fig = go.Figure(go.Scatter(x=frame["date"], y=frame["accuracy"], mode="lines+markers", line=dict(color="#0ea5e9", width=2), marker=dict(size=6)))
    fig.update_layout(
        margin=dict(l=10, r=10, t=10, b=10),
        height=320,
        xaxis_title="Date",
        yaxis_title="Accuracy %",
        yaxis=dict(range=[0, 100]),
        showlegend=False,
    )
    return fig


def _render_system_status(st_module, system_status):
    checks = [
        ("Market Data", system_status.get("market_data", "Waiting")),
        ("Research Engine", system_status.get("research_engine", "Waiting")),
        ("Historical DB", system_status.get("historical_database", "Waiting")),
        ("Dashboard", system_status.get("dashboard", "Waiting")),
        ("Tests", system_status.get("tests", "Waiting")),
    ]
    cols = st_module.columns(5)
    for col, (name, value) in zip(cols, checks):
        render_metric_card(col, name, value)


def load_workflow_status():
    if not WORKFLOW_STATUS_FILE.exists():
        return {
            "last_workflow_run": "N/A",
            "workflow_duration_seconds": "N/A",
            "last_report_generated": "N/A",
            "research_status": "N/A",
        }

    try:
        payload = json.loads(WORKFLOW_STATUS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {
            "last_workflow_run": "N/A",
            "workflow_duration_seconds": "N/A",
            "last_report_generated": "N/A",
            "research_status": "N/A",
        }

    return {
        "last_workflow_run": payload.get("last_workflow_run", "N/A"),
        "workflow_duration_seconds": payload.get("workflow_duration_seconds", payload.get("execution_time_seconds", "N/A")),
        "last_report_generated": payload.get("last_report_generated", "N/A"),
        "research_status": payload.get("research_status", payload.get("status", "N/A")),
    }


def _cached_report_payload():
    report = STORAGE.load_latest_report()
    if isinstance(report, dict):
        return report
    return {}


def _fallback_market_snapshot():
    report = _cached_report_payload()
    market = report.get("Raw Engine Report", {}).get("market", {})
    rows = market.get("internals_rows", []) if isinstance(market, dict) else []
    snapshot = {}
    for row in rows:
        symbol = row.get("Asset")
        if not symbol:
            continue
        snapshot[symbol] = {
            "price": row.get("Price", "N/A"),
            "change": row.get("Daily %", "N/A"),
            "stale": True,
        }
    return snapshot


def _fallback_market_internals():
    report = _cached_report_payload()
    internals = report.get("Market Internals", [])
    if isinstance(internals, dict):
        return internals

    converted = {}
    for row in internals or []:
        asset = row.get("Asset")
        if not asset:
            continue
        converted[asset] = {
            "price": row.get("Price", "N/A"),
            "daily_change_percent": row.get("Daily %", "N/A"),
            "direction": row.get("Direction", "N/A"),
            "stale": True,
        }
    return converted


def _fallback_macro_events():
    report = _cached_report_payload()
    return report.get("Macro Events", [])


def _fallback_historical_matches():
    report = _cached_report_payload()
    return report.get("Historical Match", {})


def _fallback_leadership():
    report = _cached_report_payload()
    raw = report.get("Leadership", {})
    if isinstance(raw, dict) and "rows" in raw:
        converted = {}
        for row in raw.get("rows", []):
            sector = row.get("Sector")
            if not sector:
                continue
            converted[sector] = {
                "score": row.get("Score (%)", "N/A"),
                "status": row.get("Status", "Neutral"),
                "stale": True,
            }
        return converted
    if isinstance(raw, dict):
        return raw
    return {}


def _run_refresh_button(refresh_service):
    if "oe_refresh_running" not in st.session_state:
        st.session_state["oe_refresh_running"] = False

    clicked = st.button(
        "Refresh OPENEDGE",
        type="primary",
        disabled=bool(st.session_state.get("oe_refresh_running", False)),
        width="stretch",
    )
    if not clicked:
        return

    st.session_state["oe_refresh_running"] = True
    try:
        with st.spinner("Refreshing OPENEDGE..."):
            result = refresh_service.run_refresh()

        cache_data = getattr(st, "cache_data", None)
        if cache_data is not None and hasattr(cache_data, "clear"):
            cache_data.clear()

        if result.get("success"):
            _toast_success(result.get("message", "OPENEDGE refreshed successfully"))
            st.rerun()

        _toast_error(result.get("message", "Refresh failed. Previous report remains available."))
    except Exception:
        _toast_error("Refresh failed safely. Previous report remains available.")
    finally:
        st.session_state["oe_refresh_running"] = False


def main():
    st.set_page_config(page_title="OPENEDGE", page_icon="📈", layout="wide")
    inject_styles(st)

    if "oe_refresh_seconds" not in st.session_state:
        st.session_state["oe_refresh_seconds"] = 30

    interval_options = [15, 30, 60, 120, 300]
    current_interval = st.session_state.get("oe_refresh_seconds", 30)
    if current_interval not in interval_options:
        st.session_state["oe_refresh_seconds"] = 30

    refresh_service = RefreshService(BASE_DIR)
    health_service = HealthService(BASE_DIR)

    with st.expander("Refresh Controls", expanded=True):
        st.checkbox("Enable auto-refresh", value=st.session_state.get("oe_auto_refresh", False), key="oe_auto_refresh")
        st.selectbox(
            "Auto-refresh interval (seconds)",
            options=interval_options,
            key="oe_refresh_seconds",
        )
        if st.button("Refresh now"):
            st.rerun()
        _run_refresh_button(refresh_service)
        selected_interval = st.session_state.get("oe_refresh_seconds", 30)
        st.caption(f"Current interval: {selected_interval}s")

        refresh_status = refresh_service.get_refresh_status()
        status_cols = st.columns(3)
        status_cols[0].markdown(f"**Last successful refresh:** {refresh_status.get('last_successful_refresh', 'N/A')}")
        status_cols[1].markdown(f"**Refresh duration:** {refresh_status.get('last_duration_seconds', 'N/A')}s")
        status_cols[2].markdown(f"**Refresh status:** {'RUNNING' if refresh_status.get('is_running') else refresh_status.get('last_message', 'N/A')}")

    if st.session_state.get("oe_auto_refresh", False):
        if st_autorefresh is not None:
            st_autorefresh(interval=int(st.session_state.get("oe_refresh_seconds", 60)) * 1000, key="oe_dashboard_autorefresh")
        else:
            st.info("Auto-refresh is unavailable because streamlit-autorefresh is not installed in this environment.")

    generated_at = datetime.now().astimezone()

    source_warnings = []

    snapshot_result = safe_source_call("Yahoo market data", get_market_snapshot_with_cache, fallback_fn=lambda: (_fallback_market_snapshot(), datetime.now()))
    if snapshot_result.warning:
        source_warnings.append(snapshot_result.warning)
    snapshot, _ = snapshot_result.value if snapshot_result.value else ({}, datetime.now())

    internals_result = safe_source_call("Market internals", get_market_internals_with_cache, fallback_fn=lambda: (_fallback_market_internals(), datetime.now()))
    if internals_result.warning:
        source_warnings.append(internals_result.warning)
    market_internals, internals_fetched_at = internals_result.value if internals_result.value else ({}, datetime.now())

    macro_result = safe_source_call("Macro events", get_macro_events, fallback_fn=_fallback_macro_events)
    if macro_result.warning:
        source_warnings.append(macro_result.warning)
    macro_events = macro_result.value or []

    historical_result_data = safe_source_call(
        "Historical CSV/database",
        lambda: get_historical_matches(CSV_FILE, top_n=5),
        fallback_fn=_fallback_historical_matches,
    )
    if historical_result_data.warning:
        source_warnings.append(historical_result_data.warning)
    historical_result = historical_result_data.value or {}

    leadership_result = safe_source_call(
        "Leadership data",
        get_leadership_with_fallback,
        fallback_fn=lambda: (_fallback_leadership(), datetime.now(), True),
    )
    if leadership_result.warning:
        source_warnings.append(leadership_result.warning)
    leadership, _, used_fallback = leadership_result.value if leadership_result.value else ({}, datetime.now(), True)

    latest_signal = load_latest_signal()
    history_df = load_signal_history()
    validation_engine = ValidationEngine(db_path=CSV_FILE, journal_path=JOURNAL_FILE, reports_dir=BASE_DIR / "reports")

    engine = IntelligenceEngine(
        latest_signal=latest_signal,
        market_internals=market_internals,
        leadership=leadership,
        macro_events=macro_events,
        historical_matches=historical_result,
        market_snapshot=snapshot,
        history_df=history_df,
    )
    report = engine.build_report()
    workflow_status = load_workflow_status()
    health = health_service.get_health()
    market = report.get("market", {})
    macro = report.get("macro", {})
    leadership_report = report.get("leadership", {})
    historical = report.get("historical", {})
    summary = report.get("summary", {})

    st.markdown("<div class='oe-shell'><div class='oe-kicker'>Morning Research Terminal</div><h1 class='oe-title'>OPENEDGE</h1><p class='oe-subtitle'>Research Before Risk</p></div>", unsafe_allow_html=True)

    for warning in source_warnings:
        st.warning(warning)

    if health.get("application_status") != "healthy":
        st.warning("System health is degraded. OPENEDGE is operating with available data and stale fallbacks where needed.")

    meta_cols = st.columns(5)
    meta_cols[0].markdown(f"<div class='oe-meta-card'><strong>Current Date</strong><br>{generated_at.strftime('%Y-%m-%d')}</div>", unsafe_allow_html=True)
    meta_cols[1].markdown(f"<div class='oe-meta-card'><strong>Current Time</strong><br>{generated_at.strftime('%H:%M:%S %Z')}</div>", unsafe_allow_html=True)
    meta_cols[2].markdown(f"<div class='oe-meta-card'><strong>OPENEDGE Version</strong><br>{DISPLAY_VERSION}</div>", unsafe_allow_html=True)
    meta_cols[3].markdown(f"<div class='oe-meta-card'><strong>Last Market Refresh</strong><br>{internals_fetched_at.strftime('%H:%M:%S')}</div>", unsafe_allow_html=True)
    meta_cols[4].markdown(f"<div class='oe-meta-card'><strong>Health</strong><br>{health.get('application_status', 'unknown').upper()}</div>", unsafe_allow_html=True)

    render_section_header(st, "Workflow Automation")
    w1, w2, w3, w4 = st.columns(4)
    render_metric_card(w1, "Last Workflow Run", workflow_status.get("last_workflow_run", "N/A"))
    duration = workflow_status.get("workflow_duration_seconds", "N/A")
    duration_value = f"{duration}s" if isinstance(duration, (int, float)) else str(duration)
    render_metric_card(w2, "Workflow Duration", duration_value)
    render_metric_card(w3, "Last Report Generated", workflow_status.get("last_report_generated", "N/A"))
    render_metric_card(w4, "Research Status", workflow_status.get("research_status", "N/A"))

    render_section_header(st, "System Status")
    _render_system_status(st, summary.get("system_status", {}))

    render_section_header(st, "Research Validation")
    validation_summary = validation_engine.summary()
    rolling_20 = validation_engine.rolling_accuracy(window=20)
    by_regime = validation_engine.accuracy_by_market_regime().get("items", [])
    confidence_calibration = validation_engine.confidence_calibration().get("items", [])
    monthly = validation_engine.monthly_accuracy().get("items", [])

    v1, v2, v3, v4, v5 = st.columns(5)
    render_metric_card(v1, "Total Signals", validation_summary.get("total_signals", 0))
    render_metric_card(v2, "Correct Signals", validation_summary.get("correct_signals", 0))
    render_metric_card(v3, "Incorrect Signals", validation_summary.get("incorrect_signals", 0))
    render_metric_card(v4, "Overall Accuracy", f"{float(validation_summary.get('overall_accuracy', 0.0)):.2f}%")
    render_metric_card(v5, "Rolling 20-session Accuracy", f"{float(validation_summary.get('rolling_20_accuracy', 0.0)):.2f}%")

    v6, v7, v8, v9 = st.columns(4)
    render_metric_card(v6, "Average Confidence", f"{float(validation_summary.get('average_confidence', 0.0)):.2f}")
    render_metric_card(v7, "Best Regime", validation_summary.get("best_performing_regime", "N/A"))
    render_metric_card(v8, "Worst Regime", validation_summary.get("worst_performing_regime", "N/A"))
    render_metric_card(v9, "Avg Historical Similarity", f"{float(validation_summary.get('average_historical_similarity', 0.0)):.2f}%")

    if not rolling_20.get("points"):
        st.info("No validation records available yet. Run morning sessions to populate performance charts.")
    else:
        st.markdown("**Rolling Accuracy**")
        rolling_frame = pd.DataFrame(rolling_20.get("points", []))
        if go is None:
            st.dataframe(rolling_frame, hide_index=True, width="stretch")
        else:
            fig = go.Figure(
                go.Scatter(
                    x=rolling_frame["date"],
                    y=rolling_frame["accuracy"],
                    mode="lines+markers",
                    line=dict(color="#0ea5e9", width=2),
                )
            )
            fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10), yaxis=dict(range=[0, 100]), showlegend=False)
            _safe_plotly_chart(st, fig)

    st.markdown("**Accuracy by Regime**")
    if by_regime:
        regime_frame = pd.DataFrame(by_regime)
        if go is None:
            st.dataframe(regime_frame, hide_index=True, width="stretch")
        else:
            fig = go.Figure(go.Bar(x=regime_frame["regime"], y=regime_frame["accuracy"], marker_color="#10b981"))
            fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10), yaxis=dict(range=[0, 100]), showlegend=False)
            _safe_plotly_chart(st, fig)
    else:
        st.info("No regime-level accuracy data available yet.")

    st.markdown("**Confidence Calibration**")
    if confidence_calibration:
        confidence_frame = pd.DataFrame(confidence_calibration)
        if go is None:
            st.dataframe(confidence_frame, hide_index=True, width="stretch")
        else:
            fig = go.Figure(go.Bar(x=confidence_frame["band"], y=confidence_frame["accuracy_percent"], marker_color="#f59e0b"))
            fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10), yaxis=dict(range=[0, 100]), showlegend=False)
            _safe_plotly_chart(st, fig)
    else:
        st.info("No confidence band records available yet.")

    st.markdown("**Monthly Accuracy**")
    if monthly:
        monthly_frame = pd.DataFrame(monthly)
        if go is None:
            st.dataframe(monthly_frame, hide_index=True, width="stretch")
        else:
            fig = go.Figure(go.Bar(x=monthly_frame["month"], y=monthly_frame["accuracy"], marker_color="#6366f1"))
            fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10), yaxis=dict(range=[0, 100]), showlegend=False)
            _safe_plotly_chart(st, fig)
    else:
        st.info("No monthly validation data available yet.")

    render_section_header(st, "Today's Decision", "Executive snapshot for the pre-market session")
    decision_cells = [
        ("Market Regime", f"{market.get('market_regime', 'N/A')} {render_status_badge(market.get('market_regime', 'N/A'))}"),
        ("Bias", f"{market.get('bias', 'N/A')} {render_status_badge(market.get('bias', 'N/A'))}"),
        ("Confidence", f"{market.get('confidence', 'N/A')}/100"),
        ("Opening Auction Risk", f"{market.get('opening_risk', 'N/A')}/10"),
        ("Opportunity Score", f"{market.get('opportunity_score', 'N/A')}/10"),
        ("Opening Style", market.get("opening_style", "N/A")),
        ("Primary Risk", (summary.get("key_risks", ["No elevated risk catalyst identified"]) or ["No elevated risk catalyst identified"])[0]),
        ("Suggested Focus", summary.get("todays_focus", "N/A")),
    ]
    decision_html = "".join([f"<div class='oe-cell'><div class='oe-cell-label'>{label}</div><div class='oe-cell-value'>{value}</div></div>" for label, value in decision_cells])
    st.markdown(f"<div class='oe-shell'><div class='oe-decision-grid'>{decision_html}</div></div>", unsafe_allow_html=True)

    render_section_header(st, "KPI Dashboard")
    k1, k2, k3, k4, k5 = st.columns(5)
    render_metric_card(k1, "Confidence", f"{market.get('confidence', 'N/A')}/100")
    render_metric_card(k2, "Opening Auction Risk", f"{market.get('opening_risk', 'N/A')}/10")
    render_metric_card(k3, "Bias", market.get("bias", "N/A"))
    render_metric_card(k4, "Opportunity Score", f"{market.get('opportunity_score', 'N/A')}/10")
    render_metric_card(k5, "Market Regime", market.get("market_regime", "N/A"))
    confidence_value = float(market.get("confidence", 0)) if market.get("confidence") not in (None, "N/A") else 0.0
    st.progress(max(0.0, min(1.0, confidence_value / 100.0)))

    render_section_header(st, "Market Internals")
    st.dataframe(market_internals_table(market.get("internals_rows", [])), hide_index=True, width="stretch")
    st.caption(market.get("internals_summary", "N/A"))

    render_section_header(st, "Leadership")
    if used_fallback:
        st.info("Leadership is partially using last known values due to temporary data gaps.")
    leader_chart = leadership_chart(leadership_report.get("rows", []))
    if isinstance(leader_chart, pd.DataFrame):
        st.dataframe(leader_chart, hide_index=True, width="stretch")
    elif leader_chart is not None:
        _safe_plotly_chart(st, leader_chart)
    else:
        st.info("Leadership chart unavailable.")

    render_section_header(st, "Macro Events")
    st.dataframe(macro_events_styled_table(macro.get("today_events", [])), hide_index=True, width="stretch")
    render_metric_card(st, "Overall Macro Risk", macro.get("macro_risk", "N/A"))

    render_section_header(st, "Historical Match")
    best_match = historical.get("best_match", {})
    h1, h2, h3, h4 = st.columns(4)
    render_metric_card(h1, "Best Match", best_match.get("date", "N/A"))
    render_metric_card(h2, "Similarity", f"{float(best_match.get('similarity', 0.0)):.2f}%")
    render_metric_card(h3, "Expected Outcome", historical.get("expected_outcome", "N/A"))
    render_metric_card(h4, "Historical Confidence", historical.get("historical_confidence", "N/A"))
    hist_chart = historical_matches_chart(historical.get("rows", []))
    if isinstance(hist_chart, pd.DataFrame):
        st.dataframe(hist_chart, hide_index=True, width="stretch")
    elif hist_chart is not None:
        _safe_plotly_chart(st, hist_chart)

    render_section_header(st, "Performance")
    performance = summary.get("performance", {})
    p1, p2, p3, p4 = st.columns(4)
    render_metric_card(p1, "Signals Tracked", performance.get("signals_tracked", 0))
    render_metric_card(p2, "Correct Calls", performance.get("correct_calls", 0))
    render_metric_card(p3, "Incorrect Calls", performance.get("incorrect_calls", 0))
    render_metric_card(p4, "Historical Accuracy", f"{float(performance.get('historical_accuracy') or 0.0):.2f}%")
    rolling_chart = rolling_accuracy_chart(performance.get("rolling_accuracy", []))
    if isinstance(rolling_chart, pd.DataFrame):
        st.dataframe(rolling_chart, hide_index=True, width="stretch")
    elif rolling_chart is not None:
        _safe_plotly_chart(st, rolling_chart)

    render_section_header(st, "AI Morning Brief", "Executive research narrative")
    st.markdown("<div class='oe-brief'>", unsafe_allow_html=True)
    st.markdown("**Executive Summary**")
    st.write(summary.get("executive_summary", "N/A"))
    st.markdown("**Today's Focus**")
    st.write(summary.get("todays_focus", "N/A"))
    st.markdown("**Primary Risks**")
    _render_bullet_lines(st, summary.get("key_risks", []))
    st.markdown("**Strengths**")
    _render_bullet_lines(st, summary.get("strengths", []))
    st.markdown("**Weaknesses**")
    _render_bullet_lines(st, summary.get("weaknesses", []))
    st.markdown("**Research Conclusion**")
    st.write(summary.get("research_conclusion", "N/A"))
    st.markdown("</div>", unsafe_allow_html=True)

    render_footer(st, DISPLAY_VERSION, generated_at)


if __name__ == "__main__":
    main()

