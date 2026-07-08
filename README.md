# OPENEDGE

## Project

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

## Running Analysis

Run analysis and generate report:

```bash
python openedge.py analyze
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

## Testing

Run the full test suite:

```bash
python -m pytest -q
```

## Roadmap

See ROADMAP.md for completed and upcoming milestones.

## Contributing

See CONTRIBUTING.md for contribution workflow, branch strategy, and pull request standards.

## License

MIT License. See LICENSE.

## Disclaimer

OPENEDGE is a market research platform. It does not provide investment advice.

