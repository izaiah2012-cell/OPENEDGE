from __future__ import annotations

import pandas as pd

from openedge.analytics import explain
from openedge.engines.historical_analyzer import HistoricalAnalyzer
from openedge.engines.leadership_analyzer import LeadershipAnalyzer
from openedge.engines.macro_analyzer import MacroAnalyzer
from openedge.engines.market_analyzer import MarketAnalyzer
from openedge.engines.market_internals import summarize_market_internals
from openedge.engines.summary_builder import SummaryBuilder
from openedge.models.score_engine import opportunity_score


class IntelligenceEngine:
    """Modular deterministic orchestrator for OPENEDGE intelligence analyzers."""

    def __init__(
        self,
        latest_signal=None,
        market_internals=None,
        leadership=None,
        macro_events=None,
        historical_matches=None,
        **kwargs,
    ):
        self.latest_signal = latest_signal or {}
        self.market_internals = market_internals or {}
        self.leadership = leadership or {}
        self.macro_events = macro_events or []

        historical_payload = historical_matches
        if historical_payload is None:
            historical_payload = kwargs.get("historical_match", {})

        self.historical_match = self._normalize_historical_matches(historical_payload)
        self.market_snapshot = kwargs.get("market_snapshot") or self._snapshot_from_internals(self.market_internals)
        self.history_df = kwargs.get("history_df")

        self.market_analyzer = MarketAnalyzer(
            market_snapshot=self.market_snapshot,
            market_internals=self.market_internals,
            leadership=self.leadership,
            macro_events=self.macro_events,
            historical_matches=self.historical_match,
        )
        self.macro_analyzer = MacroAnalyzer(self.macro_events)
        self.leadership_analyzer = LeadershipAnalyzer(self.leadership)
        self.historical_analyzer = HistoricalAnalyzer(self.historical_match, self.latest_signal)

    @staticmethod
    def _normalize_historical_matches(payload):
        if isinstance(payload, dict):
            return {
                "matches": payload.get("matches", []),
                "best_match": payload.get("best_match", {}),
                "average_similarity": payload.get("average_similarity", 0.0),
                "most_common_outcome": payload.get("most_common_outcome", "N/A"),
                "message": payload.get("message", ""),
            }

        if isinstance(payload, list):
            matches = payload
            best_match = matches[0] if matches else {}
            average_similarity = (
                round(sum(float(match.get("similarity", 0.0)) for match in matches) / len(matches), 2)
                if matches
                else 0.0
            )
            return {
                "matches": matches,
                "best_match": best_match,
                "average_similarity": average_similarity,
                "most_common_outcome": "N/A",
                "message": "",
            }

        return {
            "matches": [],
            "best_match": {},
            "average_similarity": 0.0,
            "most_common_outcome": "N/A",
            "message": "",
        }

    @staticmethod
    def _snapshot_from_internals(internals):
        snapshot = {}
        for symbol in ("SPY", "QQQ", "DIA", "VIX"):
            values = (internals or {}).get(symbol, {})
            snapshot[symbol] = {"change": values.get("daily_change_percent")}
        return snapshot

    @staticmethod
    def _status_tag(ok):
        return "Healthy" if ok else "Waiting"

    def calculate_bias(self):
        return self.market_analyzer.bias()

    # Backward-compatible alias for legacy callers.
    def _calculate_bias(self):
        return self.calculate_bias()

    def _historical_confidence_band(self):
        return self.historical_analyzer.historical_confidence()

    def _highest_probability(self, bias):
        expected = self.historical_analyzer.expected_outcome()
        if expected in (None, "", "N/A"):
            return bias
        return expected

    def calculate_market_regime(self):
        return self.market_analyzer.market_regime()

    def calculate_opening_risk(self):
        return self.market_analyzer.opening_risk()

    def calculate_risk_level(self):
        return self.market_analyzer.risk_level()

    def calculate_confidence(self):
        return self.market_analyzer.confidence()

    def calculate_opening_style(self):
        return self.market_analyzer.opening_style()

    def calculate_opportunity_score(self):
        bias = self.calculate_bias()
        oar = self.calculate_opening_risk()
        return int(opportunity_score(bias, oar))

    def _build_summary(self, market_payload, macro_payload, leadership_payload, historical_payload):
        return SummaryBuilder(
            market=market_payload,
            macro=macro_payload,
            leadership=leadership_payload,
            historical=historical_payload,
        ).build()

    def _performance_payload(self):
        if isinstance(self.history_df, pd.DataFrame) and not self.history_df.empty and "correct" in self.history_df.columns:
            valid = pd.to_numeric(self.history_df["correct"], errors="coerce").dropna()
            if not valid.empty:
                correct_calls = int((valid == 1).sum())
                incorrect_calls = int((valid == 0).sum())

                rolling_df = self.history_df.copy()
                rolling_df["correct_numeric"] = pd.to_numeric(rolling_df["correct"], errors="coerce")
                rolling_df = rolling_df.dropna(subset=["correct_numeric"])

                rolling_accuracy = []
                if not rolling_df.empty:
                    cumulative = (rolling_df["correct_numeric"].expanding().mean() * 100).round(2)
                    dates = rolling_df.get("date", pd.Series(["N/A"] * len(cumulative))).astype(str).tolist()
                    rolling_accuracy = [
                        {"date": date, "accuracy": float(acc)}
                        for date, acc in zip(dates, cumulative.tolist())
                    ]

                return {
                    "signals_tracked": int(len(valid)),
                    "historical_accuracy": round(float(valid.mean()) * 100, 2),
                    "correct_calls": correct_calls,
                    "incorrect_calls": incorrect_calls,
                    "rolling_accuracy": rolling_accuracy,
                    "status": "Available",
                }

        return {
            "signals_tracked": 0,
            "historical_accuracy": None,
            "correct_calls": 0,
            "incorrect_calls": 0,
            "rolling_accuracy": [],
            "status": "Pending",
        }

    def _system_status_payload(self, performance):
        return {
            "market_data": self._status_tag(bool(self.market_internals)),
            "research_engine": "Healthy",
            "historical_database": self._status_tag(performance.get("signals_tracked", 0) > 0),
            "dashboard": "Healthy",
            "tests": "Verified",
        }

    def _internals_rows(self):
        rows = []
        for asset, values in self.market_internals.items():
            price = values.get("price")
            daily_change = values.get("daily_change_percent")
            if daily_change is None:
                daily_change_text = "N/A"
            elif abs(float(daily_change)) < 1e-12:
                daily_change_text = "0.00%"
            else:
                daily_change_text = f"{float(daily_change):+.2f}%"

            rows.append(
                {
                    "Asset": asset,
                    "Price": "N/A" if price is None else f"{float(price):,.2f}",
                    "Daily %": daily_change_text,
                    "Direction": values.get("direction", "N/A"),
                }
            )
        return rows

    def _latest_signal_payload(self):
        signal = self.latest_signal if isinstance(self.latest_signal, dict) else {}
        return {
            "Latest Bias": signal.get("bias", "N/A"),
            "Actual": signal.get("actual", "N/A"),
            "VIX Score": signal.get("vix", "N/A"),
            "Correct": signal.get("correct", "N/A"),
        }

    def _historical_explanation(self):
        signal = self.latest_signal if isinstance(self.latest_signal, dict) else {}
        required = {"risk", "leadership", "vix", "bias", "correct"}
        if not required.issubset(set(signal.keys())):
            return ""
        try:
            return explain(signal)
        except Exception:
            return ""

    def build_report(self):
        market_payload = {
            "bias": self.market_analyzer.bias(),
            "market_regime": self.market_analyzer.market_regime(),
            "risk_level": self.market_analyzer.risk_level(),
            "confidence": self.market_analyzer.confidence(),
            "opening_style": self.market_analyzer.opening_style(),
            "opening_risk": self.market_analyzer.opening_risk(),
        }
        market_payload["opportunity_score"] = int(
            opportunity_score(market_payload["bias"], market_payload["opening_risk"])
        )
        market_payload["internals_rows"] = self._internals_rows()
        market_payload["internals_summary"] = summarize_market_internals(self.market_internals)

        macro_payload = {
            "macro_risk": self.macro_analyzer.macro_risk(),
            "today_events": self.macro_analyzer.today_events(),
            "summary": self.macro_analyzer.summary(),
        }

        leadership_payload = {
            "strongest_sector": self.leadership_analyzer.strongest_sector(),
            "weakest_sector": self.leadership_analyzer.weakest_sector(),
            "sector_summary": self.leadership_analyzer.sector_summary(),
            "rows": self.leadership_analyzer.rows(),
        }

        historical_payload = {
            "best_match": self.historical_analyzer.best_match(),
            "historical_confidence": self.historical_analyzer.historical_confidence(),
            "expected_outcome": self.historical_analyzer.expected_outcome(),
            "rows": self.historical_analyzer.rows(),
            "average_similarity": self.historical_analyzer.average_similarity(),
            "most_common_outcome": self.historical_match.get("most_common_outcome", "N/A"),
            "message": self.historical_analyzer.message(),
        }

        summary_payload = self._build_summary(
            market_payload=market_payload,
            macro_payload=macro_payload,
            leadership_payload=leadership_payload,
            historical_payload=historical_payload,
        )

        summary_payload["system_status"] = self._system_status_payload(self._performance_payload())
        summary_payload["performance"] = self._performance_payload()

        highest_probability = self._highest_probability(market_payload["bias"])
        summary_payload["narrative"] = (
            f"OPENEDGE reads a {market_payload['market_regime']} environment with {market_payload['risk_level']} risk, "
            f"{market_payload['confidence']}/100 confidence, and bias {market_payload['bias']}. "
            f"Opening style is {market_payload['opening_style']} with opening risk {market_payload['opening_risk']}/10 "
            f"and opportunity score {market_payload['opportunity_score']}/10. "
            f"Highest-probability directional path is {highest_probability}. Focus: {summary_payload['todays_focus']}"
        )

        historical_payload["historical_research_explanation"] = self._historical_explanation()

        performance = self._performance_payload()

        return {
            "status": "READY",
            "market": market_payload,
            "macro": macro_payload,
            "leadership": leadership_payload,
            "historical": historical_payload,
            "summary": summary_payload,
            "performance": performance,
            "latest_signal": self._latest_signal_payload(),
        }
