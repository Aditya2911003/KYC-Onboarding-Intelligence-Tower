"""Data access layer: one cached DuckDB connection over the Parquet marts.

* ``get_connection`` creates an in-memory DuckDB database with one view per mart.
* ``query(sql, params)`` is the only way the app runs SQL; results are cached.
* ``where_clause(filters)`` turns the slicer state into ``(sql, params)`` with
  ``?`` placeholders. User input is never formatted into SQL text.
"""

from __future__ import annotations

import os
import re
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

from app.state import SLICERS, Filters

REPO_ROOT = Path(__file__).resolve().parents[1]
_VIEW_NAME = re.compile(r"^[a-z][a-z0-9_]*$")
EXPORT_ROW_CAP = 5_000


def marts_dir() -> Path:
    """Folder with the Parquet marts (override with the KYC_MARTS_DIR env var)."""
    return Path(os.environ.get("KYC_MARTS_DIR", REPO_ROOT / "data" / "marts"))


@st.cache_resource(show_spinner=False)
def get_connection(folder: str | None = None) -> duckdb.DuckDBPyConnection:
    """Open one in-memory DuckDB connection with a view per Parquet mart.

    Views read Parquet lazily, so memory stays small on Streamlit Community Cloud.
    """
    root = Path(folder) if folder else marts_dir()
    con = duckdb.connect(database=":memory:")
    for path in sorted(root.glob("*.parquet")):
        name = path.stem
        if not _VIEW_NAME.match(name):
            continue  # file names become identifiers, so only accept safe ones
        safe_path = path.resolve().as_posix().replace("'", "''")
        con.execute(f"CREATE OR REPLACE VIEW {name} AS SELECT * FROM read_parquet('{safe_path}')")
    return con


@st.cache_data(show_spinner=False, max_entries=1024)
def query(sql: str, params: tuple = ()) -> pd.DataFrame:
    """Run a parameterised query (``?`` placeholders) and return a DataFrame."""
    cursor = get_connection(str(marts_dir())).cursor()  # a cursor per call is thread-safe
    try:
        return cursor.execute(sql, list(params)).df()
    finally:
        cursor.close()


def available_marts() -> set[str]:
    """Names of the marts present on disk."""
    return {p.stem for p in marts_dir().glob("*.parquet")}


def where_clause(filters: Filters, prefix: str = "") -> tuple[str, tuple]:
    """Translate slicers into a WHERE clause over mart_case_detail columns.

    Args:
        filters: active slicer state.
        prefix: optional table alias (e.g. ``"c."``) for joins.

    Returns:
        (SQL text such as ``"WHERE opened_date BETWEEN ? AND ? AND country IN (?)"``,
        parameter tuple)
    """
    clauses = [f"{prefix}opened_date BETWEEN ? AND ?"]
    params: list = [filters.start, filters.end]
    for name, (column, _label) in SLICERS.items():
        values = getattr(filters, name)
        if values:
            clauses.append(f"{prefix}{column} IN ({', '.join('?' for _ in values)})")
            params.extend(values)
    return "WHERE " + " AND ".join(clauses), tuple(params)


def date_bounds() -> tuple[date, date]:
    """Earliest and latest simulated opened_date in the case mart."""
    frame = query("SELECT MIN(opened_date) AS lo, MAX(opened_date) AS hi FROM mart_case_detail")
    return pd.Timestamp(frame.at[0, "lo"]).date(), pd.Timestamp(frame.at[0, "hi"]).date()


def distinct_values(column: str) -> list[str]:
    """Sorted distinct values of a slicer column (column names come from SLICERS only)."""
    allowed = {col for col, _ in SLICERS.values()}
    if column not in allowed:
        raise ValueError(f"column {column!r} is not a slicer column")
    frame = query(f"SELECT DISTINCT {column} AS v FROM mart_case_detail ORDER BY v")
    return [str(v) for v in frame["v"].tolist()]


def filtered_cases(filters: Filters, columns: tuple[str, ...]) -> pd.DataFrame:
    """Return the filtered case rows for the requested (whitelisted) columns."""
    allowed = set(query("SELECT * FROM mart_case_detail LIMIT 0").columns)
    bad = [c for c in columns if c not in allowed]
    if bad:
        raise ValueError(f"unknown columns: {bad}")
    where, params = where_clause(filters)
    return query(f"SELECT {', '.join(columns)} FROM mart_case_detail {where}", params)
