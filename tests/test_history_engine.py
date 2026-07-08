from pathlib import Path

from openedge.engines.history_engine import get_historical_matches, summarize_historical_matches


def test_get_historical_matches_top5_excludes_latest(tmp_path):
    csv_path = tmp_path / "openedge_db.csv"
    csv_path.write_text(
        "date,risk,leadership,vix,oar,oos,bias,actual,correct\n"
        "2024-01-01,1.0,0.5,5,4,3.0,UP,UP,1\n"
        "2024-01-02,0.8,0.4,5,4,3.1,UP,UP,1\n"
        "2024-01-03,-1.0,-0.6,7,6,-0.8,DOWN,DOWN,1\n"
        "2024-01-04,0.9,0.3,5,4,3.0,UP,DOWN,0\n"
        "2024-01-05,0.7,0.2,6,5,2.8,UP,UP,1\n"
        "2024-01-06,0.6,0.1,6,5,2.7,UP,UP,1\n",
        encoding="utf-8",
    )

    matches = get_historical_matches(csv_path=csv_path, top_n=5)

    assert len(matches) == 5
    assert all(match["date"] != "2024-01-06" for match in matches)
    assert matches[0]["rank"] == 1
    assert matches == sorted(matches, key=lambda m: m["similarity"], reverse=True)


def test_summarize_historical_matches_values():
    matches = [
        {"date": "2024-01-04", "similarity": 90.0, "actual": "UP"},
        {"date": "2024-01-03", "similarity": 80.0, "actual": "DOWN"},
        {"date": "2024-01-02", "similarity": 70.0, "actual": "UP"},
    ]

    summary = summarize_historical_matches(matches)

    assert summary["most_similar_session"] == "2024-01-04 (90.00%)"
    assert summary["average_similarity"] == 80.0
    assert summary["most_common_outcome"] == "UP"
