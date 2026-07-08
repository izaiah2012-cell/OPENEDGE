# OPENEDGE

## Project Overview

OPENEDGE is a modular morning market research platform focused on structured observation of market conditions. The platform aggregates index behavior, sector leadership, macro catalysts, and historical matching into a single dashboard and daily research note.

OPENEDGE is designed for research workflows and does not provide financial advice.

## Features

- Morning Intelligence Dashboard
- Market Snapshot and Morning Brief
- Leadership Engine with sector diagnostics
- Macro Intelligence Engine and macro risk scoring
- Historical Match Engine with similarity analysis
- Performance Dashboard metrics
- AI Research Writer
- Markdown report generation in reports/

## Architecture

OPENEDGE is organized into package modules:

- Dashboard layer: Streamlit app for visualization and workflow control
- Research engine layer: score, macro, leadership, historical, and narrative engines
- Data layer: market fetchers and CSV history storage
- Report layer: markdown report generation and export

See docs/architecture.md for more details.

## Installation

1. Clone the repository.
2. Create and activate a Python virtual environment.
3. Install dependencies.

```bash
pip install -e .
```

## Quick Start

Run data collection:

```bash
python openedge.py run
```

Run analysis and generate report:

```bash
python openedge.py analyze
```

Run tests:

```bash
python -m pytest -q
```

## Dashboard

Launch the dashboard:

```bash
streamlit run openedge/dashboard/app.py
```

## Project Structure

```text
openedge/
	analytics/
	dashboard/
	data/
	engines/
	models/

docs/
reports/
tests/
openedge.py
openedge_db.csv
```

## Research Workflow

1. Collect/update session research rows with python openedge.py run.
2. Analyze historical behavior with python openedge.py analyze.
3. Review dashboard sections for intelligence, macro, leadership, and historical matching.
4. Archive daily markdown note from reports/.

## Future Roadmap

See ROADMAP.md for planned releases and milestones.

## Contributing

1. Create a feature branch.
2. Add or update tests for your change.
3. Run pytest and verify dashboard startup.
4. Open a pull request with a concise change summary.

## License

MIT License. See LICENSE.

