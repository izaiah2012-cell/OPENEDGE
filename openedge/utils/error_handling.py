from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, TypeVar

T = TypeVar("T")


@dataclass
class SourceResult:
    value: object
    warning: str
    stale: bool


def user_facing_error(source_name: str, exc: Exception) -> str:
    message = str(exc).strip() or exc.__class__.__name__
    lowered = message.lower()

    if "yahoo" in lowered or "yf" in lowered or "ticker" in lowered:
        return f"{source_name} unavailable from Yahoo Finance."
    if "macro" in lowered:
        return "Macro events are temporarily unavailable."
    if "csv" in lowered or "database" in lowered:
        return "Historical CSV/database is unavailable."
    if "parse" in lowered or "malformed" in lowered:
        return "Some source rows are malformed and were skipped."
    if "report" in lowered:
        return "Report generation failed for this refresh cycle."

    return f"{source_name} is temporarily unavailable."


def safe_source_call(
    source_name: str,
    fetch_fn: Callable[[], T],
    *,
    fallback_fn: Callable[[], T] | None = None,
    stale_label: str = "STALE",
) -> SourceResult:
    try:
        value = fetch_fn()
        return SourceResult(value=value, warning="", stale=False)
    except Exception as exc:
        if fallback_fn is None:
            return SourceResult(value=None, warning=user_facing_error(source_name, exc), stale=False)

        try:
            fallback = fallback_fn()
        except Exception:
            fallback = None

        if fallback is None:
            return SourceResult(value=None, warning=user_facing_error(source_name, exc), stale=False)

        return SourceResult(
            value=fallback,
            warning=f"{user_facing_error(source_name, exc)} Using latest cached value ({stale_label}).",
            stale=True,
        )
