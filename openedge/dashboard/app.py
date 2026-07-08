from pathlib import Path

import pandas as pd
import streamlit as st

from openedge.analytics import explain
from openedge.data.market import get_market_snapshot

BASE_DIR = Path(__file__).resolve().parents[2]
CSV_FILE = BASE_DIR / "openedge_db.csv"


def load_latest_signal():
    if not CSV_FILE.exists():
        return None

    try:
        df = pd.read_csv(CSV_FILE)
    except Exception:
        return None

    if df.empty:
        return None

    return df.iloc[-1].to_dict()


def main():
    st.set_page_config(page_title="OPENEDGE", page_icon="📈", layout="wide")
    st.title("📈 OPENEDGE")
    st.subheader("Research Before Risk")

    snapshot = get_market_snapshot()
    latest_signal = load_latest_signal()

    col1, col2, col3 = st.columns(3)
    col1.metric("Confidence", "--")
    col2.metric("Opening Auction Risk", "--")
    col3.metric("Bias", latest_signal.get("bias", "--") if latest_signal else "--")

    st.header("📊 Market Snapshot")
    for symbol, values in snapshot.items():
        st.write(f"**{symbol}** : {values['price']} ({values['change']}%)")

    st.divider()

    st.header("📈 Today's Signal")
    if latest_signal:
        st.success("Latest signal loaded from the project database")
        st.json(latest_signal)
        if "risk" in latest_signal and "leadership" in latest_signal and "vix" in latest_signal:
            st.write(explain(latest_signal))
    else:
        st.info("No signal history is available yet. Run the analysis workflow to populate the database.")

    st.header("🧠 OPENEDGE AI Analysis")
    st.info("AI analysis will be displayed when market data is available")


if __name__ == "__main__":
    main()

