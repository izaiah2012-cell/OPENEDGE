from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path

import pandas as pd


class StorageBackend(ABC):
    @abstractmethod
    def save_report(self, report: dict, *, as_of: datetime | None = None) -> dict[str, Path]:
        raise NotImplementedError

    @abstractmethod
    def load_latest_report(self) -> dict | None:
        raise NotImplementedError

    @abstractmethod
    def save_journal_entry(self, entry: dict) -> Path:
        raise NotImplementedError

    @abstractmethod
    def load_journal(self) -> pd.DataFrame:
        raise NotImplementedError

    @abstractmethod
    def save_refresh_metadata(self, payload: dict) -> Path:
        raise NotImplementedError

    @abstractmethod
    def load_refresh_metadata(self) -> dict:
        raise NotImplementedError

    @abstractmethod
    def load_workflow_status(self) -> dict:
        raise NotImplementedError
