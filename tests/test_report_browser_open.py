import importlib.util
from pathlib import Path


def _load_openedge_cli_module():
    module_path = Path(__file__).resolve().parents[1] / "openedge.py"
    spec = importlib.util.spec_from_file_location("openedge_cli_test", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_latest_html_report_falls_back_to_newest_file(tmp_path, monkeypatch):
    cli = _load_openedge_cli_module()

    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    older = reports_dir / "2026-07-10.html"
    newer = reports_dir / "2026-07-14.html"
    older.write_text("older", encoding="utf-8")
    newer.write_text("newer", encoding="utf-8")

    monkeypatch.setattr(cli, "REPORTS_DIR", reports_dir)
    monkeypatch.setattr(cli, "BASE_DIR", tmp_path)

    selected = cli._latest_html_report("2026-07-15")

    assert selected == newer


def test_open_latest_morning_report_tries_candidates_until_success(monkeypatch, capsys, tmp_path):
    cli = _load_openedge_cli_module()

    report_path = tmp_path / "reports" / "2026-07-15.html"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("<html></html>", encoding="utf-8")

    attempted_urls = []

    monkeypatch.setattr(cli, "_latest_html_report", lambda _date: report_path)
    monkeypatch.setattr(cli, "_report_url_candidates", lambda _path, _remote: ["http://bad", "http://good"])

    def fake_open(url):
        attempted_urls.append(url)
        return url == "http://good"

    monkeypatch.setattr(cli, "_open_report_url", fake_open)
    monkeypatch.setattr(cli.shutil, "which", lambda _name: None)

    cli.open_latest_morning_report()

    output = capsys.readouterr().out
    assert attempted_urls == ["http://bad", "http://good"]
    assert "Opened report in browser: http://good" in output


def test_open_latest_morning_report_handles_missing_reports(monkeypatch, capsys):
    cli = _load_openedge_cli_module()

    monkeypatch.setattr(cli, "_latest_html_report", lambda _date: None)

    cli.open_latest_morning_report()

    output = capsys.readouterr().out
    assert "Morning report not found in:" in output


def test_latest_morning_report_url_returns_first_candidate(monkeypatch, tmp_path):
    cli = _load_openedge_cli_module()

    report_path = tmp_path / "reports" / "2026-07-15.html"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("<html></html>", encoding="utf-8")

    monkeypatch.setattr(cli, "_latest_html_report", lambda _date: report_path)
    monkeypatch.setattr(cli, "_report_url_candidates", lambda _path, _remote: ["http://preferred", "http://fallback"])

    assert cli.latest_morning_report_url() == "http://preferred"
