"""Data-quality checks (section 6.8) and the claimed-vs-measured table.

``run_quality_checks`` executes every check against the freshly built warehouse,
classifies it as pass / warn / fail and writes two marts:

* ``mart_dq_report.parquet``    check name, table, result, threshold, status, detail
* ``mart_claims_check.parquet`` every fact the specification asserts, recomputed

A ``fail`` means the pipeline produced something wrong; ``warn`` is an
informational finding about the source data that is documented and handled.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd

MART_SIZE_LIMIT_MB = 25.0


@dataclass(frozen=True)
class Check:
    """One data-quality check: a SQL returning a single number and a rule."""

    name: str
    table: str
    sql: str
    op: str  # one of "==", ">", ">=", "<="
    threshold: float
    severity: str = "fail"  # status when the rule is violated: "fail" or "warn"
    detail: str = ""


def _passes(value: float, op: str, threshold: float) -> bool:
    """Evaluate ``value <op> threshold``."""
    if op == "==":
        return abs(value - threshold) < 1e-9
    if op == ">":
        return value > threshold
    if op == ">=":
        return value >= threshold
    if op == "<=":
        return value <= threshold
    raise ValueError(f"unknown operator {op}")


def build_checks() -> list[Check]:
    """Return the ordered list of warehouse checks."""
    checks: list[Check] = []
    # Row counts: every staging table must be populated.
    for table in (
        "stg_customers",
        "stg_cases",
        "stg_documents",
        "stg_rules",
        "stg_guidelines",
        "sim_case_ops",
        "stg_benchmark",
        "stg_hallucinated",
    ):
        checks.append(Check(f"row_count_{table}", table, f"SELECT COUNT(*) FROM {table}", ">", 0))

    # Null counts on the columns every KPI depends on.
    null_cols = {
        "stg_customers": (
            "customer_id",
            "risk_category",
            "is_pep",
            "is_sanctioned",
            "identity_verified",
            "address_verified",
            "last_updated",
            "age",
            "dob",
        ),
        "stg_cases": ("case_id", "customer_id", "decision", "verified_docs", "risk_category"),
        "stg_documents": ("document_id", "customer_id", "doc_type", "is_verified", "confidence"),
        "stg_rules": ("rule_id", "rule_category", "jurisdiction", "priority"),
        "stg_guidelines": ("guideline_id", "rule_id", "effective_date"),
    }
    for table, cols in null_cols.items():
        expr = " + ".join(f"COUNT(*) FILTER (WHERE {c} IS NULL)" for c in cols)
        checks.append(
            Check(
                f"null_count_{table}",
                table,
                f"SELECT {expr} FROM {table}",
                "==",
                0,
                detail=f"nulls across {', '.join(cols)}",
            )
        )

    # Duplicate primary keys.
    for table, key in (
        ("stg_customers", "customer_id"),
        ("stg_cases", "case_id"),
        ("stg_cases", "customer_id"),
        ("stg_rules", "rule_id"),
        ("stg_guidelines", "guideline_id"),
        ("stg_benchmark", "benchmark_id"),
        ("stg_hallucinated", "hallucination_id"),
    ):
        checks.append(
            Check(f"duplicate_{key}_{table}", table, f"SELECT COUNT(*) - COUNT(DISTINCT {key}) FROM {table}", "==", 0)
        )

    checks += [
        # Documents: the natural key is (customer_id, doc_type). DocumentID is a
        # random synthetic number that collides across customers, so its
        # duplicates are reported as an informational warning, not a failure.
        Check(
            "duplicate_customer_doc_type_stg_documents",
            "stg_documents",
            "SELECT COUNT(*) - COUNT(DISTINCT (customer_id, doc_type)) FROM stg_documents",
            "==",
            0,
            detail="natural key of a document",
        ),
        Check(
            "duplicate_document_id_stg_documents",
            "stg_documents",
            "SELECT COUNT(*) - COUNT(DISTINCT document_id) FROM stg_documents",
            "==",
            0,
            severity="warn",
            detail="DocumentID values are reused across different customers (synthetic ID collisions)",
        ),
        # Referential integrity.
        Check(
            "ri_case_has_customer",
            "stg_cases",
            "SELECT COUNT(*) FROM stg_cases k ANTI JOIN stg_customers c USING (customer_id)",
            "==",
            0,
        ),
        Check(
            "ri_customer_has_case",
            "stg_customers",
            "SELECT COUNT(*) FROM stg_customers c ANTI JOIN stg_cases k USING (customer_id)",
            "==",
            0,
        ),
        Check(
            "ri_customer_has_5_documents",
            "stg_documents",
            "SELECT COUNT(*) FROM stg_customers c LEFT JOIN (SELECT customer_id, COUNT(*) n "
            "FROM stg_documents GROUP BY 1) d USING (customer_id) WHERE COALESCE(d.n, 0) <> 5",
            "==",
            0,
        ),
        Check(
            "ri_document_has_customer",
            "stg_documents",
            "SELECT COUNT(*) FROM stg_documents d ANTI JOIN stg_customers c USING (customer_id)",
            "==",
            0,
        ),
        Check(
            "ri_case_has_decision",
            "stg_cases",
            "SELECT COUNT(*) FROM stg_cases WHERE decision IS NULL OR decision = ''",
            "==",
            0,
        ),
        Check(
            "ri_guideline_has_rule",
            "stg_guidelines",
            "SELECT COUNT(*) FROM stg_guidelines g ANTI JOIN stg_rules r USING (rule_id)",
            "==",
            0,
        ),
        Check(
            "ri_fact_case_lossless_join",
            "fact_case",
            "SELECT (SELECT COUNT(*) FROM fact_case) - (SELECT COUNT(*) FROM stg_cases)",
            "==",
            0,
            detail="fact_case keeps exactly one row per staged case",
        ),
        Check(
            "ri_sim_covers_every_case",
            "sim_case_ops",
            "SELECT COUNT(*) FROM fact_case WHERE opened_at IS NULL",
            "==",
            0,
        ),
        # Consistency.
        Check(
            "verified_documents_equals_verified_rows",
            "fact_case",
            "SELECT COUNT(*) FROM fact_case WHERE verified_docs <> verified_doc_rows",
            "==",
            0,
            detail="kyc_cases.VerifiedDocuments vs count of verified rows in customer_documents",
        ),
        Check(
            "profile_matches_case_attributes",
            "stg_cases",
            "SELECT COUNT(*) FROM stg_cases k JOIN stg_customers c USING (customer_id) "
            "WHERE k.is_pep <> c.is_pep OR k.is_sanctioned <> c.is_sanctioned "
            "OR k.risk_category <> c.risk_category OR k.country <> c.country "
            "OR k.income <> c.income OR k.aml_flag <> c.aml_flag OR k.occupation <> c.occupation",
            "==",
            0,
        ),
        Check(
            "age_consistent_with_dob",
            "stg_customers",
            "SELECT COUNT(*) FROM stg_customers WHERE age NOT IN ("
            "date_sub('year', dob, (SELECT MAX(last_updated) FROM stg_customers)), "
            "date_sub('year', dob, getvariable('as_of')))",
            "==",
            0,
            detail="Age equals completed years at the extract date (latest LastUpdated) or at AS_OF",
        ),
        Check(
            "age_differs_from_dob_at_as_of",
            "stg_customers",
            "SELECT COUNT(*) FROM stg_customers WHERE age <> date_sub('year', dob, getvariable('as_of'))",
            "==",
            0,
            severity="warn",
            detail="Birthdays between the extract date and AS_OF; Age is not recomputed (documented)",
        ),
        Check(
            "decision_domain",
            "stg_cases",
            "SELECT COUNT(*) FROM stg_cases WHERE decision NOT IN ('Approve', 'Enhanced Due Diligence', "
            "'Reject', 'Manual Review', 'Pending Documents')",
            "==",
            0,
        ),
        Check(
            "no_sanctioned_customer_approved",
            "fact_case",
            "SELECT COUNT(*) FROM fact_case WHERE is_sanctioned AND decision = 'Approve'",
            "==",
            0,
        ),
        Check(
            "engine_agrees_pct",
            "fact_case",
            "SELECT 100.0 * AVG(engine_agrees::INT) FROM fact_case",
            "==",
            100.0,
            detail="rule engine reconciles with the labelled decision",
        ),
        Check(
            "decision_reason_matches_engine_rule",
            "fact_case",
            "SELECT COUNT(*) FROM (SELECT engine_rule FROM fact_case GROUP BY engine_rule "
            "HAVING COUNT(DISTINCT decision_reason) > 1)",
            "==",
            0,
            detail="each fired rule maps to exactly one labelled DecisionReason",
        ),
        Check(
            "confidence_in_unit_interval",
            "stg_documents",
            "SELECT COUNT(*) FROM stg_documents WHERE confidence < 0 OR confidence > 1",
            "==",
            0,
        ),
        Check(
            "guideline_dates_not_in_future",
            "stg_guidelines",
            "SELECT COUNT(*) FROM stg_guidelines WHERE effective_date > getvariable('as_of')",
            "==",
            0,
        ),
        # Simulation sanity (SIMULATED layer).
        Check(
            "sim_closed_after_opened",
            "sim_case_ops",
            "SELECT COUNT(*) FROM sim_case_ops WHERE closed_at < opened_at",
            "==",
            0,
        ),
        Check(
            "sim_closed_not_after_as_of",
            "sim_case_ops",
            "SELECT COUNT(*) FROM sim_case_ops WHERE closed_at > CAST(getvariable('as_of') AS TIMESTAMP)",
            "==",
            0,
        ),
        Check(
            "sim_sla_flag_consistent",
            "sim_case_ops",
            "SELECT COUNT(*) FROM sim_case_ops WHERE sla_breached <> (tat_days > sla_days)",
            "==",
            0,
        ),
        Check("sim_analyst_domain", "sim_case_ops", "SELECT COUNT(DISTINCT assigned_to) FROM sim_case_ops", "<=", 24),
        # AI benchmark integrity.
        Check(
            "ai_label_consistency",
            "stg_benchmark",
            "SELECT COUNT(*) FROM stg_benchmark WHERE is_hallucinated::INT <> expected_label",
            "==",
            0,
        ),
        Check(
            "ai_none_type_is_faithful",
            "stg_benchmark",
            "SELECT COUNT(*) FROM stg_benchmark WHERE (hallucination_type = 'NONE') = is_hallucinated",
            "==",
            0,
        ),
        Check(
            "ai_hallucinated_rows_flagged",
            "stg_hallucinated",
            "SELECT COUNT(*) FROM stg_hallucinated WHERE NOT is_hallucinated",
            "==",
            0,
        ),
        Check(
            "ai_severity_domain",
            "stg_hallucinated",
            "SELECT COUNT(*) FROM stg_hallucinated WHERE severity NOT IN ('Low', 'Medium', 'High', 'Critical')",
            "==",
            0,
        ),
    ]
    return checks


def _scalar(con: duckdb.DuckDBPyConnection, sql: str) -> float:
    row = con.execute(sql).fetchone()
    return float(row[0]) if row and row[0] is not None else 0.0


def run_checks(con: duckdb.DuckDBPyConnection, out_dir: Path) -> pd.DataFrame:
    """Run the warehouse checks plus mart-level checks and return the report."""
    rows = []
    for check in build_checks():
        value = _scalar(con, check.sql)
        ok = _passes(value, check.op, check.threshold)
        rows.append(
            {
                "check_name": check.name,
                "table_name": check.table,
                "result": value,
                "threshold": f"{check.op} {check.threshold:g}",
                "status": "pass" if ok else check.severity,
                "detail": check.detail,
            }
        )

    marts = sorted(p for p in out_dir.glob("*.parquet") if p.stem not in {"mart_dq_report", "mart_claims_check"})
    for path in marts:
        n = _scalar(con, f"SELECT COUNT(*) FROM read_parquet('{path.as_posix()}')")
        rows.append(
            {
                "check_name": f"mart_non_empty_{path.stem}",
                "table_name": path.stem,
                "result": n,
                "threshold": "> 0",
                "status": "pass" if n > 0 else "fail",
                "detail": "every exported mart must contain rows",
            }
        )
    size_mb = sum(p.stat().st_size for p in out_dir.glob("*.parquet")) / 1e6
    rows.append(
        {
            "check_name": "marts_total_size_mb",
            "table_name": "data/marts",
            "result": round(size_mb, 3),
            "threshold": f"<= {MART_SIZE_LIMIT_MB:g}",
            "status": "pass" if size_mb <= MART_SIZE_LIMIT_MB else "fail",
            "detail": "committed marts stay small enough for Git and Streamlit Cloud",
        }
    )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Claimed vs measured: every fact stated in the specification, recomputed.
# (claim id, claim text, claimed display value, measured SQL, low, high)
# A claim matches when low <= measured <= high.
# ---------------------------------------------------------------------------
_RAW_FILES = (
    ("customer_profiles", 100_000, 100_000),
    ("kyc_cases", 100_000, 100_000),
    ("customer_documents", 500_000, 500_000),
    ("aml_rules", 3_000, 3_000),
    ("kyc_guidelines", 10_000, 10_000),
    ("benchmark_dataset", 150_000, 150_000),
    ("hallucinated_answers", 100_000, 100_000),
    ("ground_truth_answers", 500_000, 500_000),
    ("kyc_questions", 500_000, 500_000),
    ("hallucination_labels", 100_000, 200_000),
    ("hallucination_training_dataset", 100_000, 200_000),
    ("hallucination_training_dataset_v2", 100_000, 200_000),
    ("nli_dataset", 100_000, 200_000),
    ("nli_dataset_dedup", 100_000, 200_000),
)

_APPROVED = "(SELECT COUNT(*) FROM fact_case WHERE decision = 'Approve')"
_CLAIMS: tuple[tuple[str, str, str, str, float, float], ...] = (
    (
        "C01",
        "Rule engine reconciles with labelled decisions (%)",
        "100%",
        "SELECT 100.0 * AVG(engine_agrees::INT) FROM fact_case",
        100,
        100,
    ),
    ("C02", "Approved customers", "63,001", f"SELECT {_APPROVED}", 63_001, 63_001),
    (
        "C03",
        "Approved with IdentityVerified = No",
        "31,377",
        "SELECT COUNT(*) FROM fact_case WHERE breach_approved_no_identity",
        31_377,
        31_377,
    ),
    (
        "C04",
        "Approved with identity or address unverified",
        "47,157",
        "SELECT COUNT(*) FROM fact_case WHERE breach_approved_id_or_address",
        47_157,
        47_157,
    ),
    (
        "C05",
        "Share of approvals with identity or address unverified (%)",
        "74.9%",
        f"SELECT ROUND(100.0 * COUNT(*) FILTER (WHERE breach_approved_id_or_address) / {_APPROVED}, 1) FROM fact_case",
        74.9,
        74.9,
    ),
    (
        "C06",
        "Profiles more than 12 months old at 2026-06-30",
        "49,828",
        "SELECT COUNT(*) FROM dim_customer WHERE review_overdue",
        49_828,
        49_828,
    ),
    (
        "C06b",
        "Profiles more than 365 days old at the extract date (max LastUpdated)",
        "49,828",
        "SELECT COUNT(*) FROM stg_customers WHERE date_diff('day', last_updated, "
        "(SELECT MAX(last_updated) FROM stg_customers)) > 365",
        49_828,
        49_828,
    ),
    (
        "C07",
        "Decision Enhanced Due Diligence",
        "23,121",
        "SELECT COUNT(*) FROM fact_case WHERE decision = 'Enhanced Due Diligence'",
        23_121,
        23_121,
    ),
    ("C08", "Decision Reject", "7,877", "SELECT COUNT(*) FROM fact_case WHERE decision = 'Reject'", 7_877, 7_877),
    (
        "C09",
        "Decision Manual Review",
        "4,577",
        "SELECT COUNT(*) FROM fact_case WHERE decision = 'Manual Review'",
        4_577,
        4_577,
    ),
    (
        "C10",
        "Decision Pending Documents",
        "1,424",
        "SELECT COUNT(*) FROM fact_case WHERE decision = 'Pending Documents'",
        1_424,
        1_424,
    ),
    ("C11", "PEP = Yes", "20,030", "SELECT COUNT(*) FROM stg_cases WHERE is_pep", 20_030, 20_030),
    ("C12", "Sanction = Yes", "7,877", "SELECT COUNT(*) FROM stg_cases WHERE is_sanctioned", 7_877, 7_877),
    ("C13", "Risk tier High", "35,575", "SELECT COUNT(*) FROM stg_cases WHERE risk_category = 'High'", 35_575, 35_575),
    (
        "C14",
        "Risk tier Medium",
        "36,671",
        "SELECT COUNT(*) FROM stg_cases WHERE risk_category = 'Medium'",
        36_671,
        36_671,
    ),
    ("C15", "Risk tier Low", "27,754", "SELECT COUNT(*) FROM stg_cases WHERE risk_category = 'Low'", 27_754, 27_754),
    ("C16", "Countries (each about 20%)", "5", "SELECT COUNT(DISTINCT country) FROM stg_cases", 5, 5),
    (
        "C17",
        "Largest country share (%)",
        "about 20%",
        "SELECT ROUND(100.0 * MAX(n) / SUM(n), 2) FROM (SELECT COUNT(*) n FROM stg_cases GROUP BY country)",
        19,
        21,
    ),
    (
        "C18",
        "Smallest country share (%)",
        "about 20%",
        "SELECT ROUND(100.0 * MIN(n) / SUM(n), 2) FROM (SELECT COUNT(*) n FROM stg_cases GROUP BY country)",
        19,
        21,
    ),
    ("C19", "Account types", "4", "SELECT COUNT(DISTINCT account_type) FROM stg_customers", 4, 4),
    ("C20", "Occupations", "10", "SELECT COUNT(DISTINCT occupation) FROM stg_customers", 10, 10),
    ("C21", "Verified documents", "475,052", "SELECT COUNT(*) FROM stg_documents WHERE is_verified", 475_052, 475_052),
    (
        "C22",
        "Unverified documents",
        "24,948",
        "SELECT COUNT(*) FROM stg_documents WHERE NOT is_verified",
        24_948,
        24_948,
    ),
    (
        "C23",
        "Lowest document-type fail rate (%)",
        "about 5%",
        "SELECT ROUND(MIN(p), 2) FROM (SELECT 100.0 * AVG((NOT is_verified)::INT) p FROM stg_documents "
        "GROUP BY doc_type)",
        4.5,
        5.5,
    ),
    (
        "C24",
        "Highest document-type fail rate (%)",
        "about 5%",
        "SELECT ROUND(MAX(p), 2) FROM (SELECT 100.0 * AVG((NOT is_verified)::INT) p FROM stg_documents "
        "GROUP BY doc_type)",
        4.5,
        5.5,
    ),
    ("C25", "OCR confidence minimum", "0.80", "SELECT MIN(confidence) FROM stg_documents", 0.80, 0.80),
    ("C26", "OCR confidence maximum", "0.99", "SELECT MAX(confidence) FROM stg_documents", 0.99, 0.99),
    ("C27", "OCR confidence mean", "0.895", "SELECT ROUND(AVG(confidence), 3) FROM stg_documents", 0.895, 0.895),
    (
        "C28",
        "Cases with VerifiedDocuments = 5",
        "77,387",
        "SELECT COUNT(*) FROM stg_cases WHERE verified_docs = 5",
        77_387,
        77_387,
    ),
    (
        "C29",
        "Cases with VerifiedDocuments = 4",
        "20,414",
        "SELECT COUNT(*) FROM stg_cases WHERE verified_docs = 4",
        20_414,
        20_414,
    ),
    (
        "C30",
        "Cases with VerifiedDocuments = 3",
        "2,068",
        "SELECT COUNT(*) FROM stg_cases WHERE verified_docs = 3",
        2_068,
        2_068,
    ),
    (
        "C31",
        "Cases with VerifiedDocuments = 2",
        "126",
        "SELECT COUNT(*) FROM stg_cases WHERE verified_docs = 2",
        126,
        126,
    ),
    ("C32", "Cases with VerifiedDocuments = 1", "5", "SELECT COUNT(*) FROM stg_cases WHERE verified_docs = 1", 5, 5),
    (
        "C33",
        "VerifiedDocuments equals verified document rows (% of customers)",
        "100%",
        "SELECT 100.0 * AVG((verified_docs = verified_doc_rows)::INT) FROM fact_case",
        100,
        100,
    ),
    (
        "C34",
        "Funnel: passed sanctions",
        "92,123",
        "SELECT cases FROM mart_funnel WHERE stage_order = 2",
        92_123,
        92_123,
    ),
    ("C35", "Funnel: passed PEP", "73,648", "SELECT cases FROM mart_funnel WHERE stage_order = 3", 73_648, 73_648),
    ("C36", "Funnel: passed risk", "64,425", "SELECT cases FROM mart_funnel WHERE stage_order = 4", 64_425, 64_425),
    (
        "C37",
        "High-risk non-PEP escalations sent to EDD (%)",
        "about 50%",
        "SELECT ROUND(100.0 * AVG((decision = 'Enhanced Due Diligence')::INT), 2) FROM fact_case "
        "WHERE engine_decision = 'Escalate (EDD/Manual)'",
        45,
        55,
    ),
    (
        "C38",
        "Lowest sanction rate by country (%)",
        "7.6%",
        "SELECT ROUND(MIN(p), 1) FROM (SELECT 100.0 * AVG(is_sanctioned::INT) p FROM stg_cases GROUP BY country)",
        7.6,
        7.6,
    ),
    (
        "C39",
        "Highest sanction rate by country (%)",
        "8.2%",
        "SELECT ROUND(MAX(p), 1) FROM (SELECT 100.0 * AVG(is_sanctioned::INT) p FROM stg_cases GROUP BY country)",
        8.2,
        8.2,
    ),
    ("C40", "Minimum income", "200k", "SELECT MIN(income) FROM stg_customers", 200_000, 210_000),
    ("C41", "Maximum income", "10M", "SELECT MAX(income) FROM stg_customers", 9_990_000, 10_000_000),
    (
        "C42",
        "IdentityVerified = Yes (%)",
        "about 50%",
        "SELECT ROUND(100.0 * AVG(identity_verified::INT), 2) FROM stg_customers",
        48,
        52,
    ),
    (
        "C43",
        "AddressVerified = Yes (%)",
        "about 50%",
        "SELECT ROUND(100.0 * AVG(address_verified::INT), 2) FROM stg_customers",
        48,
        52,
    ),
    ("C44", "Earliest document expiry year", "2027", "SELECT MIN(year(expiry_date)) FROM stg_documents", 2027, 2027),
    ("C45", "Latest document expiry year", "2036", "SELECT MAX(year(expiry_date)) FROM stg_documents", 2036, 2036),
    (
        "C46",
        "Distinct masked generated-answer templates",
        "25",
        "SELECT COUNT(DISTINCT generated_masked) FROM stg_benchmark",
        25,
        25,
    ),
    (
        "C47",
        "Lowest hallucination % by question template",
        "66.5%",
        "SELECT ROUND(MIN(hallucination_pct), 1) FROM mart_ai_by_question",
        66.5,
        66.5,
    ),
    (
        "C48",
        "Highest hallucination % by question template",
        "66.9%",
        "SELECT ROUND(MAX(hallucination_pct), 1) FROM mart_ai_by_question",
        66.9,
        66.9,
    ),
    (
        "C49",
        "Faithful benchmark answers",
        "50,000",
        "SELECT COUNT(*) FROM stg_benchmark WHERE NOT is_hallucinated",
        50_000,
        50_000,
    ),
    (
        "C50",
        "Hallucinated benchmark answers",
        "100,000",
        "SELECT COUNT(*) FROM stg_benchmark WHERE is_hallucinated",
        100_000,
        100_000,
    ),
    (
        "C51",
        "Smallest hallucination type (answers)",
        "about 20,000",
        "SELECT MIN(n) FROM (SELECT COUNT(*) n FROM stg_hallucinated GROUP BY hallucination_type)",
        19_000,
        21_000,
    ),
    (
        "C52",
        "Largest hallucination type (answers)",
        "about 20,000",
        "SELECT MAX(n) FROM (SELECT COUNT(*) n FROM stg_hallucinated GROUP BY hallucination_type)",
        19_000,
        21_000,
    ),
    ("C53", "Rules without a guideline", "about 117", "SELECT COUNT(*) FROM dim_rule WHERE is_orphan", 117, 117),
    ("C54", "Rule categories", "7", "SELECT COUNT(DISTINCT rule_category) FROM stg_rules", 7, 7),
    (
        "C55",
        "SIMULATED average turnaround (days)",
        "about 4.6",
        "SELECT ROUND(AVG(tat_days), 2) FROM sim_case_ops",
        4.4,
        4.8,
    ),
    (
        "C56",
        "SIMULATED SLA breach (%)",
        "about 25%",
        "SELECT ROUND(100.0 * AVG(sla_breached::INT), 1) FROM sim_case_ops",
        23,
        27,
    ),
    ("C57", "SIMULATED open cases", "about 500", "SELECT COUNT(*) FROM sim_case_ops WHERE is_open", 400, 600),
)


def claims_vs_measured(con: duckdb.DuckDBPyConnection, raw_dir: Path) -> pd.DataFrame:
    """Recompute every fact the specification claims and flag mismatches."""
    rows = []
    for claim_id, claim, claimed, sql, low, high in _CLAIMS:
        measured = _scalar(con, sql)
        rows.append(
            {
                "claim_id": claim_id,
                "claim": claim,
                "claimed": claimed,
                "measured": measured,
                "matches": bool(low - 1e-9 <= measured <= high + 1e-9),
            }
        )
    raw = raw_dir.resolve()
    present = sorted(raw.glob("*.csv"))
    total_mb = sum(p.stat().st_size for p in present) / 1e6
    rows.append(
        {
            "claim_id": "F00",
            "claim": "Raw CSV files in archive",
            "claimed": "14",
            "measured": float(len(present)),
            "matches": len(present) == 14,
        }
    )
    rows.append(
        {
            "claim_id": "F01",
            "claim": "Raw CSV size (MB, decimal)",
            "claimed": "about 645 MB",
            "measured": round(total_mb, 1),
            "matches": 612 <= total_mb <= 678,
        }
    )
    for i, (stem, low, high) in enumerate(_RAW_FILES, start=2):
        path = raw / f"{stem}.csv"
        if path.exists():
            safe = path.as_posix().replace("'", "''")
            n = _scalar(con, f"SELECT COUNT(*) FROM read_csv('{safe}', header = true, auto_detect = true)")
        else:
            n = float("nan")
        claimed = f"{low:,}" if low == high else f"{low // 1000}k to {high // 1000}k"
        rows.append(
            {
                "claim_id": f"F{i:02d}",
                "claim": f"Rows in {stem}.csv",
                "claimed": claimed,
                "measured": n,
                "matches": bool(low <= n <= high),
            }
        )
    return pd.DataFrame(rows)


def run_quality_checks(con: duckdb.DuckDBPyConnection, raw_dir: Path, out_dir: Path) -> pd.DataFrame:
    """Run all checks, write ``mart_dq_report`` and ``mart_claims_check``, return the report."""
    report = run_checks(con, out_dir)
    claims = claims_vs_measured(con, raw_dir)
    for name, frame in (("mart_dq_report", report), ("mart_claims_check", claims)):
        con.register("frame_df", frame)
        con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM frame_df")
        con.unregister("frame_df")
        target = (out_dir / f"{name}.parquet").as_posix().replace("'", "''")
        con.execute(f"COPY {name} TO '{target}' (FORMAT parquet, COMPRESSION zstd)")
    return report


def record_mart_check(out_dir: Path, mart: str) -> None:
    """Upsert a ``mart_non_empty_<mart>`` row into an existing mart_dq_report.

    Used by later pipeline stages (the ML stage) that write marts after the ETL
    has already produced the report.
    """
    report_path = out_dir / "mart_dq_report.parquet"
    mart_path = out_dir / f"{mart}.parquet"
    if not report_path.exists() or not mart_path.exists():
        return
    report = pd.read_parquet(report_path)
    rows = float(len(pd.read_parquet(mart_path)))
    name = f"mart_non_empty_{mart}"
    report = report[report["check_name"] != name]
    extra = pd.DataFrame(
        [
            {
                "check_name": name,
                "table_name": mart,
                "result": rows,
                "threshold": "> 0",
                "status": "pass" if rows > 0 else "fail",
                "detail": "every exported mart must contain rows",
            }
        ]
    )
    pd.concat([report, extra], ignore_index=True).to_parquet(report_path, compression="zstd", index=False)
