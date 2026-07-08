def _value(data, key, default="N/A"):
    value = data.get(key, default)
    if value is None or value == "":
        return default
    return value


def _format_leadership(leadership):
    if not leadership:
        return "Sector leadership data is limited in the current snapshot."

    lines = []
    for sector, values in leadership.items():
        score = values.get("score", "N/A")
        status = values.get("status", "Neutral")
        lines.append(f"- {sector}: {status} ({score})")

    return "\n".join(lines)


def _format_macro_events(events):
    if not events:
        return "No high-priority macro events are currently listed."

    lines = []
    for event in events[:5]:
        lines.append(f"- {event.get('time', 'N/A')}: {event.get('event', 'N/A')} ({event.get('impact', 'Low')})")
    return "\n".join(lines)


def _format_historical_match(match, similarity):
    if not match:
        return "Historical matching is not yet available due to limited completed sessions."

    date = match.get("date", "N/A")
    bias = match.get("bias", "N/A")
    actual = match.get("actual", "N/A")
    correct = match.get("correct", "N/A")
    return (
        f"Most comparable session is {date} with average similarity at {similarity}%. "
        f"The matched session showed bias {bias}, realized outcome {actual}, and correctness flag {correct}."
    )


def generate_research_summary(data):
    market_regime = _value(data, "market_regime")
    confidence = _value(data, "confidence", 0)
    oar = _value(data, "opening_auction_risk", "N/A")
    oos = _value(data, "opportunity_score", "N/A")
    bias = _value(data, "bias")
    leadership = data.get("leadership", {})
    macro_events = data.get("macro_events", [])
    macro_risk = _value(data, "macro_risk")
    historical_match = data.get("historical_match", {})
    historical_similarity = _value(data, "historical_similarity", 0.0)

    return f"""## Executive Summary
OPENEDGE's morning diagnostics currently indicate a {market_regime} backdrop, with directional bias assessed as {bias}. Internal confidence is {confidence}/100 while opening auction risk is {oar}/10 and opportunity score is {oos}/10. These metrics describe the current market structure and should be interpreted as observational research context.

## Market Regime
The present regime classification is {market_regime}. Bias remains {bias} with a confidence reading of {confidence}/100, suggesting the signal profile is active but still conditional on intraday validation and macro event flow.

## Sector Leadership
{_format_leadership(leadership)}

## Macro Events
Macro risk is currently tagged as {macro_risk}. Scheduled events under review:
{_format_macro_events(macro_events)}

## Historical Comparison
{_format_historical_match(historical_match, historical_similarity)}

## Research Conclusion
The combined signal stack points to a {market_regime} environment with bias {bias}, balanced against macro risk rated {macro_risk}. This note is a structured research observation designed to contextualize conditions and does not provide trade instruction or execution guidance.
"""
