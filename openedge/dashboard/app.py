from pathlib import Path

import pandas as pd
import streamlit as st

from openedge.analytics import explain
from openedge.data.market import get_market_snapshot
from openedge.models.score_engine import (
    market_bias,
    opening_auction_risk,
    opportunity_score,
)
from openedge.models.leadership_engine import evaluate_sector_leadership

BASE_DIR = Path(__file__).resolve().parents[2]
CSV_FILE = BASE_DIR / "openedge_db.csv"


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


def leadership_table(leadership):
    rows = []
    for sector, values in leadership.items():
        rows.append(
            {
                "Sector": sector,
                "Score (%)": values.get("score", 0.0),
                "Status": values.get("status", "Neutral"),
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


def main():
    st.set_page_config(page_title="OPENEDGE", page_icon="📈", layout="wide")
    st.title("📈 OPENEDGE")
    st.subheader("Research Before Risk")

    snapshot = get_market_snapshot()
    bias, confidence = market_bias(snapshot)
    oar = opening_auction_risk(snapshot)
    oos = opportunity_score(bias, oar)
    regime = classify_market_regime(snapshot)
    leadership = evaluate_sector_leadership()
    latest_signal = load_latest_signal()
    history_df = load_signal_history()

    st.header("Today's Intelligence")
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Confidence", confidence)
    col2.metric("Opening Auction Risk", oar)
    col3.metric("Bias", bias)
    col4.metric("Opportunity Score", oos)
    col5.metric("Market Regime", regime)

    st.progress(confidence / 100)
    st.write(f"Market Bias: {format_bias_with_color(bias)}")
    st.info(intelligence_explanation(bias))

    st.header("Market Snapshot")
    snap_cols = st.columns(4)
    symbols = ["SPY", "DIA", "QQQ", "VIX"]
    for col, symbol in zip(snap_cols, symbols):
        values = snapshot.get(symbol, {"price": None, "change": None})
        col.markdown(format_snapshot_card(symbol, values))

    st.header("Morning Brief")
    st.info(morning_brief(bias, regime, confidence, oar, oos))

    st.header("Leadership")
    st.dataframe(leadership_table(leadership), hide_index=True, width="stretch")

    st.divider()

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


if __name__ == "__main__":
    main()

