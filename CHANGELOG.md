# OPENEDGE Changelog

## v1.0 Beta

### Added

- Morning Intelligence Dashboard
- Market Snapshot
- Morning Brief
- Leadership Engine
- Macro Intelligence Engine
- Historical Match Engine
- Performance Dashboard
- AI Research Writer
- Markdown report generation

### Improved

- Modular architecture
- CSV handling
- Historical similarity analysis
- Dashboard stability

### Fixed

- Import resolution
- Package structure
- Database path handling

### Release Validation Checklist

- `python -m pytest -q` passes
- `python openedge.py analyze` runs successfully
- `streamlit run openedge/dashboard/app.py` starts without import errors
