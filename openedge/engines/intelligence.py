from __future__ import annotations


def _infer_market_regime(bias, internals):
    vix_direction = internals.get("VIX", {}).get("direction", "N/A")
    if bias == "BULLISH" and vix_direction != "UP":
        return "Risk On"
    if bias == "BEARISH" or vix_direction == "UP":
        return "Risk Off"
    return "Balanced"


def _infer_opening_style(opening_auction_risk, market_regime):
    if opening_auction_risk >= 7:
        return "Defensive Open"
    if market_regime == "Risk On" and opening_auction_risk <= 5:
        return "Trend Open"
    return "Neutral Open"


def _highest_probability(bias, historical_result):
    common_outcome = historical_result.get("most_common_outcome", "N/A")
    if common_outcome not in ("N/A", "", None):
        return common_outcome
    return bias


def _base_risk_level(macro_risk):
    if macro_risk in ("LOW", "MEDIUM", "HIGH"):
        return macro_risk
    return "MEDIUM"


def _elevate_risk(risk_level):
    if risk_level == "LOW":
        return "MEDIUM"
    return "HIGH"


def _reduce_risk(risk_level):
    if risk_level == "HIGH":
        return "MEDIUM"
    return "LOW"


def _risk_from_conditions(macro_risk, opening_auction_risk, bias, internals, leadership):
    risk_level = _base_risk_level(macro_risk)

    vix_direction = internals.get("VIX", {}).get("direction", "N/A")
    strong_count = sum(1 for values in leadership.values() if values.get("status") == "Strong")
    weak_count = sum(1 for values in leadership.values() if values.get("status") == "Weak")

    if opening_auction_risk >= 7 or vix_direction == "UP":
        risk_level = _elevate_risk(risk_level)

    if bias == "BEARISH" and weak_count >= max(2, strong_count):
        risk_level = _elevate_risk(risk_level)

    if bias == "BULLISH" and strong_count >= max(2, weak_count + 1) and opening_auction_risk <= 5:
        risk_level = _reduce_risk(risk_level)

    return risk_level


def _strengths(bias, leadership, historical_result, internals):
    strengths = []
    strong_sectors = [name for name, values in leadership.items() if values.get("status") == "Strong"]
    if bias == "BULLISH":
        strengths.append("Broad upside bias in core index signals")
    if strong_sectors:
        strengths.append(f"Leadership support from {', '.join(strong_sectors[:2])}")

    band = historical_result.get("best_match", {}).get("confidence_band", "")
    if band == "Strong":
        strengths.append("Historical analog confidence is strong")

    if internals.get("VIX", {}).get("direction") == "DOWN":
        strengths.append("Volatility pressure is easing")

    return strengths[:3] or ["No clear structural strength identified"]


def _weaknesses(bias, leadership, internals):
    weaknesses = []
    weak_sectors = [name for name, values in leadership.items() if values.get("status") == "Weak"]

    if bias == "BEARISH":
        weaknesses.append("Core index tone is defensive")
    if weak_sectors:
        weaknesses.append(f"Sector drag from {', '.join(weak_sectors[:2])}")

    if internals.get("VIX", {}).get("direction") == "UP":
        weaknesses.append("Volatility is rising into the open")

    return weaknesses[:3] or ["No dominant weakness detected"]


def _key_risks(macro_events, risk_level, opening_auction_risk):
    risks = []
    high_impact = [event.get("event", "Macro event") for event in macro_events if str(event.get("impact", "")).upper() == "HIGH"]

    if high_impact:
        risks.append(f"High-impact macro release risk: {high_impact[0]}")
    if opening_auction_risk >= 7:
        risks.append("Opening auction may be unstable")
    if risk_level == "HIGH":
        risks.append("Position sizing should remain defensive")

    return risks[:3] or ["No elevated risk catalyst identified"]


def _focus_for_today(bias, risk_level):
    if risk_level == "HIGH":
        return "Prioritize risk control, tighter invalidation levels, and selective entries."
    if bias == "BULLISH":
        return "Focus on leading sectors and momentum continuation setups after confirmation."
    if bias == "BEARISH":
        return "Focus on capital preservation and short-duration opportunities on weak bounces."
    return "Focus on balanced execution and wait for directional confirmation before sizing up."


def build_openedge_intelligence(
    *,
    market_internals,
    leadership,
    macro_events,
    macro_risk,
    historical_result,
    bias,
    confidence,
    opening_auction_risk,
    opportunity_score,
):
    """Compose a deterministic morning intelligence object from existing OPENEDGE signals."""
    market_regime = _infer_market_regime(bias, market_internals)
    risk_level = _risk_from_conditions(
        macro_risk=macro_risk,
        opening_auction_risk=opening_auction_risk,
        bias=bias,
        internals=market_internals,
        leadership=leadership,
    )
    opening_style = _infer_opening_style(opening_auction_risk, market_regime)
    highest_probability = _highest_probability(bias, historical_result)

    strengths = _strengths(bias, leadership, historical_result, market_internals)
    weaknesses = _weaknesses(bias, leadership, market_internals)
    key_risks = _key_risks(macro_events, risk_level, opening_auction_risk)
    focus_for_today = _focus_for_today(bias, risk_level)

    summary = (
        f"OPENEDGE reads a {market_regime} backdrop with {risk_level} risk and {confidence}/100 confidence. "
        f"Opening style is {opening_style}, with highest-probability path biased toward {highest_probability} and opportunity score {opportunity_score}/10. "
        f"Primary focus: {focus_for_today}"
    )

    return {
        "market_regime": market_regime,
        "risk_level": risk_level,
        "confidence": confidence,
        "opening_style": opening_style,
        "highest_probability": highest_probability,
        "key_risks": key_risks,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "focus_for_today": focus_for_today,
        "summary": summary,
    }
