# OPENEDGE Architecture

OPENEDGE uses a modular architecture designed for morning market research workflows.

## Core Flow

User

↓

Dashboard

↓

Research Engines

↓

Market Data

↓

Historical Database

↓

Reports

## Component Summary

- Dashboard: Streamlit application that surfaces research signals and summaries.
- Research Engines: Domain modules for score, leadership, macro, historical match, and AI narrative generation.
- Market Data: Live/near-live market inputs fetched from approved data sources.
- Historical Database: CSV-based research history for trend analysis and similarity matching.
- Reports: Markdown research notes generated for auditability and daily documentation.
