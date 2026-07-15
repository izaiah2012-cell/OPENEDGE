"""
Helper utilities for timeline and bias transition monitoring.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd


class DecisionTimeline:
    """Track decision workflow timeline events."""
    
    def __init__(self, storage_path: Path | None = None):
        self.storage_path = storage_path or Path.home() / ".openedge" / "decision_timeline.json"
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
    
    def add_event(self, event_type: str, details: dict, timestamp: datetime | None = None) -> None:
        """Add a timeline event."""
        if timestamp is None:
            timestamp = datetime.now().astimezone()
        
        events = self._load_events()
        events.append({
            "timestamp": timestamp.isoformat(),
            "type": event_type,
            "details": details,
        })
        
        self._save_events(events)
    
    def get_today_timeline(self) -> list[dict]:
        """Get today's decision timeline events."""
        events = self._load_events()
        today = datetime.now().date()
        
        today_events = []
        for event in events:
            try:
                event_date = datetime.fromisoformat(event["timestamp"]).date()
                if event_date == today:
                    today_events.append(event)
            except Exception:
                continue
        
        return today_events
    
    def _load_events(self) -> list[dict]:
        """Load events from storage."""
        if not self.storage_path.exists():
            return []
        
        try:
            return json.loads(self.storage_path.read_text(encoding="utf-8"))
        except Exception:
            return []
    
    def _save_events(self, events: list[dict]) -> None:
        """Save events to storage."""
        try:
            self.storage_path.write_text(json.dumps(events, indent=2), encoding="utf-8")
        except Exception:
            pass


class BiasTransitionMonitor:
    """Track bias transitions and confidence changes throughout the day."""
    
    def __init__(self, storage_path: Path | None = None):
        self.storage_path = storage_path or Path.home() / ".openedge" / "bias_transitions.json"
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
    
    def add_transition(
        self,
        timestamp: datetime,
        bias_before: str,
        bias_after: str,
        confidence_before: float,
        confidence_after: float,
        reason: str = "",
    ) -> None:
        """Record a bias transition event."""
        transitions = self._load_transitions()
        
        transitions.append({
            "timestamp": timestamp.isoformat(),
            "bias_before": bias_before,
            "bias_after": bias_after,
            "confidence_before": float(confidence_before),
            "confidence_after": float(confidence_after),
            "confidence_change": float(confidence_after - confidence_before),
            "reason": reason,
        })
        
        self._save_transitions(transitions)
    
    def get_today_transitions(self) -> list[dict]:
        """Get today's bias transitions."""
        transitions = self._load_transitions()
        today = datetime.now().date()
        
        today_trans = []
        for trans in transitions:
            try:
                trans_date = datetime.fromisoformat(trans["timestamp"]).date()
                if trans_date == today:
                    today_trans.append(trans)
            except Exception:
                continue
        
        return today_trans
    
    def has_transition_today(self) -> bool:
        """Check if there have been any bias transitions today."""
        return len(self.get_today_transitions()) > 0
    
    def get_latest_transition(self) -> dict | None:
        """Get the most recent bias transition."""
        transitions = self.get_today_transitions()
        return transitions[-1] if transitions else None
    
    def _load_transitions(self) -> list[dict]:
        """Load transitions from storage."""
        if not self.storage_path.exists():
            return []
        
        try:
            return json.loads(self.storage_path.read_text(encoding="utf-8"))
        except Exception:
            return []
    
    def _save_transitions(self, transitions: list[dict]) -> None:
        """Save transitions to storage."""
        try:
            self.storage_path.write_text(json.dumps(transitions, indent=2), encoding="utf-8")
        except Exception:
            pass


class ResearchQuality:
    """Calculate research quality score based on multiple factors."""
    
    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path
    
    def calculate_quality(self, report: dict) -> dict:
        """
        Calculate research quality score (0-5 stars).
        
        Factors:
        - Historical match quality (0-20%)
        - Data completeness (0-20%)
        - Macro coverage (0-20%)
        - Internal validation (0-20%)
        - Confidence stability (0-20%)
        """
        factors = {}
        
        # Historical match quality
        historical = report.get("historical", {})
        best_match = historical.get("best_match", {})
        similarity = float(best_match.get("similarity", 0.0)) / 100.0
        factors["historical_match"] = min(1.0, similarity)
        
        # Data completeness
        market = report.get("market", {})
        internals = market.get("internals_rows", [])
        leadership = report.get("leadership", {}).get("rows", [])
        macro = report.get("macro", {}).get("today_events", [])
        data_score = (len(internals) + len(leadership) + len(macro)) / 30.0  # Normalize to ~30 data points
        factors["data_completeness"] = min(1.0, data_score)
        
        # Macro coverage
        if macro:
            factors["macro_coverage"] = min(1.0, len(macro) / 10.0)
        else:
            factors["macro_coverage"] = 0.0
        
        # Internal validation
        confidence = float(market.get("confidence", 0.0)) / 100.0
        factors["internal_validation"] = confidence
        
        # Confidence stability (estimate from trend)
        factors["confidence_stability"] = min(1.0, abs(confidence - 0.5) * 2)  # Penalize extreme confidence
        
        # Calculate weighted average
        weights = {
            "historical_match": 0.20,
            "data_completeness": 0.20,
            "macro_coverage": 0.20,
            "internal_validation": 0.20,
            "confidence_stability": 0.20,
        }
        
        total_score = sum(factors[k] * weights[k] for k in factors.keys())
        stars = max(1, min(5, round(total_score * 5)))
        
        return {
            "stars": stars,
            "score": round(total_score * 100, 1),
            "factors": {k: round(v * 100, 1) for k, v in factors.items()},
            "description": self._star_description(stars),
        }
    
    @staticmethod
    def _star_description(stars: int) -> str:
        """Get description for star rating."""
        descriptions = {
            1: "Low confidence – limited supporting data",
            2: "Below average – some data gaps",
            3: "Average – good coverage, normal confidence",
            4: "High quality – strong signals and data",
            5: "Excellent – comprehensive analysis, high confidence",
        }
        return descriptions.get(stars, "Unknown")
    
    @staticmethod
    def format_stars(stars: int) -> str:
        """Format star count as emoji."""
        return "⭐" * stars + "☆" * (5 - stars)
