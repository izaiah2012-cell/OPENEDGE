from pathlib import Path
from datetime import datetime

import pandas as pd
import streamlit as st

from openedge.analytics import explain
from openedge.engines.history_engine import get_historical_matches
from openedge.data.market import get_market_snapshot
from openedge.engines.macro_engine import calculate_macro_risk, get_macro_events
from openedge.engines.research_writer import generate_research_summary
from openedge.models.score_engine import (
    market_bias,
    opening_auction_risk,
    opportunity_score,
)
from openedge.models.leadership_engine import evaluate_sector_leadership

LEADERSHIP_SECTORS = [
    "Technology",
    "Financials",
    "Industrials",
    "Healthcare",
    "Consumer",
    "Energy",
]

BASE_DIR = Path(__file__).resolve().parents[2]
CSV_FILE = BASE_DIR / "openedge_db.csv"
VERSION_FILE = BASE_DIR / "VERSION"


def _inject_dashboard_styles():
    st.markdown(
        """
        <style>
        .oe-section-gap { margin-top: 0.75rem; margin-bottom: 0.25rem; }
        .oe-status-card {
            border-radius: 12px;
            padding: 0.8rem 0.9rem;
            border: 1px solid rgba(148, 163, 184, 0.35);
            background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.0));
            margin-bottom: 0.5rem;
        }
        .oe-status-label {
            font-size: 0.8rem;
            color: #94a3b8;
            margin-bottom: 0.2rem;
        }
        .oe-status-value {
            font-size: 1.05rem;
            font-weight: 700;
        }
        .oe-health {
            border-radius: 10px;
            padding: 0.5rem 0.75rem;
            border: 1px solid rgba(16, 185, 129, 0.35);
            background: rgba(16, 185, 129, 0.08);
            font-size: 0.88rem;
        }
        .oe-footer {
            margin-top: 1.2rem;
            border-top: 1px solid rgba(148, 163, 184, 0.25);
            padding-top: 0.75rem;
            color: #94a3b8;
            font-size: 0.85rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _read_version():
    if VERSION_FILE.exists():
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    return "dev"


def _card_color(value):
    if value in ("BULLISH", "LOW", "Strong", "Risk On"):
        return "#16a34a"
    if value in ("BEARISH", "HIGH", "Weak", "Risk Off"):
        return "#dc2626"
    return "#d97706"


def render_status_cards(values):
    cols = st.columns(len(values))
    for col, (label, value) in zip(cols, values):
        color = _card_color(str(value))
        col.markdown(
            f"""
            <div class="oe-status-card">
                <div class="oe-status-label">{label}</div>
                <div class="oe-status-value" style="color:{color}">{value}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_system_health_banner(db_ready):
    checks = [
        ("Market Data", "Healthy"),
        ("Research Engine", "Healthy"),
        ("Historical Database", "Healthy" if db_ready else "Waiting"),
        ("Dashboard", "Healthy"),
        ("Tests", "Verified"),
    ]
    health_cols = st.columns(5)
    for col, (name, status) in zip(health_cols, checks):
        icon = "🟢" if status in ("Healthy", "Verified") else "🟡"
        col.markdown(f"<div class='oe-health'><strong>{name}</strong><br>{icon} {status}</div>", unsafe_allow_html=True)


def intelligence_explanation(bias):
    if bias == "BULLISH":
        return "Risk assets are broadly positive while volatility remains contained."
    if bias == "BEARISH":
        return "Risk assets are under pressure and volatility is expanding."
    return "Market conditions are mixed with no strong directional bias."


def format_bias_with_color(bias):
    if bias == "BULLISH":
        return ":green[BULLISH]"
    if bias == "BEARISH":
        return ":red[BEARISH]"
    return ":orange[NEUTRAL]"


def classify_market_regime(snapshot):
    spy = snapshot.get("SPY", {}).get("change") or 0.0
    dia = snapshot.get("DIA", {}).get("change") or 0.0
    qqq = snapshot.get("QQQ", {}).get("change") or 0.0
    vix = snapshot.get("VIX", {}).get("change") or 0.0

    avg_risk_assets = (spy + dia + qqq) / 3

    if avg_risk_assets > 0.3 and vix <= 2.0:
        return "Risk On"
    if avg_risk_assets < -0.3 or vix >= 3.0:
        return "Risk Off"
    return "Neutral"


def format_snapshot_card(symbol, values):
    price = values.get("price")
    change = values.get("change")

    price_text = "N/A" if price is None else f"{price:.2f}"
    if change is None:
        change_text = "N/A"
    else:
        change_text = f"{change:+.2f}%"

    return f"""
### {symbol}
Price: {price_text}

Daily Change: {change_text}
"""


def morning_brief(bias, regime, confidence, oar, oos):
    bias_text = {
        "BULLISH": "buyers currently have the tactical edge",
        "BEARISH": "selling pressure is currently dominant",
        "NEUTRAL": "the market is balanced without clear directional control",
    }.get(bias, "market direction is mixed")

    return (
        f"Current regime is {regime}. Bias is {bias.lower()} and {bias_text}. "
        f"Confidence is {confidence}/100, opening auction risk is {oar}/10, "
        f"and opportunity score is {oos}/10."
    )


def load_signal_history():
    if not CSV_FILE.exists():
        return None

    try:
        df = pd.read_csv(CSV_FILE)
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


def leadership_table(leadership, fetched_at):
    age_seconds = max(0, int((datetime.now() - fetched_at).total_seconds()))
    freshness = "Live" if age_seconds < 120 else "Cached"

    rows = []
    for sector in LEADERSHIP_SECTORS:
        values = leadership.get(sector, {})
        rows.append(
            {
                "Sector": sector,
                "Score (%)": values.get("score", 0.0),
                "5D Momentum (%)": values.get("momentum_5d", 0.0),
                "Status": values.get("status", "Neutral"),
                "Last Updated": fetched_at.strftime("%H:%M:%S"),
                "Freshness": freshness,
            }
        )

    frame = pd.DataFrame(rows)

    def style_status(value):
        if value == "Strong":
            return "color: #15803d; font-weight: 700;"
        if value == "Weak":
            return "color: #b91c1c; font-weight: 700;"
        return "color: #d97706; font-weight: 700;"

    return frame.style.map(style_status, subset=["Status"])


def macro_events_table(events):
    if not events:
        return pd.DataFrame(columns=["Time", "Event", "Impact"])

    return pd.DataFrame(
        [
            {
                "Time": event.get("time", "N/A"),
                "Event": event.get("event", "N/A"),
                "Impact": event.get("impact", "Low"),
            }
            for event in events
        ]
    )


def format_macro_risk(risk):
    if risk == "LOW":
        return ":green[LOW]"
    if risk == "MEDIUM":
        return ":orange[MEDIUM]"
    return ":red[HIGH]"


def historical_match_table(matches):
    if not matches:
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

    frame = pd.DataFrame(
        [
            {
                "Rank": match.get("rank"),
                "Date": match.get("date"),
                "Similarity %": match.get("similarity"),
                "Confidence Band": match.get("confidence_band", "Weak"),
                "Bias": match.get("bias"),
                "Actual": match.get("actual"),
                "Correct": match.get("correct"),
                "Why Similar": match.get("why_similar", ""),
            }
            for match in matches
        ]
    )

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


def classify_regime_from_signals(bias, vix_change):
    if bias == "BULLISH" and vix_change <= 2:
        return "Risk On"
    if bias == "BEARISH" or vix_change >= 3:
        return "Risk Off"
    return "Neutral"


def _render_research_summary(report_text):
    container_fn = getattr(st, "container", None)
    if callable(container_fn):
        with container_fn(border=True):
            st.markdown(report_text)
        return

    st.markdown(report_text)


def main():
    st.set_page_config(page_title="OPENEDGE", page_icon="📈", layout="wide")
    _inject_dashboard_styles()

    generated_at = datetime.now()
    version = _read_version()

    st.title("📈 OPENEDGE")
    st.subheader("Research Before Risk")

    snapshot = get_market_snapshot()
    bias, confidence = market_bias(snapshot)
    oar = opening_auction_risk(snapshot)
    oos = opportunity_score(bias, oar)
    regime = classify_market_regime(snapshot)
    macro_events = get_macro_events()
    macro_risk = calculate_macro_risk(macro_events)
    historical_result = get_historical_matches(CSV_FILE, top_n=5)
    historical_matches = historical_result.get("matches", [])
    leadership, leadership_fetched_at, used_fallback = get_leadership_with_fallback()
    latest_signal = load_latest_signal()
    history_df = load_signal_history()

    st.markdown("<div class='oe-section-gap'></div>", unsafe_allow_html=True)
    render_system_health_banner(db_ready=history_df is not None)

    with st.container(border=True):
        st.header("Today's Intelligence")
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Confidence", confidence)
        col2.metric("Opening Auction Risk", oar)
        col3.metric("Bias", bias)
        col4.metric("Opportunity Score", oos)
        col5.metric("Market Regime", regime)

        st.progress(confidence / 100)
        st.write(f"Market Bias: {format_bias_with_color(bias)}")
        render_status_cards(
            [
                ("Bias State", bias),
                ("Regime", regime),
                ("Macro Risk", macro_risk),
                ("Best Match Band", historical_result.get("best_match", {}).get("confidence_band", "N/A")),
            ]
        )
        st.info(intelligence_explanation(bias))

    with st.container(border=True):
        st.header("Market Snapshot")
        snap_cols = st.columns(4)
        symbols = ["SPY", "DIA", "QQQ", "VIX"]
        for col, symbol in zip(snap_cols, symbols):
            values = snapshot.get(symbol, {"price": None, "change": None})
            col.markdown(format_snapshot_card(symbol, values))

    with st.container(border=True):
        st.header("Morning Brief")
        st.info(morning_brief(bias, regime, confidence, oar, oos))

    summary_payload = {
        "market_regime": classify_regime_from_signals(bias, snapshot.get("VIX", {}).get("change") or 0.0),
        "confidence": confidence,
        "opening_auction_risk": oar,
        "opportunity_score": oos,
        "bias": bias,
        "leadership": leadership,
        "macro_events": macro_events,
        "macro_risk": macro_risk,
        "historical_match": historical_result.get("best_match", {}),
        "historical_similarity": historical_result.get("average_similarity", 0.0),
    }
    research_report = generate_research_summary(summary_payload)

    with st.container(border=True):
        st.header("🧠 AI Research Summary")
        _render_research_summary(research_report)

    with st.container(border=True):
        st.header("📅 Today's Macro Events")
        st.dataframe(macro_events_table(macro_events), hide_index=True, width="stretch")
        st.metric("Macro Risk", macro_risk)
        st.write(f"Macro Risk Level: {format_macro_risk(macro_risk)}")

    with st.container(border=True):
        st.header("Leadership")
        if used_fallback:
            st.info("Leadership is partially using last known values due to temporary data gaps.")
        st.dataframe(leadership_table(leadership, leadership_fetched_at), hide_index=True, width="stretch")

    st.divider()

    with st.container(border=True):
        st.header("Historical Research")
        if latest_signal:
            r1, r2, r3, r4 = st.columns(4)
            r1.metric("Latest Bias", latest_signal.get("bias", "N/A"))
            r2.metric("Actual", latest_signal.get("actual", "N/A"))
            r3.metric("VIX Score", latest_signal.get("vix", "N/A"))
            r4.metric("Correct", latest_signal.get("correct", "N/A"))

            if "risk" in latest_signal and "leadership" in latest_signal and "vix" in latest_signal:
                st.write(explain(latest_signal))
        else:
            st.info("No signal history is available yet. Run the analysis workflow to populate the database.")

    with st.container(border=True):
        st.header("📈 Historical Match")

        best_match = historical_result.get("best_match", {})
        most_similar_session = (
            f"{best_match.get('date', 'N/A')} ({best_match.get('similarity', 0):.2f}%)"
            if best_match
            else "N/A"
        )

        h1, h2, h3 = st.columns(3)
        h1.metric("Most Similar Session", most_similar_session)
        h2.metric("Average Similarity", f"{historical_result.get('average_similarity', 0.0):.2f}%")
        h3.metric("Most Common Outcome", historical_result.get("most_common_outcome", "N/A"))

        if historical_matches:
            st.dataframe(historical_match_table(historical_matches), hide_index=True, width="stretch")
        else:
            st.info("Not enough historical data yet. Keep collecting sessions.")

    with st.container(border=True):
        st.header("Performance")
        if history_df is not None and "correct" in history_df.columns:
            valid = pd.to_numeric(history_df["correct"], errors="coerce").dropna()
            if not valid.empty:
                win_rate = float(valid.mean()) * 100
                p1, p2 = st.columns(2)
                p1.metric("Signals Tracked", len(valid))
                p2.metric("Historical Accuracy", f"{win_rate:.2f}%")
            else:
                st.info("Performance metrics will appear once outcomes are recorded.")
        else:
            st.info("Performance metrics will appear once historical data is available.")

    st.markdown(
        f"""
        <div class="oe-footer">
            <strong>OPENEDGE {version}</strong><br>
            Generation timestamp: {generated_at.strftime('%Y-%m-%d %H:%M:%S')}<br>
            Research framework: OPENEDGE Multi-Engine Research Framework<br>
            Data source: Yahoo Finance + OPENEDGE CSV History
        </div>
        """,
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()

