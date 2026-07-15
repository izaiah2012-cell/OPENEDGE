import sys as _sys
from pathlib import Path as _Path
# Ensure repo root is importable on Streamlit Cloud (no pip install needed)
_repo_root = str(_Path(__file__).resolve().parents[2])
if _repo_root not in _sys.path:
    _sys.path.insert(0, _repo_root)

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
from openedge.utils.timeline_monitor import DecisionTimeline, BiasTransitionMonitor, ResearchQuality
from openedge.validation.validation_engine import ValidationEngine

LEADERSHIP_SECTORS = ["Technology", "Financials", "Industrials", "Healthcare", "Consumer", "Energy"]
CORE_MARKET_INTERNALS = ["SPY", "QQQ", "DIA", "VIX", "Gold", "Oil", "Dollar", "US10Y", "Bitcoin"]

BASE_DIR = Path(__file__).resolve().parents[2]
CSV_FILE = BASE_DIR / "openedge_db.csv"
VERSION_FILE = BASE_DIR / "VERSION"
DISPLAY_VERSION = "v1.1.0"
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
    if "Asset" in frame.columns:
        frame = frame[frame["Asset"].astype(str).isin(CORE_MARKET_INTERNALS)]

    if frame.empty:
        return pd.DataFrame(columns=["Asset", "Price", "Daily %", "Direction"])

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


def _render_refresh_controls(st_module, refresh_service):
    if "oe_refresh_seconds" not in st_module.session_state:
        st_module.session_state["oe_refresh_seconds"] = 30

    interval_options = [15, 30, 60, 120, 300]
    current_interval = st_module.session_state.get("oe_refresh_seconds", 30)
    if current_interval not in interval_options:
        st_module.session_state["oe_refresh_seconds"] = 30

    with st_module.expander("Refresh Controls", expanded=True):
        st_module.checkbox("Enable auto-refresh", value=st_module.session_state.get("oe_auto_refresh", False), key="oe_auto_refresh")
        st_module.selectbox(
            "Auto-refresh interval (seconds)",
            options=interval_options,
            key="oe_refresh_seconds",
        )

        col1, col2 = st_module.columns(2)
        with col1:
            if st_module.button("Refresh now"):
                st_module.rerun()
        with col2:
            _run_refresh_button(refresh_service)

        selected_interval = st_module.session_state.get("oe_refresh_seconds", 30)
        st_module.caption(f"Current interval: {selected_interval}s")

        refresh_status = refresh_service.get_refresh_status()
        status_cols = st_module.columns(3)
        status_cols[0].markdown(f"**Last successful refresh:** {refresh_status.get('last_successful_refresh', 'N/A')}")
        status_cols[1].markdown(f"**Refresh duration:** {refresh_status.get('last_duration_seconds', 'N/A')}s")
        status_cols[2].markdown(f"**Refresh status:** {'RUNNING' if refresh_status.get('is_running') else refresh_status.get('last_message', 'N/A')}")


