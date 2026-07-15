"""
Operations – System monitoring and workflow management.
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_repo_root = str(_Path(__file__).resolve().parents[3])
if _repo_root not in _sys.path:
    _sys.path.insert(0, _repo_root)

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from openedge.dashboard.components import inject_styles, render_footer, render_metric_card, render_section_header
from openedge.services.health_service import HealthService
from openedge.services.refresh_service import RefreshService

BASE_DIR = Path(__file__).resolve().parents[3]
LOGS_DIR = BASE_DIR / "logs"
DISPLAY_VERSION = "v1.1.0"


def _render_health_badge(status: str) -> str:
    """Render a color-coded health badge."""
    if status == "healthy":
        return "🟢 Healthy"
    elif status == "degraded":
        return "🟡 Degraded"
    else:
        return "🔴 Unhealthy"


def _render_scheduler_section(st_module, refresh_service, health_service):
    """Render scheduler and refresh cadence information."""
    render_section_header(st_module, "⏱ Scheduler")

    refresh_status = refresh_service.get_refresh_status()
    scheduler_cols = st_module.columns(4)
    render_metric_card(scheduler_cols[0], "Cadence", "Weekdays 13:30 UTC")
    render_metric_card(scheduler_cols[1], "Auto Refresh", "Manual + optional UI auto-refresh")
    render_metric_card(scheduler_cols[2], "Last Refresh", refresh_status.get("last_successful_refresh", "N/A"))
    render_metric_card(scheduler_cols[3], "Workflow", health_service.get_health().get("latest_workflow_status", "N/A"))

    with st_module.expander("Scheduler Details", expanded=False):
        st_module.markdown("- Primary workflow cadence: weekdays at 13:30 UTC")
        st_module.markdown("- Manual refresh is available from Refresh Controls")
        st_module.markdown("- Auto-refresh can be enabled from the UI")


def _render_testing_section(st_module):
    """Render a lightweight environment and import verification panel."""
    render_section_header(st_module, "🧪 Testing")

    import_results = []
    modules = [
        ("Dashboard", "openedge.dashboard.app"),
        ("Research Lab", "openedge.dashboard.pages.research_lab"),
        ("Operations", "openedge.dashboard.pages.operations"),
        ("Research Archive", "openedge.dashboard.pages.research_archive"),
    ]
    for label, module_name in modules:
        try:
            __import__(module_name)
            import_results.append((label, "healthy"))
        except Exception:
            import_results.append((label, "degraded"))

    cols = st_module.columns(len(import_results))
    for col, (label, status) in zip(cols, import_results):
        render_metric_card(col, label, _render_health_badge(status))

    with st_module.expander("Testing Notes", expanded=False):
        st_module.markdown("- Local verification command: `python -m pytest -q`")
        st_module.markdown("- These checks confirm the dashboard modules import cleanly")
        st_module.markdown("- Full functional coverage still comes from the project test suite")


def _render_workflow_section(st_module, refresh_service, health_service):
    """Render workflow status and controls."""
    render_section_header(st_module, "🔄 Workflow Automation")
    
    workflow_status = health_service.get_workflow_status()
    
    w1, w2, w3, w4 = st_module.columns(4)
    render_metric_card(w1, "Last Run", workflow_status.get("last_workflow_run", "N/A"))
    duration = workflow_status.get("workflow_duration_seconds", "N/A")
    duration_str = f"{duration}s" if isinstance(duration, (int, float)) else str(duration)
    render_metric_card(w2, "Duration", duration_str)
    render_metric_card(w3, "Last Report", workflow_status.get("last_report_generated", "N/A"))
    render_metric_card(w4, "Status", workflow_status.get("research_status", "N/A"))


def _render_refresh_section(st_module, refresh_service):
    """Render refresh controls."""
    render_section_header(st_module, "🔃 Refresh Controls")
    
    with st_module.expander("Refresh Controls", expanded=True):
        col1, col2 = st_module.columns(2)
        
        with col1:
            if st_module.button("🔄 Manual Refresh Now"):
                result = refresh_service.run_refresh()
                if result.get("success"):
                    st_module.success("✅ Refresh completed successfully!")
                else:
                    st_module.warning(f"⚠️ {result.get('message', 'Refresh failed')}")
        
        with col2:
            st_module.checkbox("Enable auto-refresh", value=st_module.session_state.get("oe_auto_refresh", False), key="oe_auto_refresh")
        
        refresh_status = refresh_service.get_refresh_status()
        st_module.markdown(f"**Last successful refresh:** {refresh_status.get('last_successful_refresh', 'N/A')}")
        st_module.markdown(f"**Duration:** {refresh_status.get('last_duration_seconds', 'N/A')}s")
        st_module.markdown(f"**Status:** {'🟢 RUNNING' if refresh_status.get('is_running') else '🟢 READY'}")


def _render_health_section(st_module, health_service):
    """Render system health status."""
    render_section_header(st_module, "🏥 System Health")
    
    health = health_service.get_health()
    
    h1, h2, h3, h4, h5 = st_module.columns(5)
    render_metric_card(h1, "Application", _render_health_badge(health.get("application_status", "unknown")))
    render_metric_card(h2, "Market Data", _render_health_badge(health.get("market_provider_status", "unknown")))
    render_metric_card(h3, "Latest Report", "✅ Available" if health.get("latest_report_available") else "❌ Missing")
    render_metric_card(h4, "Storage", _render_health_badge(health.get("storage_status", "unknown")))
    render_metric_card(h5, "Workflow", _render_health_badge(health.get("workflow_status", "unknown")))
    
    # Detailed health info
    with st_module.expander("Detailed Health Report", expanded=False):
        st_module.json(health)


def _render_logs_section(st_module):
    """Render system logs viewer."""
    render_section_header(st_module, "📋 Logs")
    
    if LOGS_DIR.exists():
        log_files = list(LOGS_DIR.glob("*.log"))
        if log_files:
            selected_log = st_module.selectbox(
                "Select log file",
                options=sorted(log_files, reverse=True),
                format_func=lambda x: x.name
            )
            
            if selected_log:
                with st_module.expander(f"View {selected_log.name}", expanded=False):
                    try:
                        content = selected_log.read_text(encoding="utf-8")
                        # Show last 100 lines
                        lines = content.split("\n")
                        st_module.text_area("Log content", value="\n".join(lines[-100:]), height=400, disabled=True)
                    except Exception as e:
                        st_module.error(f"Error reading log: {e}")
        else:
            st_module.info("No log files available.")
    else:
        st_module.info("Logs directory not found.")


def _render_database_section(st_module):
    """Render database status."""
    render_section_header(st_module, "🗄️ Database")
    
    db_dir = BASE_DIR / "database"
    csv_file = BASE_DIR / "openedge_db.csv"
    journal_file = BASE_DIR / "research_journal.csv"
    
    d1, d2, d3 = st_module.columns(3)
    
    # CSV status
    if csv_file.exists():
        try:
            df = pd.read_csv(csv_file)
            render_metric_card(d1, "Validation Records", len(df))
        except Exception:
            render_metric_card(d1, "Validation Records", "Error")
    else:
        render_metric_card(d1, "Validation Records", "0")
    
    # Journal status
    if journal_file.exists():
        try:
            df = pd.read_csv(journal_file)
            render_metric_card(d2, "Journal Entries", len(df))
        except Exception:
            render_metric_card(d2, "Journal Entries", "Error")
    else:
        render_metric_card(d2, "Journal Entries", "0")
    
    # Database directory status
    if db_dir.exists():
        files = list(db_dir.glob("*"))
        render_metric_card(d3, "Database Files", len(files))
    else:
        render_metric_card(d3, "Database Files", "0")
    
    # Detailed database info
    with st_module.expander("Database Details", expanded=False):
        st_module.markdown("**Validation Database (openedge_db.csv)**")
        if csv_file.exists():
            df = pd.read_csv(csv_file)
            st_module.dataframe(df.tail(10), hide_index=True, width="stretch")
        else:
            st_module.info("No validation database found.")
        
        st_module.markdown("**Research Journal (research_journal.csv)**")
        if journal_file.exists():
            df = pd.read_csv(journal_file)
            st_module.dataframe(df.tail(10), hide_index=True, width="stretch")
        else:
            st_module.info("No research journal found.")


def _render_deployment_section(st_module):
    """Render deployment info."""
    render_section_header(st_module, "🚀 Deployment")
    
    version_file = BASE_DIR / "VERSION"
    version = "1.1.0"
    if version_file.exists():
        version = version_file.read_text().strip()
    
    d1, d2, d3 = st_module.columns(3)
    render_metric_card(d1, "Version", version)
    render_metric_card(d2, "Environment", "Streamlit Cloud" if "streamlit" in str(Path.home()) else "Local")
    render_metric_card(d3, "Python Version", "3.10+")
    
    with st_module.expander("Deployment Details", expanded=False):
        st_module.markdown("**Repository**")
        st_module.markdown("- Owner: izaiah2012-cell")
        st_module.markdown("- Repo: OPENEDGE")
        st_module.markdown("- Branch: main")
        st_module.markdown("")
        st_module.markdown("**Entry Point**")
        st_module.markdown("- openedge/dashboard/app.py")
        st_module.markdown("")
        st_module.markdown("**Configuration**")
        st_module.markdown("- .streamlit/config.toml")
        st_module.markdown("- requirements.txt")


def main():
    try:
        st.set_page_config(page_title="OPENEDGE Operations", page_icon="⚙️", layout="wide")
    except Exception:
        pass

    inject_styles(st)
    
    refresh_service = RefreshService(BASE_DIR)
    health_service = HealthService(BASE_DIR)

    st.markdown(
        "<div class='oe-shell'><div class='oe-kicker'>System Management</div>"
        "<h1 class='oe-title'>Operations</h1>"
        "<p class='oe-subtitle'>Monitor and manage OPENEDGE systems.</p></div>",
        unsafe_allow_html=True,
    )

    st.divider()

    # Sections
    _render_workflow_section(st, refresh_service, health_service)
    st.markdown("")

    _render_refresh_section(st, refresh_service)
    st.markdown("")

    _render_scheduler_section(st, refresh_service, health_service)
    st.markdown("")

    _render_health_section(st, health_service)
    st.markdown("")

    _render_logs_section(st)
    st.markdown("")

    _render_testing_section(st)
    st.markdown("")

    _render_database_section(st)
    st.markdown("")

    _render_deployment_section(st)

    render_footer(st, DISPLAY_VERSION, datetime.now().astimezone())


if __name__ == "__main__":
    main()
