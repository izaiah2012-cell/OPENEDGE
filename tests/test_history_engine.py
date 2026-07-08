import openedge.engines.history_engine as history_engine


def test_history_engine_imports_correctly():
    assert history_engine is not None


def test_get_historical_matches_missing_file_safe(tmp_path):
    csv_path = tmp_path / "missing.csv"
    result = history_engine.get_historical_matches(csv_path=csv_path, top_n=5)

    assert result["matches"] == []
    assert result["best_match"] == {}
    assert result["average_similarity"] == 0.0
    assert "not found" in result["message"].lower() or "unreadable" in result["message"].lower()


def test_get_historical_matches_too_little_data_safe(tmp_path):
    csv_path = tmp_path / "openedge_db.csv"
    csv_path.write_text(
        "date,risk,leadership,vix,oar,oos,bias,actual,correct\n"
        "2024-01-01,1.0,0.5,5,4,3.0,UP,UP,1\n",
        encoding="utf-8",
    )

    result = history_engine.get_historical_matches(csv_path=csv_path, top_n=5)

    assert result["matches"] == []
    assert result["best_match"] == {}
    assert result["average_similarity"] == 0.0
    assert result["message"] == "Not enough historical data yet. Keep collecting sessions."


def test_get_historical_matches_returns_matches(tmp_path):
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

    result = history_engine.get_historical_matches(csv_path=csv_path, top_n=5)
    matches = result["matches"]

    assert len(matches) == 5
    assert all(match["date"] != "2024-01-06" for match in matches)
    assert matches[0]["rank"] == 1
    assert matches == sorted(matches, key=lambda m: m["similarity"], reverse=True)
    assert result["best_match"]["rank"] == 1
    assert result["average_similarity"] > 0
    assert result["most_common_outcome"] in {"UP", "DOWN", "NEUTRAL"}
    assert matches[0]["confidence_band"] in {"Strong", "Moderate", "Weak"}
    assert "why_similar" in matches[0]
    assert "feature_deltas" in matches[0]
    assert isinstance(matches[0]["feature_deltas"], dict)
    assert 1.0 <= matches[0]["recency_factor"] <= 1.12
