"""Build the KYC Onboarding Control Tower warehouse and export the Parquet marts.

Pipeline (one command, idempotent, deterministic):

1. ``sql/01_staging.sql``  typed staging tables over the raw CSVs (OCRText skipped)
2. ``simulate_case_ops``   the SIMULATED operations layer (seed 42) -> ``sim_case_ops``
3. ``sql/02_model.sql``    star schema, rule engine and control-breach flags
4. ``sql/03_marts.sql``    app-ready marts
5. ``sql/04_analysis.sql`` advanced-SQL analysis tables (validated against the marts)
6. ``etl/ai_qa_marts.py``  AI-answer quality marts
7. export every ``mart_*`` / ``analysis_*`` table to zstd Parquet
8. ``etl/quality_checks.py`` data-quality report and claimed-vs-measured table

Usage::

    python etl/build_warehouse.py --raw-dir data/raw --out-dir data/marts
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from string import Template

import duckdb
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from etl import ai_qa_marts, quality_checks  # noqa: E402

LOG = logging.getLogger("build_warehouse")

SQL_DIR = REPO_ROOT / "sql"
SQL_FILES = ("01_staging.sql", "02_model.sql", "03_marts.sql", "04_analysis.sql")

# ---------------------------------------------------------------------------
# Simulation parameters (SIMULATED operations layer). Defined once, reused by
# the app's methodology page and the docs, and covered by tests.
# ---------------------------------------------------------------------------
AS_OF = datetime(2026, 6, 30)
SEED = 42
OPENED_BETA_A = 1.3
OPENED_BETA_B = 2.2
OPENED_WINDOW_DAYS = 730
N_ANALYSTS = 24
CHANNELS = ("Web", "Branch", "Mobile", "Partner")
CHANNEL_PROBS = (0.40, 0.25, 0.25, 0.10)
HANDLING_SIGMA = 0.45
HANDLING_BASE_DAYS = {
    "Approve": 1.5,
    "Pending Documents": 4.0,
    "Manual Review": 5.0,
    "Enhanced Due Diligence": 7.0,
    "Reject": 2.5,
}
HIGH_RISK_MULTIPLIER = 1.35
PEP_MULTIPLIER = 1.25
SLA_DAYS = {
    "Approve": 3,
    "Pending Documents": 5,
    "Manual Review": 7,
    "Enhanced Due Diligence": 10,
    "Reject": 3,
}


def simulate_case_ops(cases: pd.DataFrame, seed: int = SEED, as_of: datetime = AS_OF) -> pd.DataFrame:
    """Generate the SIMULATED operations fields for each case, deterministically.

    The source data has no timestamps, analysts, channels or SLAs, so these are
    simulated with a fixed seed and kept only in ``sim_case_ops``. Draws happen
    in a fixed order over cases sorted by ``case_id``: opened offset, analyst,
    channel, handling time.

    Args:
        cases: DataFrame with ``case_id``, ``decision``, ``risk_category``, ``is_pep``.
        seed: seed for ``numpy.random.default_rng``.
        as_of: snapshot instant; cases whose handling ends after it are open.

    Returns:
        One row per case with opened_at, closed_at, handling_days, tat_days,
        sla_days, sla_breached, is_open, assigned_to and channel.
    """
    ordered = cases.sort_values("case_id").reset_index(drop=True)
    n = len(ordered)
    rng = np.random.default_rng(seed)

    offset_days = (rng.beta(OPENED_BETA_A, OPENED_BETA_B, n) * OPENED_WINDOW_DAYS).astype(int)
    analyst_idx = rng.integers(1, N_ANALYSTS + 1, n)
    channel = rng.choice(np.array(CHANNELS), size=n, p=np.array(CHANNEL_PROBS))

    decision = ordered["decision"].to_numpy()
    base = np.array([HANDLING_BASE_DAYS[d] for d in decision], dtype=float)
    risk_mult = np.where(ordered["risk_category"].to_numpy() == "High", HIGH_RISK_MULTIPLIER, 1.0)
    pep_mult = np.where(ordered["is_pep"].to_numpy(dtype=bool), PEP_MULTIPLIER, 1.0)
    mu = base * risk_mult * pep_mult
    handling_days = rng.lognormal(mean=np.log(mu), sigma=HANDLING_SIGMA)

    as_of_ts = pd.Timestamp(as_of)
    opened_at = as_of_ts - pd.to_timedelta(offset_days, unit="D")
    end_at = opened_at + pd.to_timedelta(handling_days, unit="D")
    is_open = np.asarray(end_at > as_of_ts)
    closed_at = end_at.where(~is_open, as_of_ts)
    tat_days = np.asarray((closed_at - opened_at) / pd.Timedelta(days=1), dtype=float)
    sla_days = np.array([SLA_DAYS[d] for d in decision], dtype=int)

    return pd.DataFrame(
        {
            "case_id": ordered["case_id"].to_numpy(),
            "opened_at": np.asarray(opened_at),
            "closed_at": np.asarray(closed_at),
            "handling_days": handling_days,
            "tat_days": tat_days,
            "sla_days": sla_days,
            "sla_breached": tat_days > sla_days,
            "is_open": is_open,
            "assigned_to": [f"Analyst_{i:02d}" for i in analyst_idx],
            "channel": channel,
        }
    )


def render_sql(path: Path, raw_dir: Path) -> str:
    """Read a SQL file and substitute ``${RAW_DIR}`` with a quote-escaped path."""
    safe_raw = raw_dir.resolve().as_posix().replace("'", "''")
    return Template(path.read_text(encoding="utf-8")).safe_substitute(RAW_DIR=safe_raw)


def run_sql_file(con: duckdb.DuckDBPyConnection, name: str, raw_dir: Path) -> None:
    """Execute one SQL file from ``sql/`` statement by statement and log its duration.

    Statements are executed one at a time (parsed by DuckDB itself) because the
    parser scopes named WINDOW clauses per script, not per statement.
    """
    start = time.perf_counter()
    for statement in con.extract_statements(render_sql(SQL_DIR / name, raw_dir)):
        con.execute(statement)
    LOG.info("ran %-16s in %.2fs", name, time.perf_counter() - start)


def build_simulation(con: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Create ``sim_case_ops`` from ``stg_cases`` and return it."""
    cases = con.execute("SELECT case_id, decision, risk_category, is_pep FROM stg_cases ORDER BY case_id").df()
    sim = simulate_case_ops(cases)
    con.register("sim_df", sim)
    con.execute("CREATE OR REPLACE TABLE sim_case_ops AS SELECT * FROM sim_df")
    con.unregister("sim_df")
    LOG.info(
        "sim_case_ops: %s rows | avg tat %.2f d | SLA breach %.1f%% | open %s",
        f"{len(sim):,}",
        sim["tat_days"].mean(),
        100 * sim["sla_breached"].mean(),
        f"{int(sim['is_open'].sum()):,}",
    )
    return sim


