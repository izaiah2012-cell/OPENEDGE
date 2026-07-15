# OPENEDGE Deployment Guide

This guide prepares OPENEDGE for a permanent hosted URL on Streamlit Community Cloud.

## 1. Entry Point

Use this exact app path:

`openedge/dashboard/app.py`

## 2. Repository Requirements

Make sure these files are committed:

- `requirements.txt`
- `.streamlit/config.toml`
- `.streamlit/secrets.toml.example`
- `.github/workflows/openedge-morning.yml`
- `.github/workflows/openedge-tests.yml`

## 3. Deploy to Streamlit Community Cloud

1. Push your branch to GitHub.
2. Open Streamlit Community Cloud.
3. Click **New app**.
4. Select repository: `izaiah2012-cell/OPENEDGE`.
5. Set main file path to `openedge/dashboard/app.py`.
6. Select your deploy branch.
7. Deploy.

## 4. Secrets Configuration

Create secrets in Streamlit Cloud app settings using `.streamlit/secrets.toml.example` as a template.

Never commit real credentials.

## 5. Morning Workflow Automation

The GitHub workflow `.github/workflows/openedge-morning.yml` supports:

- `workflow_dispatch` for manual runs
- weekday scheduled runs in UTC

Current schedule:

- `30 13 * * 1-5` (13:30 UTC, Monday-Friday)

Adjust the cron value if your morning preparation window uses a different timezone.

## 6. Manual Morning Run

From GitHub Actions:

1. Open **Actions**.
2. Select **OPENEDGE Morning Workflow**.
3. Click **Run workflow**.

The workflow runs:

- tests
- `python openedge.py morning`
- uploads report artifacts

## 7. Runtime Refresh in Dashboard

The dashboard provides `Refresh OPENEDGE`:

- runs `RefreshService`
- clears Streamlit cache
- reports refresh status and duration
- re-runs dashboard safely

## 8. Storage Notes

Current backend: local filesystem via `openedge/storage/local_storage.py`.

Interface defined in `openedge/storage/base.py` allows future storage backends (PostgreSQL/Supabase) without dashboard code changes.

## 9. Known Hosted Limitations

Streamlit Community Cloud uses ephemeral runtime storage between restarts.

For long-term persistence, add a durable backend implementation behind `StorageBackend`.
