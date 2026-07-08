from openedge.engines.macro_engine import calculate_macro_risk, get_macro_events


def test_get_macro_events_default_dataset():
    events = get_macro_events()

    assert isinstance(events, list)
    assert len(events) >= 2
    assert {"time", "event", "impact"}.issubset(events[0].keys())


def test_get_macro_events_custom_provider():
    events = get_macro_events(
        provider=lambda: [
            type("MacroEvent", (), {"time": "09:45 ET", "event": "PMI", "impact": "Low"})
        ]
    )

    assert events == [{"time": "09:45 ET", "event": "PMI", "impact": "Low"}]


def test_calculate_macro_risk_thresholds():
    low_events = [{"impact": "Low"}]
    medium_events = [{"impact": "High"}, {"impact": "Low"}]
    high_events = [{"impact": "High"}, {"impact": "High"}]

    assert calculate_macro_risk(low_events) == "LOW"
    assert calculate_macro_risk(medium_events) == "MEDIUM"
    assert calculate_macro_risk(high_events) == "HIGH"
