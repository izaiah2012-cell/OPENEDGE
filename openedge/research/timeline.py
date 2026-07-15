from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class DecisionTimelineStore:
    base_dir: Path

    @property
    def path(self) -> Path:
        return self.base_dir / "database" / "decision_timeline.json"

    def load(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def save(self, events: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(events, indent=2), encoding="utf-8")

    def today(self) -> list[dict]:
        today = datetime.now().date()
        events = []
        for event in self.load():
            try:
                timestamp = datetime.fromisoformat(event.get("timestamp", ""))
            except Exception:
                continue
            if timestamp.date() == today:
                events.append(event)
        return events


@dataclass
class BiasTransitionHistory:
    base_dir: Path

    @property
    def path(self) -> Path:
        return self.base_dir / "database" / "bias_transitions.json"

    def load(self) -> list[dict]:
        if not self.path.exists():
            return []
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def save(self, transitions: list[dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(transitions, indent=2), encoding="utf-8")

    def today(self) -> list[dict]:
        today = datetime.now().date()
        rows = []
        for transition in self.load():
            try:
                timestamp = datetime.fromisoformat(transition.get("timestamp", ""))
            except Exception:
                continue
            if timestamp.date() == today:
                rows.append(transition)
        return rows
