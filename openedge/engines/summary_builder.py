from __future__ import annotations


class SummaryBuilder:
    """Deterministic summary generator from analyzer outputs."""

    def __init__(self, market, macro, leadership, historical):
        self.market = market
        self.macro = macro
        self.leadership = leadership
        self.historical = historical

    def executive_summary(self):
        return (
            f"OPENEDGE reads a {self.market.get('market_regime', 'Balanced')} backdrop with "
            f"{self.market.get('risk_level', 'MEDIUM')} risk, confidence {self.market.get('confidence', 0)}/100, "
            f"and bias {self.market.get('bias', 'NEUTRAL')}."
        )

    def key_risks(self):
        risks = []

        if self.macro.get("macro_risk") == "HIGH":
            events = self.macro.get("today_events", [])
            event_name = events[0].get("Event") if events else "macro catalysts"
            risks.append(f"High-impact macro event risk: {event_name}")

        if int(self.market.get("opening_risk", 0)) >= 7:
            risks.append("Opening auction imbalance risk is elevated")

        if self.market.get("risk_level") == "HIGH":
            risks.append("Overall market risk regime is elevated")

        return risks or ["No elevated risk catalyst identified"]

    def strengths(self):
        strengths = []

        if self.market.get("bias") == "BULLISH":
            strengths.append("Core index bias is constructive")

        strongest = self.leadership.get("strongest_sector", {})
        if strongest.get("sector") not in (None, "", "N/A"):
            strengths.append(f"Leadership supported by {strongest.get('sector')}")

        if self.historical.get("historical_confidence") == "Strong":
            strengths.append("Historical analog confidence is strong")

        return strengths[:3] or ["No dominant structural strength detected"]

    def weaknesses(self):
        weaknesses = []

        if self.market.get("bias") == "BEARISH":
            weaknesses.append("Core index bias is defensive")

        weakest = self.leadership.get("weakest_sector", {})
        if weakest.get("sector") not in (None, "", "N/A"):
            weaknesses.append(f"Relative weakness in {weakest.get('sector')}")

        if self.market.get("risk_level") == "HIGH":
            weaknesses.append("Risk conditions can reduce setup quality")

        return weaknesses[:3] or ["No dominant structural weakness detected"]

    def todays_focus(self):
        if self.market.get("risk_level") == "HIGH":
            return "Prioritize capital preservation and controlled exposure into early volatility."

        bias = self.market.get("bias")
        if bias == "BULLISH":
            return "Focus on relative strength continuation setups with disciplined entries."
        if bias == "BEARISH":
            return "Focus on defensive positioning and short-duration opportunities."

        return "Focus on balanced execution until direction confirms with participation."

    def research_conclusion(self):
        return (
            f"Expected path is {self.historical.get('expected_outcome', 'N/A')} with opening style "
            f"{self.market.get('opening_style', 'Neutral Open')}. "
            f"Macro context: {self.macro.get('summary', '')}"
        )

    def build(self):
        return {
            "executive_summary": self.executive_summary(),
            "key_risks": self.key_risks(),
            "strengths": self.strengths(),
            "weaknesses": self.weaknesses(),
            "todays_focus": self.todays_focus(),
            "research_conclusion": self.research_conclusion(),
        }
