"""Slicer state shared by every page (Power BI-style report-level filters).

Canonical filter values live in ``st.session_state`` under ``flt_*`` keys that are
not bound to any widget, so they survive page switches. Widgets use ``w_*`` keys
and copy their value into the canonical key through ``on_change`` callbacks.
Cross-filter clicks write the canonical keys directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import streamlit as st

# Slicer name -> (mart column, label).
SLICERS: dict[str, tuple[str, str]] = {
    "country": ("country", "Country"),
    "risk": ("risk_category", "Risk tier"),
    "account": ("account_type", "Account type"),
    "channel": ("channel", "Channel (SIMULATED)"),
    "decision": ("decision", "Decision"),
}


@dataclass(frozen=True)
class Filters:
    """Immutable snapshot of the active slicers."""

    start: date
    end: date
    country: tuple[str, ...] = field(default_factory=tuple)
    risk: tuple[str, ...] = field(default_factory=tuple)
    account: tuple[str, ...] = field(default_factory=tuple)
    channel: tuple[str, ...] = field(default_factory=tuple)
    decision: tuple[str, ...] = field(default_factory=tuple)

    def with_dates(self, start: date, end: date) -> Filters:
        """Return a copy with a different date range (used for the previous period)."""
        return Filters(start, end, self.country, self.risk, self.account, self.channel, self.decision)

    def active_count(self, full_start: date, full_end: date) -> int:
        """Count slicers that differ from their defaults."""
        n = sum(bool(getattr(self, name)) for name in SLICERS)
        return n + int((self.start, self.end) != (full_start, full_end))


def init_state(full_start: date, full_end: date) -> None:
    """Create canonical filter keys once per session."""
    st.session_state.setdefault("flt_dates", (full_start, full_end))
    for name in SLICERS:
        st.session_state.setdefault(f"flt_{name}", [])
    st.session_state.setdefault("xf_nonce", 0)


def reset_filters(full_start: date, full_end: date) -> None:
    """Restore every slicer to its default (all values, full date range)."""
    st.session_state["flt_dates"] = (full_start, full_end)
    for name in SLICERS:
        st.session_state[f"flt_{name}"] = []
    st.session_state["xf_nonce"] = st.session_state.get("xf_nonce", 0) + 1


def current_filters(full_start: date, full_end: date) -> Filters:
    """Build a Filters snapshot from the canonical keys."""
    init_state(full_start, full_end)
    dates = st.session_state["flt_dates"]
    start, end = (
        (dates[0], dates[1]) if isinstance(dates, (tuple, list)) and len(dates) == 2 else (full_start, full_end)
    )
    return Filters(
        start=start,
        end=end,
        **{name: tuple(sorted(st.session_state[f"flt_{name}"])) for name in SLICERS},
    )


def set_filter(name: str, values: list[str]) -> None:
    """Set one categorical slicer (used by cross-filter clicks)."""
    st.session_state[f"flt_{name}"] = list(values)


def toggle_filter(name: str, value: str) -> None:
    """Power BI behaviour: clicking the only selected value clears the filter."""
    current = st.session_state.get(f"flt_{name}", [])
    set_filter(name, [] if list(current) == [value] else [value])
