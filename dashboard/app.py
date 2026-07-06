import streamlit as st

st.set_page_config(
    page_title="OPENEDGE",
    page_icon="📈",
    layout="wide"
)

st.title("📈 OPENEDGE")

st.subheader("Research Before Risk")

col1, col2, col3 = st.columns(3)

col1.metric("Confidence", "--")

col2.metric("Opening Auction Risk", "--")

col3.metric("Bias", "--")

st.divider()

st.header("Today's Research")

st.info("OPENEDGE v1.0 is now running 🚀")