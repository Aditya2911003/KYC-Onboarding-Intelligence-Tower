"""Shared fixtures: a warehouse built from the deterministic sample.

By default the sample in ``data/sample`` is built once per test session into a
temporary folder. CI builds it explicitly first and points the tests at it with
``KYC_TEST_MARTS_DIR`` (and optionally ``KYC_TEST_DB``). Tests assert
relationships and invariants, never absolute full-data row counts, so they pass
on both the sample and the full data.
"""

from __future__ import annotations

import os
import sys
from collections.abc import Iterator
from pathlib import Path

import duckdb
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl import build_warehouse  # noqa: E402

SAMPLE_DIR = REPO_ROOT / "data" / "sample"
COMMITTED_MARTS = REPO_ROOT / "data" / "marts"


@pytest.fixture(scope="session")
def built(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """(marts dir, warehouse db) for the sample-built warehouse."""
    env_marts = os.environ.get("KYC_TEST_MARTS_DIR")
    if env_marts:
        marts = Path(env_marts)
        db = Path(os.environ.get("KYC_TEST_DB", marts.resolve().parent / "warehouse.duckdb"))
        if (marts / "mart_case_detail.parquet").exists() and db.exists():
            return marts, db
    root = tmp_path_factory.mktemp("warehouse")
    marts, db = root / "marts", root / "warehouse.duckdb"
    build_warehouse.build(SAMPLE_DIR, marts, db)
    return marts, db


@pytest.fixture(scope="session")
def marts_dir(built: tuple[Path, Path]) -> Path:
    """Folder with the sample-built Parquet marts."""
    return built[0]


@pytest.fixture()
def con(built: tuple[Path, Path]) -> Iterator[duckdb.DuckDBPyConnection]:
    """Read-only connection to the sample-built warehouse."""
    connection = duckdb.connect(str(built[1]), read_only=True)
    connection.execute(f"SET VARIABLE as_of = DATE '{build_warehouse.AS_OF:%Y-%m-%d}'")
    yield connection
    connection.close()


def scalar(con: duckdb.DuckDBPyConnection, sql: str, params: list | None = None) -> float:
    """Run a query that returns one value."""
    row = con.execute(sql, params or []).fetchone()
    assert row is not None
    return row[0]
