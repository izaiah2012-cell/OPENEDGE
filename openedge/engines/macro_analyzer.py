from __future__ import annotations

from openedge.engines.macro_engine import calculate_macro_risk


class MacroAnalyzer:
    """Deterministic macro event analyzer."""

    def __init__(self, macro_events=None):
        self.macro_events = macro_events or []

    def macro_risk(self):
        return calculate_macro_risk(self.macro_events)

    def today_events(self):
        return [
            {
                "Time": event.get("time", "N/A"),
                "Event": event.get("event", "N/A"),
                "Impact": event.get("impact", "Low"),
            }
            for event in self.macro_events
        ]

    def summary(self):
        risk_tag = self.macro_risk()
        high_impact = [event.get("event", "Macro event") for event in self.macro_events if str(event.get("impact", "")).upper() == "HIGH"]

        if high_impact:
            return f"Macro risk is {risk_tag} with high-impact focus on {high_impact[0]}."

        if self.macro_events:
            return f"Macro risk is {risk_tag} with scheduled catalysts monitored through the session."

        return f"Macro risk is {risk_tag} with no major scheduled catalysts listed."
