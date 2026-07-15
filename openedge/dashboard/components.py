from __future__ import annotations

from datetime import datetime


def inject_styles(st_module):
    st_module.markdown(
        """
        <style>
        .block-container { padding-top: 1.4rem; padding-bottom: 1.2rem; max-width: 1280px; }
        .oe-shell {
            border: 1px solid rgba(15, 23, 42, 0.08);
            border-radius: 14px;
            background: linear-gradient(140deg, rgba(15, 23, 42, 0.03), rgba(248, 250, 252, 0.7));
            padding: 1rem 1.1rem;
            margin-bottom: 0.65rem;
        }
        .oe-kicker {
            font-size: 0.78rem;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.04em;
            margin-bottom: 0.12rem;
        }
        .oe-title {
            margin: 0;
            font-size: 1.82rem;
            line-height: 1.06;
            color: #0f172a;
            font-weight: 750;
        }
        .oe-subtitle {
            margin: 0.2rem 0 0 0;
            color: #334155;
            font-weight: 500;
        }
        .oe-meta-card {
            border-radius: 10px;
            border: 1px solid rgba(148, 163, 184, 0.25);
            background: rgba(255, 255, 255, 0.8);
            padding: 0.58rem 0.72rem;
            margin-bottom: 0.25rem;
            font-size: 0.9rem;
        }
        .oe-section-header {
            margin: 0 0 0.35rem 0;
            color: #0f172a;
            font-size: 1.05rem;
            font-weight: 700;
        }
        .oe-section-subtitle {
            margin: 0 0 0.55rem 0;
            color: #475569;
            font-size: 0.92rem;
        }
        .oe-badge {
            display: inline-block;
            border-radius: 999px;
            color: white;
            padding: 0.15rem 0.56rem;
            font-size: 0.76rem;
            font-weight: 700;
            letter-spacing: 0.01em;
        }
        .oe-decision-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(185px, 1fr));
            gap: 0.52rem;
            margin-top: 0.35rem;
        }
        .oe-cell {
            border: 1px solid rgba(148, 163, 184, 0.22);
            border-radius: 10px;
            padding: 0.52rem 0.62rem;
            background: rgba(255,255,255,0.86);
        }
        .oe-cell-label {
            font-size: 0.78rem;
            color: #64748b;
            margin-bottom: 0.12rem;
        }
        .oe-cell-value {
            font-size: 0.98rem;
            line-height: 1.22;
            color: #0f172a;
            font-weight: 700;
        }
        .oe-brief {
            border: 1px solid rgba(148, 163, 184, 0.28);
            border-radius: 12px;
            background: rgba(248, 250, 252, 0.8);
            padding: 0.8rem 0.95rem;
        }
        .oe-footer {
            margin-top: 1.1rem;
            border-top: 1px solid rgba(148, 163, 184, 0.25);
            padding-top: 0.72rem;
            color: #64748b;
            font-size: 0.85rem;
            line-height: 1.45;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _badge_color(value):
    text = str(value).upper()
    if text in ("BULLISH", "RISK ON", "LOW", "STRONG", "UP"):
        return "#16a34a"
    if text in ("BEARISH", "RISK OFF", "HIGH", "WEAK", "DOWN"):
        return "#dc2626"
    return "#d97706"


def render_status_badge(value):
    return f"<span class='oe-badge' style='background:{_badge_color(value)}'>{value}</span>"


def render_metric_card(target, label, value, delta=None, help_text=None):
    metric_fn = getattr(target, "metric", None)
    if callable(metric_fn):
        metric_fn(label, value, delta=delta, help=help_text)


def render_section_header(st_module, title, subtitle=None):
    st_module.markdown(f"<div class='oe-section-header'>{title}</div>", unsafe_allow_html=True)
    if subtitle:
        st_module.markdown(f"<div class='oe-section-subtitle'>{subtitle}</div>", unsafe_allow_html=True)


def render_footer(st_module, version, generated_at):
    if isinstance(generated_at, datetime):
        timestamp = generated_at.strftime("%Y-%m-%d %H:%M:%S %Z").strip()
    else:
        timestamp = str(generated_at)

    st_module.markdown(
        f"""
        <div class='oe-footer'>
            <strong>OPENEDGE {version}</strong><br>
            Research Before Risk<br>
            Generated Timestamp: {timestamp}<br>
            Data Sources<br>
            Yahoo Finance<br>
            Historical Database
        </div>
        """,
        unsafe_allow_html=True,
    )
