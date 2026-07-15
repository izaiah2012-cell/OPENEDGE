from __future__ import annotations


class HistoricalAnalyzer:
    """Deterministic historical match analyzer."""

    def __init__(self, historical_matches=None, latest_signal=None):
        self.historical_matches = self._normalize(historical_matches)
        self.latest_signal = latest_signal or {}

    @staticmethod
    def _normalize(payload):
        if isinstance(payload, dict):
            return {
                "matches": payload.get("matches", []),
                "best_match": payload.get("best_match", {}),
                "average_similarity": payload.get("average_similarity", 0.0),
                "most_common_outcome": payload.get("most_common_outcome", "N/A"),
                "message": payload.get("message", ""),
            }

        if isinstance(payload, list):
            best_match = payload[0] if payload else {}
            average_similarity = (
                round(sum(float(match.get("similarity", 0.0)) for match in payload) / len(payload), 2)
                if payload
                else 0.0
            )
            return {
                "matches": payload,
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

    def best_match(self):
        return self.historical_matches.get("best_match", {})

    def historical_confidence(self):
        return self.best_match().get("confidence_band", "Weak")

    def expected_outcome(self):
        most_common = self.historical_matches.get("most_common_outcome", "N/A")
        if most_common not in (None, "", "N/A"):
            return most_common

        actual = self.latest_signal.get("actual") if isinstance(self.latest_signal, dict) else None
        if actual not in (None, "", "N/A"):
            return actual

        return self.best_match().get("actual", "N/A")

    def rows(self):
        return [
            {
                "Rank": match.get("rank"),
                "Date": match.get("date"),
                "Similarity %": match.get("similarity"),
                "Confidence Band": match.get("confidence_band", "Weak"),
                "Bias": match.get("bias"),
                "Actual": match.get("actual"),
                "Correct": match.get("correct"),
                "Why Similar": match.get("why_similar", ""),
            }
            for match in self.historical_matches.get("matches", [])
        ]

    def average_similarity(self):
        return float(self.historical_matches.get("average_similarity", 0.0))

    def message(self):
        return self.historical_matches.get("message", "")