def validate_analysis(con: duckdb.DuckDBPyConnection) -> None:
    """Cross-check the advanced-SQL analysis tables against the plain marts.

    Raises:
        AssertionError: if two independently written queries disagree.
    """
    funnel_a = con.execute("SELECT cases FROM analysis_funnel ORDER BY stage_order").fetchall()
    funnel_m = con.execute("SELECT cases FROM mart_funnel ORDER BY stage_order").fetchall()
    assert funnel_a == funnel_m, f"funnel mismatch: {funnel_a} vs {funnel_m}"

    backlog_a = con.execute(
        "SELECT risk_category, overdue FROM analysis_review_backlog ORDER BY risk_category"
    ).fetchall()
    backlog_m = con.execute("SELECT risk_category, overdue FROM mart_review_backlog ORDER BY risk_category").fetchall()
    assert backlog_a == backlog_m, f"backlog mismatch: {backlog_a} vs {backlog_m}"

    breach_total = con.execute(
        "SELECT approved_failed_id_or_address FROM analysis_breach_by_channel_country WHERE grouping_level = 3"
    ).fetchone()
    breach_mart = con.execute("SELECT SUM(breach_id_or_address) FROM mart_control_breaches").fetchone()
    assert breach_total is not None and breach_mart is not None
    assert breach_total[0] == breach_mart[0], "breach grand total mismatch"

    orphans_a = con.execute("SELECT COUNT(*) FROM analysis_rule_orphans").fetchone()
    orphans_m = con.execute("SELECT SUM(rules_without_guideline) FROM mart_rule_coverage").fetchone()
    assert orphans_a is not None and orphans_m is not None
    assert orphans_a[0] == orphans_m[0], "orphan rule count mismatch"
    LOG.info("analysis queries validated against marts")


