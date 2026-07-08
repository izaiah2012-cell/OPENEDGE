from __future__ import annotations

from openedge.models.score_engine import market_bias, opening_auction_risk, opportunity_score


class IntelligenceEngine:
    """Deterministic service that composes OPENEDGE morning intelligence."""

    def __init__(
        self,
        market_snapshot,
        market_internals,
        leadership,
        macro_events,
        historical_match,
        latest_signal,
    ):
        self.market_snapshot = market_snapshot or {}
        self.market_internals = market_internals or {}
        self.leadership = leadership or {}
        self.macro_events = macro_events or []
        self.historical_match = historical_match or {}
        self.latest_signal = latest_signal or {}

    def _calculate_bias(self):
        bias, _ = market_bias(self.market_snapshot)
        return bias

    def _historical_confidence_band(self):
        return self.historical_match.get("best_match", {}).get("confidence_band", "Weak")

    def _highest_probability(self, bias):
        common_outcome = self.historical_match.get("most_common_outcome", "N/A")
        if common_outcome not in (None, "", "N/A"):
            return common_outcome

        actual = self.latest_signal.get("actual") if isinstance(self.latest_signal, dict) else None
        if actual not in (None, "", "N/A"):
            return actual

        return bias

    def calculate_market_regime(self):
        bias = self._calculate_bias()
        vix_snapshot_change = self.market_snapshot.get("VIX", {}).get("change")
        vix_internal_direction = self.market_internals.get("VIX", {}).get("direction", "N/A")

        vix_expanding = (vix_snapshot_change is not None and float(vix_snapshot_change) >= 2.0) or vix_internal_direction == "UP"

        if bias == "BULLISH" and not vix_expanding:
            return "Risk On"
        if bias == "BEARISH" or vix_expanding:
            return "Risk Off"
        return "Balanced"

    def calculate_risk_level(self):
        high_impact = sum(1 for event in self.macro_events if str(event.get("impact", "")).upper() == "HIGH")
        medium_impact = sum(1 for event in self.macro_events if str(event.get("impact", "")).upper() == "MEDIUM")

        score = (high_impact * 3) + (medium_impact * 2)

        weak_count = sum(1 for values in self.leadership.values() if values.get("status") == "Weak")
        strong_count = sum(1 for values in self.leadership.values() if values.get("status") == "Strong")

        if weak_count >= max(2, strong_count + 1):
            score += 2

        vix_direction = self.market_internals.get("VIX", {}).get("direction", "N/A")
        if vix_direction == "UP":
            score += 2

        if score <= 2:
            return "LOW"
        if score <= 5:
            return "MEDIUM"
        return "HIGH"

    def calculate_confidence(self):
        _, base_confidence = market_bias(self.market_snapshot)
        confidence = int(base_confidence)

        band = self._historical_confidence_band()
        if band == "Strong":
            confidence += 8
        elif band == "Moderate":
            confidence += 4

        risk_level = self.calculate_risk_level()
        if risk_level == "HIGH":
            confidence -= 6
        elif risk_level == "LOW":
            confidence += 3

        return max(0, min(100, confidence))

    def calculate_opening_style(self):
        oar = opening_auction_risk(self.market_snapshot)
        regime = self.calculate_market_regime()

        if oar >= 7:
            return "Defensive Open"
        if regime == "Risk On" and oar <= 5:
            return "Trend Open"
        return "Neutral Open"

    def calculate_opportunity_score(self):
        bias = self._calculate_bias()
        oar = opening_auction_risk(self.market_snapshot)
        return int(opportunity_score(bias, oar))

    def identify_strengths(self):
        strengths = []
        bias = self._calculate_bias()

        strong_sectors = [name for name, values in self.leadership.items() if values.get("status") == "Strong"]
        if bias == "BULLISH":
            strengths.append("Core index bias is constructive")
        if strong_sectors:
            strengths.append(f"Leadership supported by {', '.join(strong_sectors[:2])}")

        if self._historical_confidence_band() == "Strong":
            strengths.append("Historical analog confidence is strong")

        vix_direction = self.market_internals.get("VIX", {}).get("direction", "N/A")
        if vix_direction == "DOWN":
            strengths.append("Volatility is easing")

        return strengths[:3] or ["No dominant structural strength detected"]

    def identify_weaknesses(self):
        weaknesses = []
        bias = self._calculate_bias()

        weak_sectors = [name for name, values in self.leadership.items() if values.get("status") == "Weak"]
        if bias == "BEARISH":
            weaknesses.append("Core index bias is defensive")
        if weak_sectors:
            weaknesses.append(f"Sector weakness in {', '.join(weak_sectors[:2])}")

        if self.market_internals.get("VIX", {}).get("direction", "N/A") == "UP":
            weaknesses.append("Volatility is rising")

        return weaknesses[:3] or ["No dominant structural weakness detected"]

    def generate_key_risks(self):
        key_risks = []

        high_impact_events = [event.get("event", "Macro event") for event in self.macro_events if str(event.get("impact", "")).upper() == "HIGH"]
        if high_impact_events:
            key_risks.append(f"High-impact macro event risk: {high_impact_events[0]}")

        if opening_auction_risk(self.market_snapshot) >= 7:
            key_risks.append("Opening auction imbalance risk is elevated")

        if self.calculate_risk_level() == "HIGH":
            key_risks.append("Overall risk regime is elevated")

        return key_risks[:3] or ["No elevated risk catalyst identified"]

    def generate_focus(self):
        risk_level = self.calculate_risk_level()
        bias = self._calculate_bias()

        if risk_level == "HIGH":
            return "Prioritize capital preservation and controlled exposure into early volatility."
        if bias == "BULLISH":
            return "Focus on relative strength continuation setups with disciplined entries."
        if bias == "BEARISH":
            return "Focus on defensive positioning and short-duration opportunities."
        return "Focus on balanced execution until direction confirms with participation."

    def generate_summary(self):
        report = {
            "confidence": self.calculate_confidence(),
            "market_regime": self.calculate_market_regime(),
            "bias": self._calculate_bias(),
            "opening_style": self.calculate_opening_style(),
            "risk_level": self.calculate_risk_level(),
            "opportunity_score": self.calculate_opportunity_score(),
            "focus": self.generate_focus(),
        }
        highest_probability = self._highest_probability(report["bias"])

        return (
            f"OPENEDGE reads a {report['market_regime']} environment with {report['risk_level']} risk, "
            f"{report['confidence']}/100 confidence, and bias {report['bias']}. "
            f"Opening style is {report['opening_style']} with opportunity score {report['opportunity_score']}/10. "
            f"Highest-probability directional path is {highest_probability}. Focus: {report['focus']}"
        )

    def build_report(self):
        bias = self._calculate_bias()
        return {
            "confidence": self.calculate_confidence(),
            "market_regime": self.calculate_market_regime(),
            "bias": bias,
            "opening_style": self.calculate_opening_style(),
            "risk_level": self.calculate_risk_level(),
            "opportunity_score": self.calculate_opportunity_score(),
            "strengths": self.identify_strengths(),
            "weaknesses": self.identify_weaknesses(),
            "key_risks": self.generate_key_risks(),
            "focus": self.generate_focus(),
            "summary": self.generate_summary(),
            "status": "READY",
        }
