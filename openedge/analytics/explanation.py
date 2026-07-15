def explain(row):

    reasons = []

    if row["risk"] < 0:
        reasons.append(
            "Market risk appetite is weakening"
        )

    if row["leadership"] < 0:
        reasons.append(
            "Leadership stocks are under pressure"
        )

    if row["vix"] > 15:
        reasons.append(
            "Volatility is elevated"
        )

    if row["bias"] == "UP":
        outlook = "Bullish"
    else:
        outlook = "Bearish"


    report = f"""
OPENEDGE AI ANALYSIS

Market Outlook:
{outlook}


Key Drivers:
"""

    for reason in reasons:
        report += f"\n✓ {reason}"


    if not reasons:
        report += "\n✓ Market signals are mixed"


    if pd_is_available(row):

        report += "\n\nHistorical Result:"
        report += f"\nCorrect: {row['correct']}"

    else:

        report += """

Historical Result:
Pending market close

OPENEDGE is monitoring today's outcome.
"""


    return report



def pd_is_available(row):

    try:
        return row["correct"] == 1 or row["correct"] == 0
    except:
        return False