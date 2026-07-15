from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class MacroEvent:
    time: str
    event: str
    impact: str


DEFAULT_MACRO_EVENTS = [
    MacroEvent(time="08:30 ET", event="CPI", impact="High"),
    MacroEvent(time="10:00 ET", event="ISM Manufacturing", impact="Medium"),
]


def _default_provider():
    return DEFAULT_MACRO_EVENTS


def get_macro_events(provider: Callable[[], list[MacroEvent]] | None = None):
    source = provider or _default_provider
    events = source()

    return [
        {
            "time": event.time,
            "event": event.event,
            "impact": event.impact,
        }
        for event in events
    ]


def calculate_macro_risk(events):
    score_map = {
        "HIGH": 3,
        "MEDIUM": 2,
        "LOW": 1,
    }

    total_score = sum(score_map.get(str(event.get("impact", "")).upper(), 1) for event in events)

    if total_score <= 2:
        return "LOW"
    if total_score <= 5:
        return "MEDIUM"
    return "HIGH"