def main():
    st.set_page_config(page_title="OPENEDGE", page_icon="📈", layout="wide")
    inject_styles(st)

    refresh_service = RefreshService(BASE_DIR)
    health_service = HealthService(BASE_DIR)

    _render_refresh_controls(st, refresh_service)

    if st.session_state.get("oe_auto_refresh", False):
        if st_autorefresh is not None:
            st_autorefresh(interval=int(st.session_state.get("oe_refresh_seconds", 60)) * 1000, key="oe_dashboard_autorefresh")
        else:
            st.info("Auto-refresh is unavailable because streamlit-autorefresh is not installed in this environment.")

    st.divider()

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

    # Compact Meta Info
    meta_cols = st.columns(5)
    meta_cols[0].markdown(f"<div class='oe-meta-card'><strong>Date</strong><br>{generated_at.strftime('%Y-%m-%d')}</div>", unsafe_allow_html=True)
    meta_cols[1].markdown(f"<div class='oe-meta-card'><strong>Time</strong><br>{generated_at.strftime('%H:%M:%S')}</div>", unsafe_allow_html=True)
    meta_cols[2].markdown(f"<div class='oe-meta-card'><strong>Version</strong><br>{DISPLAY_VERSION}</div>", unsafe_allow_html=True)
    meta_cols[3].markdown(f"<div class='oe-meta-card'><strong>Market Refresh</strong><br>{internals_fetched_at.strftime('%H:%M')}</div>", unsafe_allow_html=True)
    meta_cols[4].markdown(f"<div class='oe-meta-card'><strong>Status</strong><br>{health.get('application_status', 'unknown').upper()}</div>", unsafe_allow_html=True)

    st.divider()

    # ═════════════════════════════════════════════════════════════════════════════════════
    # HERO SECTION: TODAY'S DECISION
    # ═════════════════════════════════════════════════════════════════════════════════════
    render_section_header(st, "🎯 Today's Decision", "Pre-market executive snapshot")
    decision_cells = [
        ("Market Regime", f"{market.get('market_regime', 'N/A')} {render_status_badge(market.get('market_regime', 'N/A'))}"),
        ("Bias", f"{market.get('bias', 'N/A')} {render_status_badge(market.get('bias', 'N/A'))}"),
        ("Confidence", f"{market.get('confidence', 'N/A')}/100"),
        ("Opening Auction Risk", f"{market.get('opening_risk', 'N/A')}/10"),
        ("Opportunity Score", f"{market.get('opportunity_score', 'N/A')}/10"),
        ("Macro Risk", f"{macro.get('macro_risk', 'N/A')}"),
        ("Market Temperature", market.get("opening_style", "N/A")),
        ("Research Status", workflow_status.get("research_status", "N/A")),
        ("Last Updated", generated_at.strftime("%H:%M:%S")),
    ]
    decision_html = "".join([f"<div class='oe-cell'><div class='oe-cell-label'>{label}</div><div class='oe-cell-value'>{value}</div></div>" for label, value in decision_cells])
    st.markdown(f"<div class='oe-shell'><div class='oe-decision-grid'>{decision_html}</div></div>", unsafe_allow_html=True)
    st.markdown("")

    # ═════════════════════════════════════════════════════════════════════════════════════
    # MORNING BRIEF: Concise Executive Summary
    # ═════════════════════════════════════════════════════════════════════════════════════
    render_section_header(st, "📋 Morning Brief", "3-5 sentence executive summary")
    brief_points = [
        ("Today's Summary", summary.get("executive_summary", "No executive summary available.")),
        ("Today's Focus", summary.get("todays_focus", "N/A")),
        ("Primary Risks", "; ".join(summary.get("key_risks", [])[:2]) if summary.get("key_risks") else "N/A"),
        ("Strengths", "; ".join(summary.get("strengths", [])[:2]) if summary.get("strengths") else "N/A"),
        ("Weaknesses", "; ".join(summary.get("weaknesses", [])[:2]) if summary.get("weaknesses") else "N/A"),
        ("Expected Session Behaviour", market.get("opening_style", "N/A")),
    ]
    st.markdown("<div class='oe-brief'>", unsafe_allow_html=True)
    for label, value in brief_points:
        st.markdown(f"- **{label}:** {value}")
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("")

    # ═════════════════════════════════════════════════════════════════════════════════════
    # MARKET INTERNALS: Compact Table (9 Core Tickers)
    # ═════════════════════════════════════════════════════════════════════════════════════
    render_section_header(st, "📊 Market Internals", "Core market movers today")
    st.dataframe(market_internals_table(market.get("internals_rows", [])), hide_index=True, width="stretch")
    st.caption(market.get("internals_summary", "N/A"))
    st.markdown("")

    # ═════════════════════════════════════════════════════════════════════════════════════
    # LEADERSHIP: Horizontal Chart
    # ═════════════════════════════════════════════════════════════════════════════════════
    render_section_header(st, "👑 Leadership Trends")
    if used_fallback:
        st.info("Leadership data is using last known values due to temporary data gaps.")
    leader_chart = leadership_chart(leadership_report.get("rows", []))
    if isinstance(leader_chart, pd.DataFrame):
        st.dataframe(leader_chart, hide_index=True, width="stretch")
    elif leader_chart is not None:
        _safe_plotly_chart(st, leader_chart)
    else:
        st.info("Leadership chart unavailable.")
    st.markdown("")

    # ═════════════════════════════════════════════════════════════════════════════════════
    # MACRO EVENTS: Today Only
    # ═════════════════════════════════════════════════════════════════════════════════════
    render_section_header(st, "🌍 Today's Macro Calendar", "Economic calendar and data releases")
    st.dataframe(macro_events_styled_table(macro.get("today_events", [])), hide_index=True, width="stretch")
    st.markdown("")

    # ═════════════════════════════════════════════════════════════════════════════════════
    # AI RESEARCH SUMMARY: Core Insights
    # ═════════════════════════════════════════════════════════════════════════════════════
    render_section_header(st, "🔬 AI Research Summary")
    st.markdown("<div style='padding: 15px 0;'>", unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 1])
    with col1:
        st.markdown("**Executive Summary**")
        st.write(summary.get('executive_summary', 'N/A'))

        st.markdown("**Market Regime**")
        st.write(market.get('market_regime', 'N/A'))
        
        st.markdown("**Leadership Summary**")
        st.write(leadership_report.get('summary', 'N/A'))
    
    with col2:
        st.markdown("**Macro Summary**")
        st.write(macro.get('macro_summary', 'N/A'))
        
        st.markdown("**Today's Focus**")
        st.write(summary.get("todays_focus", "N/A"))
    
    st.markdown("**Research Conclusion**")
    st.write(summary.get("research_conclusion", "N/A"))
    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("")

    # ═════════════════════════════════════════════════════════════════════════════════════
    # COLLAPSIBLE SECTIONS: Historical, Performance, Validation, Charts
    # ═════════════════════════════════════════════════════════════════════════════════════

    # Historical Match Details
    with st.expander("📈 Historical Match Analysis", expanded=False):
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

    # Performance Details
    with st.expander("📊 Performance Metrics", expanded=False):
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

    # Validation Trends (moved from top)
    validation_summary = validation_engine.summary()
    rolling_20 = validation_engine.rolling_accuracy(window=20)
    by_regime = validation_engine.accuracy_by_market_regime().get("items", [])
    confidence_calibration = validation_engine.confidence_calibration().get("items", [])
    monthly = validation_engine.monthly_accuracy().get("items", [])

    with st.expander("✅ Validation Trends", expanded=False):
        v1, v2, v3, v4, v5 = st.columns(5)
        render_metric_card(v1, "Total Signals", validation_summary.get("total_signals", 0))
        render_metric_card(v2, "Correct", validation_summary.get("correct_signals", 0))
        render_metric_card(v3, "Incorrect", validation_summary.get("incorrect_signals", 0))
        render_metric_card(v4, "Overall Accuracy", f"{float(validation_summary.get('overall_accuracy', 0.0)):.2f}%")
        render_metric_card(v5, "Rolling 20-session", f"{float(validation_summary.get('rolling_20_accuracy', 0.0)):.2f}%")

        st.markdown("**Rolling Accuracy (20-session)**")
        if rolling_20.get("points"):
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
        else:
            st.info("No rolling accuracy data available yet.")

        st.markdown("**Accuracy by Regime**")
        if by_regime:
            regime_frame = pd.DataFrame(by_regime)
            if go is None:
                st.dataframe(regime_frame, hide_index=True, width="stretch")
            else:
                fig = go.Figure(go.Bar(x=regime_frame["regime"], y=regime_frame["accuracy"], marker_color="#10b981"))
                fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10), yaxis=dict(range=[0, 100]), showlegend=False)
                _safe_plotly_chart(st, fig)

        st.markdown("**Confidence Calibration**")
        if confidence_calibration:
            confidence_frame = pd.DataFrame(confidence_calibration)
            if go is None:
                st.dataframe(confidence_frame, hide_index=True, width="stretch")
            else:
                fig = go.Figure(go.Bar(x=confidence_frame["band"], y=confidence_frame["accuracy_percent"], marker_color="#f59e0b"))
                fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10), yaxis=dict(range=[0, 100]), showlegend=False)
                _safe_plotly_chart(st, fig)

        st.markdown("**Monthly Accuracy**")
        if monthly:
            monthly_frame = pd.DataFrame(monthly)
            if go is None:
                st.dataframe(monthly_frame, hide_index=True, width="stretch")
            else:
                fig = go.Figure(go.Bar(x=monthly_frame["month"], y=monthly_frame["accuracy"], marker_color="#6366f1"))
                fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10), yaxis=dict(range=[0, 100]), showlegend=False)
                _safe_plotly_chart(st, fig)
    # ═════════════════════════════════════════════════════════════════════════════════════
    # RESEARCH QUALITY BADGE
    # ═════════════════════════════════════════════════════════════════════════════════════
    quality_calc = ResearchQuality()
    quality_result = quality_calc.calculate_quality(report)
    stars_emoji = ResearchQuality.format_stars(quality_result["stars"])
    
    st.markdown("")
    quality_col1, quality_col2 = st.columns([3, 1])
    with quality_col1:
        render_section_header(st, "🎯 Research Quality")
        st.markdown(f"### {stars_emoji} {quality_result['description']}")
    with quality_col2:
        st.markdown(f"**Quality Score:** {quality_result['score']}%")

    st.markdown("")

    # ═════════════════════════════════════════════════════════════════════════════════════
    # DECISION TIMELINE
    # ═════════════════════════════════════════════════════════════════════════════════════
    with st.expander("📅 Decision Timeline", expanded=False):
        timeline = DecisionTimeline()
        today_events = timeline.get_today_timeline()
        
        if today_events:
            st.markdown("**Today's Decision Events:**")
            for event in today_events:
                ts = event.get("timestamp", "")
                event_type = event.get("type", "Unknown")
                details = event.get("details", {})
                st.markdown(f"- **{ts}** — {event_type}")
                if details:
                    st.caption(str(details))
        else:
            st.info("No decision events recorded yet. Events track workflow milestones and research confirmations.")

    # ═════════════════════════════════════════════════════════════════════════════════════
    # BIAS TRANSITION MONITOR
    # ═════════════════════════════════════════════════════════════════════════════════════
    with st.expander("🔄 Bias Transition Monitor", expanded=False):
        bias_monitor = BiasTransitionMonitor()
        transitions = bias_monitor.get_today_transitions()
        
        if transitions:
            st.markdown("**Today's Bias Transitions:**")
            for trans in transitions:
                ts = trans.get("timestamp", "")
                bias_before = trans.get("bias_before", "N/A")
                bias_after = trans.get("bias_after", "N/A")
                conf_before = trans.get("confidence_before", 0)
                conf_after = trans.get("confidence_after", 0)
                conf_change = trans.get("confidence_change", 0)
                reason = trans.get("reason", "No reason provided")
                
                st.markdown(f"**{ts}**")
                st.markdown(f"- Bias: {bias_before} → {bias_after}")
                st.markdown(f"- Confidence: {conf_before}% → {conf_after}% ({conf_change:+.0f}%)")
                st.markdown(f"- Reason: {reason}")
                st.divider()
        else:
            st.info("No bias transitions today. Transitions are recorded when the market bias changes significantly or confidence levels shift.")

    st.markdown("")

    # ═════════════════════════════════════════════════════════════════════════════════════
    # RESEARCH NOTES EXPANDER
    # ═════════════════════════════════════════════════════════════════════════════════════
    with st.expander("⚙️ Research Notes", expanded=False):
        st.markdown("**Primary Risks**")
        _render_bullet_lines(st, summary.get("key_risks", []))
        st.markdown("**Strengths**")
        _render_bullet_lines(st, summary.get("strengths", []))
        st.markdown("**Weaknesses**")
        _render_bullet_lines(st, summary.get("weaknesses", []))

    st.divider()

    render_footer(st, DISPLAY_VERSION, generated_at)


if __name__ == "__main__":
    main()

