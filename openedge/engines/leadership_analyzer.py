from __future__ import annotations


class LeadershipAnalyzer:
    """Deterministic sector leadership analyzer."""

    def __init__(self, leadership=None):
        self.leadership = leadership or {}

    @staticmethod
    def _status_rank(status):
        status_text = str(status or "Neutral")
        if status_text == "Strong":
            return 2
        if status_text == "Weak":
            return 0
        return 1

    @staticmethod
    def _score_value(values):
        score = values.get("score")
        if score is None:
            return 0.0
        return float(score)

    def _sorted_sectors(self):
        items = []
        for sector, values in self.leadership.items():
            items.append((sector, values))

        return sorted(
            items,
            key=lambda item: (self._status_rank(item[1].get("status")), self._score_value(item[1]), item[0]),
            reverse=True,
        )

    def strongest_sector(self):
        ordered = self._sorted_sectors()
        if not ordered:
            return {"sector": "N/A", "status": "Neutral", "score": 0.0}

        sector, values = ordered[0]
        return {
            "sector": sector,
            "status": values.get("status", "Neutral"),
            "score": self._score_value(values),
        }

    def weakest_sector(self):
        ordered = self._sorted_sectors()
        if not ordered:
            return {"sector": "N/A", "status": "Neutral", "score": 0.0}

        sector, values = sorted(
            ordered,
            key=lambda item: (self._status_rank(item[1].get("status")), self._score_value(item[1]), item[0]),
        )[0]
        return {
            "sector": sector,
            "status": values.get("status", "Neutral"),
            "score": self._score_value(values),
        }

    def sector_summary(self):
        strong = self.strongest_sector()
        weak = self.weakest_sector()
        return (
            f"Leadership is led by {strong['sector']} ({strong['status']}) "
            f"while {weak['sector']} is the weakest pocket ({weak['status']})."
        )

    def rows(self):
        return [
            {
                "Sector": sector,
                "Score (%)": values.get("score", 0.0),
                "5D Momentum (%)": values.get("momentum_5d", 0.0),
                "Status": values.get("status", "Neutral"),
            }
            for sector, values in self.leadership.items()
        ]
