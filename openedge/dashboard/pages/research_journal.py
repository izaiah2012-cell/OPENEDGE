"""
Research Journal – Daily entries, grading, statistics, export, and long-term learning.
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

from openedge.dashboard.components import inject_styles, render_footer, render_metric_card, render_section_header
from openedge.research import BiasTransitionHistory, ResearchGrader, ResearchInsightsEngine, ResearchJournal, ResearchStatistics

BASE_DIR = Path(__file__).resolve().parents[3]
DISPLAY_VERSION = "v1.2.0"


def _stars(stars: int) -> str:
    return "★★★★★"[:stars] + "☆☆☆☆☆"[: 5 - stars]


def main():
    try:
        st.set_page_config(page_title="OPENEDGE Research Journal", page_icon="📖", layout="wide")
    except Exception:
        pass

    inject_styles(st)
    journal = ResearchJournal(BASE_DIR)
    grader = ResearchGrader()
    frame = journal.load_days()
    statistics = ResearchStatistics(frame)
    insights = ResearchInsightsEngine(frame).generate()
    transitions = BiasTransitionHistory(BASE_DIR).today()

    st.markdown(
        "<div class='oe-shell'><div class='oe-kicker'>Research Memory</div>"
        "<h1 class='oe-title'>Research Journal</h1>"
        "<p class='oe-subtitle'>Daily learning history, grades, trends, and export.</p></div>",
        unsafe_allow_html=True,
    )

    summary = statistics.summary()
    cols = st.columns(5)
    render_metric_card(cols[0], "Daily Entries", summary.get("total_days", 0))
    render_metric_card(cols[1], "Average Score", f"{summary.get('average_score', 0.0):.1f}")
    render_metric_card(cols[2], "Average Similarity", f"{summary.get('average_similarity', 0.0):.1f}%")
    render_metric_card(cols[3], "Average Confidence", f"{summary.get('average_confidence', 0.0):.1f}")
    render_metric_card(cols[4], "Top Grade", summary.get("top_grade", "N/A"))

    render_section_header(st, "Grades & Statistics")
    grade_dist = statistics.grade_distribution()
    if not grade_dist.empty:
        chart_frame = grade_dist.reset_index()
        chart_frame.columns = ["Grade", "Count"]
        st.bar_chart(chart_frame.set_index("Grade"))
    else:
        st.info("No graded research days yet.")

    trend = statistics.weekly_trend()
    if not trend.empty:
        st.line_chart(trend.set_index("week"))

    render_section_header(st, "Search & Filters")
    search_term = st.text_input("Search journal", placeholder="Search comments, lessons, grades, or dates...")
    filter_cols = st.columns(4)
    with filter_cols[0]:
        grade_filter = st.selectbox("Grade", options=["All"] + sorted([g for g in grade_dist.index.astype(str).tolist()] if not grade_dist.empty else []))
    with filter_cols[1]:
        bias_filter = st.selectbox("Bias", options=["All", "Bullish", "Bearish", "Neutral", "N/A"])
    with filter_cols[2]:
        start_date = st.date_input("Start Date", value=datetime.now().date().replace(day=1))
    with filter_cols[3]:
        end_date = st.date_input("End Date", value=datetime.now().date())

    filtered = journal.search(
        search_term,
        grade="" if grade_filter == "All" else grade_filter,
        bias="" if bias_filter == "All" else bias_filter,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
    )

    render_section_header(st, "Daily Entries")
    if filtered.empty:
        st.info("No journal entries match the current filters.")
    else:
        display = filtered.copy()
        if "grade" not in display.columns:
            display["grade"] = ""
        if "research_score" not in display.columns:
            display["research_score"] = ""
        display["grade_display"] = display["grade"].astype(str).replace("", "N/A")
        display["research_score"] = pd.to_numeric(display["research_score"], errors="coerce").fillna(0.0)
        display["stars"] = display["research_score"].map(lambda value: _stars(int(round(min(max(value / 20.0, 1), 5)))))
        st.dataframe(
            display[
                [
                    "date",
                    "morning_bias",
                    "morning_confidence",
                    "morning_regime",
                    "similarity",
                    "research_score",
                    "grade_display",
                    "comments",
                    "lessons_learned",
                ]
            ],
            hide_index=True,
            width="stretch",
        )

    render_section_header(st, "Bias Transition History")
    if transitions:
        st.dataframe(pd.DataFrame(transitions), hide_index=True, width="stretch")
    else:
        st.info("No bias transitions recorded yet.")

    render_section_header(st, "Insights")
    for insight in insights[:5]:
        st.markdown(f"- {insight}")

    render_section_header(st, "Export")
    export_cols = st.columns(2)
    csv_path = journal.export_csv()
    json_path = journal.export_json()
    with export_cols[0]:
        st.download_button(
            "Export CSV",
            data=csv_path.read_bytes(),
            file_name="research_memory.csv",
            mime="text/csv",
            width="stretch",
        )
    with export_cols[1]:
        st.download_button(
            "Export JSON",
            data=json_path.read_bytes(),
            file_name="research_memory.json",
            mime="application/json",
            width="stretch",
        )

    render_section_header(st, "Grading Guide")
    st.markdown(f"### { _stars(min(5, max(1, int(round(summary.get('average_score', 0.0) / 20.0)) ))) }")
    st.markdown("- Morning accuracy, close accuracy, refresh success, historical match quality, and confidence quality contribute to the score.")

    render_footer(st, DISPLAY_VERSION, datetime.now().astimezone())


if __name__ == "__main__":
    main()
