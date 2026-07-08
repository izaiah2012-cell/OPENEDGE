import importlib.util
from datetime import datetime
from pathlib import Path

import pandas as pd

import openedge
import openedge.analytics.explanation as explanation_module
import openedge.dashboard.app as dashboard_app
import openedge.data.market as market_module
import openedge.engines.history_engine as history_module
import openedge.engines.macro_engine as macro_module
import openedge.engines.research_writer as writer_module


def load_cli_module():
    module_path = Path(__file__).resolve().parents[1] / "openedge.py"
    spec = importlib.util.spec_from_file_location("openedge_cli", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_package_imports_work():
    assert openedge is not None
    assert dashboard_app is not None
    assert market_module is not None
    assert explanation_module is not None
    assert macro_module is not None
    assert history_module is not None
    assert writer_module is not None


def test_csv_is_located_from_project_root():
    repo_root = Path(__file__).resolve().parents[1]
    csv_path = repo_root / "openedge_db.csv"
    assert csv_path.exists()
    assert csv_path.is_file()


def test_dashboard_app_loads_without_raising(monkeypatch):
    class DummyContainer:
        def metric(self, *args, **kwargs):
            return None

        def markdown(self, *args, **kwargs):
            return None

    class DummyStreamlit:
        class _DummyCtx:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

        def set_page_config(self, *args, **kwargs):
            return None

        def metric(self, *args, **kwargs):
            return None

        def title(self, *args, **kwargs):
            return None

        def subheader(self, *args, **kwargs):
            return None

        def header(self, *args, **kwargs):
            return None

        def info(self, *args, **kwargs):
            return None

        def caption(self, *args, **kwargs):
            return None

        def success(self, *args, **kwargs):
            return None

        def write(self, *args, **kwargs):
            return None

        def markdown(self, *args, **kwargs):
            return None

        def progress(self, *args, **kwargs):
            return None

        def dataframe(self, *args, **kwargs):
            return None

        def json(self, *args, **kwargs):
            return None

        def divider(self, *args, **kwargs):
            return None

        def columns(self, count):
            return [DummyContainer() for _ in range(count)]

        def container(self, *args, **kwargs):
            return self._DummyCtx()

    monkeypatch.setattr(dashboard_app, "get_market_snapshot", lambda: {"SPY": {"price": 100.0, "change": 0.5}})
    monkeypatch.setattr(
        dashboard_app,
        "get_market_internals_with_cache",
        lambda: (
            {
                "SPY": {"price": 100.0, "daily_change_percent": 0.5, "direction": "UP"},
                "DIA": {"price": 90.0, "daily_change_percent": -0.2, "direction": "DOWN"},
            },
            datetime(2026, 7, 8, 9, 30, 0),
        ),
    )
    monkeypatch.setattr(
        dashboard_app,
        "get_macro_events",
        lambda: [{"time": "08:30 ET", "event": "CPI", "impact": "High"}],
    )
    monkeypatch.setattr(dashboard_app, "calculate_macro_risk", lambda events: "MEDIUM")
    monkeypatch.setattr(
        dashboard_app,
        "get_historical_matches",
        lambda csv_path, top_n=5: {
            "matches": [{"rank": 1, "date": "2024-01-01", "similarity": 87.5, "bias": "UP", "actual": "UP", "correct": 1}],
            "best_match": {"date": "2024-01-01", "similarity": 87.5},
            "average_similarity": 87.5,
            "most_common_outcome": "UP",
            "message": "",
        },
    )
    monkeypatch.setattr(
        dashboard_app,
        "evaluate_sector_leadership",
        lambda: {"Technology": {"score": 1.2, "status": "Strong"}},
    )
    monkeypatch.setattr(dashboard_app, "load_latest_signal", lambda: {"bias": "UP", "risk": 0.1, "leadership": 0.2, "vix": 5})
    monkeypatch.setattr(dashboard_app, "st", DummyStreamlit())

    dashboard_app.main()


def test_market_internals_table_has_expected_columns():
    sample = {
        "SPY": {"price": 615.2, "daily_change_percent": 0.42, "direction": "UP"},
        "VIX": {"price": 14.9, "daily_change_percent": -1.25, "direction": "DOWN"},
    }

    styled = dashboard_app.market_internals_table(sample)
    frame = styled.data

    assert list(frame.columns) == ["Asset", "Price", "Daily %", "Direction"]
    assert len(frame) == 2


def test_cli_analyze_mode_runs_without_crashing(monkeypatch, tmp_path):
    cli_module = load_cli_module()
    csv_path = tmp_path / "openedge_db.csv"
    csv_path.write_text(
        "date,risk,leadership,vix,gap_pct,range_5m,open_type,oar,oos,bias,actual,correct\n"
        "2024-01-01,0.1,0.2,5,0.3,0.4,NEUTRAL OPEN,5,0.15,UP,UP,1\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(cli_module, "DB_FILE", csv_path)
    monkeypatch.setattr(
        cli_module,
        "load_database",
        lambda path: pd.DataFrame(
            [
                {
                    "date": "2024-01-01",
                    "risk": 0.1,
                    "leadership": 0.2,
                    "vix": 5,
                    "gap_pct": 0.3,
                    "range_5m": 0.4,
                    "open_type": "NEUTRAL OPEN",
                    "oar": 5,
                    "oos": 0.15,
                    "bias": "UP",
                    "actual": "UP",
                    "correct": 1,
                }
            ]
        ),
    )

    cli_module.analyze()
