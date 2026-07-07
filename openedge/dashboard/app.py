import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from openedge.data.market import get_market_snapshot
except ModuleNotFoundError:
    from data.market import get_market_snapshot

st.set_page_config(
    page_title="OPENEDGE",
    page_icon="📈",
    layout="wide"
)

st.title("📈 OPENEDGE")
snapshot = get_market_snapshot()
st.subheader("Research Before Risk")

col1, col2, col3 = st.columns(3)

col1.metric("Confidence", "--")

col2.metric("Opening Auction Risk", "--")

col3.metric("Bias", "--")

st.header("📊 Market Snapshot")

for symbol, values in snapshot.items():
    st.write(
        f"**{symbol}** : {values['price']} ({values['change']}%)"
    )

st.divider()

st.header("Today's Research")

st.info("OPENEDGE v1.0 is now running 🚀")

