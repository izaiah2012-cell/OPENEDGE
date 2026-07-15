from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class ResearchInsightsEngine:
    frame: pd.DataFrame

    def generate(self) -> list[str]:
        insights: list[str] = []
        if self.frame.empty:
            return ["No research memory yet. Run more morning sessions to build learning history."]

        confidence = pd.to_numeric(self.frame.get("morning_confidence"), errors="coerce")
        similarity = pd.to_numeric(self.frame.get("similarity"), errors="coerce")
        grades = self.frame.get("grade", pd.Series(dtype=str)).astype(str)
        bias = self.frame.get("morning_bias", pd.Series(dtype=str)).astype(str)
        regime = self.frame.get("morning_regime", pd.Series(dtype=str)).astype(str)

        if confidence.notna().any():
            avg_conf = float(confidence.mean())
            if 60 <= avg_conf <= 75:
                insights.append(f"Confidence has stabilized in the {avg_conf:.0f}% range, which historically aligns with better calibration.")
            elif avg_conf > 80:
                insights.append(f"Confidence is running high at {avg_conf:.0f}%, which can indicate overconfidence risk if accuracy lags.")

        if similarity.notna().any() and float(similarity.mean()) >= 85:
            insights.append(f"Historical similarity is strong at {float(similarity.mean()):.1f}%, suggesting today often resembles prior high-conviction sessions.")

        top_grade = grades.mode().iloc[0] if not grades.mode().empty else ""
        if top_grade:
            insights.append(f"Most recent grades cluster around {top_grade}, indicating the research process is either improving or consistently stable.")

        if any(regime.str.contains("Risk On", case=False, na=False)) and any(bias.str.contains("TECH", case=False, na=False)):
            insights.append("Risk On periods with Technology strength continue to be the most supportive backdrop.")

        if not insights:
            insights.append("No strong pattern detected yet; continue collecting daily entries.")
        return insights[:5]
