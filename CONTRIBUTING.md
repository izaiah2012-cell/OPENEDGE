# Contributing to OPENEDGE

## Branching

- Create feature branches from openedge-v1 using descriptive names.
- Keep each branch focused on one sprint or one scoped improvement.
- Rebase or merge frequently to reduce integration conflicts.

## Testing

Before opening a pull request, run:

```bash
python -m pytest -q
python openedge.py analyze
streamlit run openedge/dashboard/app.py
```

## Code Style

- Preserve package structure and modular boundaries.
- Keep functions focused and readable.
- Add concise comments only where logic is non-obvious.
- Avoid changing trading model or prediction logic unless explicitly requested.

## Pull Requests

- Provide a concise summary of what changed and why.
- Include verification results (tests, analyze run, dashboard startup).
- List any follow-up items or known limitations.

## Commit Message Format

Use clear, imperative messages:

- Implement Sprint X.Y feature name
- Fix <component> <issue>
- Prepare v1.0 beta release documentation