def export_tables(con: duckdb.DuckDBPyConnection, out_dir: Path) -> dict[str, int]:
    """Export every ``mart_*`` and ``analysis_*`` table to zstd Parquet.

    Returns:
        Mapping of table name to exported row count.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    tables = [
        row[0]
        for row in con.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'main' AND (table_name LIKE 'mart\\_%' ESCAPE '\\' "
            "OR table_name LIKE 'analysis\\_%' ESCAPE '\\') ORDER BY table_name"
        ).fetchall()
    ]
    counts: dict[str, int] = {}
    for table in tables:
        target = (out_dir / f"{table}.parquet").as_posix().replace("'", "''")
        con.execute(f"COPY {table} TO '{target}' (FORMAT parquet, COMPRESSION zstd)")
        row = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        counts[table] = int(row[0]) if row else 0
    return counts


def build(raw_dir: Path, out_dir: Path, db_path: Path) -> dict[str, int]:
    """Run the full pipeline and return exported row counts per table."""
    t0 = time.perf_counter()
    if not (raw_dir / "kyc_cases.csv").exists():
        raise FileNotFoundError(f"raw directory {raw_dir} does not contain kyc_cases.csv")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()  # idempotent: rebuild from scratch every run
    con = duckdb.connect(str(db_path))
    con.execute(f"SET VARIABLE as_of = DATE '{AS_OF:%Y-%m-%d}'")

    run_sql_file(con, "01_staging.sql", raw_dir)
    for table in ("stg_customers", "stg_cases", "stg_documents", "stg_rules", "stg_guidelines"):
        row = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        LOG.info("%-16s %10s rows", table, f"{row[0] if row else 0:,}")

    start = time.perf_counter()
    build_simulation(con)
    LOG.info("simulation built in %.2fs", time.perf_counter() - start)

    for name in SQL_FILES[1:]:
        run_sql_file(con, name, raw_dir)
    validate_analysis(con)

    start = time.perf_counter()
    ai_qa_marts.build_ai_marts(con, raw_dir, out_dir)
    LOG.info("AI marts built in %.2fs", time.perf_counter() - start)

    counts = export_tables(con, out_dir)
    for table, rows in counts.items():
        LOG.info("exported %-38s %10s rows", table, f"{rows:,}")

    start = time.perf_counter()
    report = quality_checks.run_quality_checks(con, raw_dir, out_dir)
    LOG.info(
        "quality checks in %.2fs: %s",
        time.perf_counter() - start,
        report["status"].value_counts().to_dict(),
    )
    con.close()

    total_mb = sum(p.stat().st_size for p in out_dir.glob("*.parquet")) / 1e6
    LOG.info("marts total %.2f MB in %s | pipeline %.1fs", total_mb, out_dir, time.perf_counter() - t0)
    return counts


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"), help="folder with the raw CSVs")
    parser.add_argument("--out-dir", type=Path, default=Path("data/marts"), help="folder for Parquet marts")
    parser.add_argument(
        "--db",
        type=Path,
        default=None,
        help="DuckDB warehouse file (default: <out-dir>/../warehouse.duckdb; never committed)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args(argv)
    db_path = args.db or (args.out_dir.resolve().parent / "warehouse.duckdb")
    build(args.raw_dir, args.out_dir, db_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
