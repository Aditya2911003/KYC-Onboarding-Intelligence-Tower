"""Write the deterministic 1,000-customer raw sample used by CI and tests.

Selects 1,000 customers with a fixed seed and writes their rows from
customer_profiles, kyc_cases and customer_documents (without OCRText), plus
1,000 rows each from benchmark_dataset and hallucinated_answers and the full
aml_rules and kyc_guidelines. Referential integrity is preserved: every sampled
case has its customer and exactly five documents, every sampled hallucinated
benchmark answer has its severity row, and every guideline has its rule.

Usage::

    python etl/make_sample.py --raw-dir data/raw --out-dir data/sample
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

import duckdb
import numpy as np

LOG = logging.getLogger("make_sample")
SEED = 42
N_CUSTOMERS = 1_000
N_AI_ROWS = 1_000


def _q(path: Path) -> str:
    return path.resolve().as_posix().replace("'", "''")


def _csv(path: Path) -> str:
    """read_csv() call that keeps every value as text, so the sample mirrors the raw format."""
    return f"read_csv('{_q(path)}', header = true, all_varchar = true)"


def make_sample(raw_dir: Path, out_dir: Path, n_customers: int = N_CUSTOMERS, seed: int = SEED) -> dict[str, int]:
    """Create the sample CSVs and return row counts per file."""
    out_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    rng = np.random.default_rng(seed)

    ids = [
        r[0]
        for r in con.execute(f"SELECT CustomerID FROM {_csv(raw_dir / 'customer_profiles.csv')} ORDER BY 1").fetchall()
    ]
    chosen = sorted(rng.choice(np.array(ids), size=min(n_customers, len(ids)), replace=False).tolist())
    con.execute("CREATE TABLE chosen AS SELECT unnest(?::VARCHAR[]) AS CustomerID", [chosen])

    bench_ids = [
        r[0]
        for r in con.execute(f"SELECT BenchmarkID FROM {_csv(raw_dir / 'benchmark_dataset.csv')} ORDER BY 1").fetchall()
    ]
    bench_pick = sorted(rng.choice(np.array(bench_ids), size=min(N_AI_ROWS, len(bench_ids)), replace=False).tolist())
    con.execute("CREATE TABLE bench_pick AS SELECT unnest(?::VARCHAR[]) AS BenchmarkID", [bench_pick])
    con.execute(
        f"CREATE TABLE bench AS SELECT b.* FROM {_csv(raw_dir / 'benchmark_dataset.csv')} b "
        "JOIN bench_pick USING (BenchmarkID) ORDER BY BenchmarkID"
    )
    # Hallucinated answers: the severity rows for the sampled hallucinated benchmark answers,
    # topped up to exactly N_AI_ROWS with other rows drawn by the same seeded generator.
    con.execute(f"CREATE TABLE hall_all AS SELECT * FROM {_csv(raw_dir / 'hallucinated_answers.csv')}")
    linked = [
        r[0]
        for r in con.execute(
            "SELECT HallucinationID FROM hall_all "
            "WHERE AnswerID IN (SELECT AnswerID FROM bench WHERE Hallucinated = '1') ORDER BY 1"
        ).fetchall()
    ]
    others = [
        r[0]
        for r in con.execute(
            "SELECT HallucinationID FROM hall_all "
            "WHERE HallucinationID NOT IN (SELECT unnest(?::VARCHAR[])) ORDER BY 1",
            [linked],
        ).fetchall()
    ]
    top_up = rng.choice(np.array(others), size=max(N_AI_ROWS - len(linked), 0), replace=False).tolist()
    con.execute("CREATE TABLE hall_pick AS SELECT unnest(?::VARCHAR[]) AS HallucinationID", [linked + top_up])

    exports = {
        "customer_profiles.csv": f"SELECT p.* FROM {_csv(raw_dir / 'customer_profiles.csv')} p "
        "JOIN chosen USING (CustomerID) ORDER BY CustomerID",
        "kyc_cases.csv": f"SELECT k.* FROM {_csv(raw_dir / 'kyc_cases.csv')} k "
        "JOIN chosen USING (CustomerID) ORDER BY CaseID",
        "customer_documents.csv": (
            "SELECT d.DocumentID, d.CustomerID, d.DocumentType, d.DocumentNumber, d.IssueCountry, d.ExpiryDate, "
            f"d.Verified, d.Confidence, d.Source FROM {_csv(raw_dir / 'customer_documents.csv')} d "
            "JOIN chosen USING (CustomerID) ORDER BY CustomerID, DocumentType"
        ),
        "benchmark_dataset.csv": "SELECT * FROM bench ORDER BY BenchmarkID",
        "hallucinated_answers.csv": "SELECT h.* FROM hall_all h JOIN hall_pick USING (HallucinationID) "
        "ORDER BY HallucinationID",
        "aml_rules.csv": f"SELECT * FROM {_csv(raw_dir / 'aml_rules.csv')} ORDER BY RuleID",
        "kyc_guidelines.csv": f"SELECT * FROM {_csv(raw_dir / 'kyc_guidelines.csv')} ORDER BY GuidelineID",
    }
    counts: dict[str, int] = {}
    for name, sql in exports.items():
        target = _q(out_dir / name)
        con.execute(f"COPY ({sql}) TO '{target}' (HEADER, DELIMITER ',')")
        row = con.execute(f"SELECT COUNT(*) FROM {_csv(out_dir / name)}").fetchone()
        counts[name] = int(row[0]) if row else 0
        LOG.info("%-26s %6s rows", name, f"{counts[name]:,}")
    con.close()
    return counts


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--out-dir", type=Path, default=Path("data/sample"))
    parser.add_argument("--n-customers", type=int, default=N_CUSTOMERS)
    args = parser.parse_args(argv)
    make_sample(args.raw_dir, args.out_dir, args.n_customers)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
