from __future__ import annotations

from openedge.models.score_engine import market_bias, opening_auction_risk


class MarketAnalyzer:
    """Deterministic market-state analyzer for regime, risk, confidence, and opening behavior."""

    def __init__(self, market_snapshot=None, market_internals=None, leadership=None, macro_events=None, historical_matches=None):
        self.market_snapshot = market_snapshot or {}
        self.market_internals = market_internals or {}
        self.leadership = leadership or {}
        self.macro_events = macro_events or []
        self.historical_matches = historical_matches or {}

    def _historical_confidence_band(self):
        return self.historical_matches.get("best_match", {}).get("confidence_band", "Weak")

    def _opening_risk(self):
        return int(opening_auction_risk(self.market_snapshot))

    def bias(self):
        bias_value, _ = market_bias(self.market_snapshot)
        return bias_value

    def market_regime(self):
        bias_value = self.bias()
        vix_snapshot_change = self.market_snapshot.get("VIX", {}).get("change")
        vix_internal_direction = self.market_internals.get("VIX", {}).get("direction", "N/A")

        vix_expanding = (vix_snapshot_change is not None and float(vix_snapshot_change) >= 2.0) or vix_internal_direction == "UP"

        if bias_value == "BULLISH" and not vix_expanding:
            return "Risk On"
        if bias_value == "BEARISH" or vix_expanding:
            return "Risk Off"
        return "Balanced"

    def risk_level(self):
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

    def confidence(self):
        _, base_confidence = market_bias(self.market_snapshot)
        confidence_value = int(base_confidence)

        band = self._historical_confidence_band()
        if band == "Strong":
            confidence_value += 8
        elif band == "Moderate":
            confidence_value += 4

        risk_tag = self.risk_level()
        if risk_tag == "HIGH":
            confidence_value -= 6
        elif risk_tag == "LOW":
            confidence_value += 3

        return max(0, min(100, confidence_value))

    def opening_style(self):
        opening_risk = self._opening_risk()
        regime = self.market_regime()

        if opening_risk >= 7:
            return "Defensive Open"
        if regime == "Risk On" and opening_risk <= 5:
            return "Trend Open"
        return "Neutral Open"

    def opening_risk(self):
        return self._opening_risk()
