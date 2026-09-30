"""Marts: presence, schema, key uniqueness, privacy and cross-mart consistency."""

from __future__ import annotations

import re
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from tests.conftest import COMMITTED_MARTS, REPO_ROOT, scalar

EXPECTED_MARTS = [
    "mart_case_detail",
    "mart_monthly_kpi",
    "mart_mom",
    "mart_analyst",
    "mart_funnel",
    "mart_control_breaches",
    "mart_doc_quality",
    "mart_doc_conf_hist",
    "mart_review_backlog",
    "mart_review_backlog_age",
    "mart_rule_coverage",
    "mart_guideline_timeline",
    "mart_rules",
    "mart_guidelines",
    "mart_customer_docs",
    "mart_dq_report",
    "mart_claims_check",
    "mart_ai_by_type",
    "mart_ai_by_question",
    "mart_ai_severity",
    "mart_ai_detector_confusion",
    "mart_ai_detector_metrics",
    "ai_examples",
    "analysis_funnel",
    "analysis_worst_analyst_month",
    "analysis_review_backlog",
    "analysis_breach_by_channel_country",
    "analysis_mom",
    "analysis_analyst_rank",
    "analysis_rule_orphans",
]
CASE_DETAIL_COLUMNS = {
    "case_id",
    "customer_id",
    "country",
    "occupation",
    "account_type",
    "risk_category",
    "is_pep",
    "is_sanctioned",
    "decision",
    "decision_reason",
    "engine_decision",
    "engine_agrees",
    "verified_docs",
    "income_quintile",
    "age_band",
    "channel",
    "assigned_to",
    "opened_date",
    "opened_month",
    "tat_days",
    "sla_days",
    "sla_breached",
    "is_open",
    "breach_approved_no_identity",
    "breach_approved_no_address",
    "breach_approved_missing_doc",
    "review_overdue",
    "identity_verified",
    "address_verified",
}


def read(marts: Path, name: str) -> pd.DataFrame:
    return pd.read_parquet(marts / f"{name}.parquet")


@pytest.mark.parametrize("name", EXPECTED_MARTS)
def test_mart_exists_and_is_non_empty(marts_dir: Path, name: str) -> None:
    assert len(read(marts_dir, name)) > 0


def test_case_detail_has_expected_columns_and_unique_keys(marts_dir: Path) -> None:
    detail = read(marts_dir, "mart_case_detail")
    assert set(detail.columns) >= CASE_DETAIL_COLUMNS
    assert detail["case_id"].is_unique and detail["customer_id"].is_unique


def test_marts_contain_no_direct_identifiers(marts_dir: Path) -> None:
    forbidden = {"full_name", "fullname", "dob", "document_number", "ocrtext", "ocr_text"}
    for path in marts_dir.glob("*.parquet"):
        cols = {c.lower() for c in pd.read_parquet(path).columns}
        assert not cols & forbidden, f"{path.name} exposes {cols & forbidden}"


def test_fact_case_join_is_lossless(con: duckdb.DuckDBPyConnection) -> None:
    assert scalar(con, "SELECT COUNT(*) FROM fact_case") == scalar(con, "SELECT COUNT(*) FROM stg_cases")
    assert scalar(con, "SELECT COUNT(*) FROM fact_case") == scalar(con, "SELECT COUNT(*) FROM stg_customers")


def test_funnel_is_monotonic_and_matches_analysis_query(marts_dir: Path) -> None:
    mart = read(marts_dir, "mart_funnel").sort_values("stage_order")
    analysis = read(marts_dir, "analysis_funnel").sort_values("stage_order")
    assert mart["cases"].is_monotonic_decreasing
    assert mart["cases"].tolist() == analysis["cases"].tolist()
    assert analysis["pct_of_opened"].iloc[0] == 100


def test_control_breach_mart_matches_case_detail(marts_dir: Path) -> None:
    detail = read(marts_dir, "mart_case_detail")
    breaches = read(marts_dir, "mart_control_breaches")
    assert breaches["approvals"].sum() == (detail["decision"] == "Approve").sum()
    assert breaches["breach_id_or_address"].sum() == detail["breach_approved_id_or_address"].sum()
    assert (breaches["breach_id_or_address"] <= breaches["approvals"]).all()


def test_review_backlog_marts_agree(marts_dir: Path) -> None:
    a = read(marts_dir, "analysis_review_backlog").set_index("risk_category")["overdue"].sort_index()
    m = read(marts_dir, "mart_review_backlog").set_index("risk_category")["overdue"].sort_index()
    assert a.equals(m)


def test_ai_examples_are_masked_and_capped(marts_dir: Path) -> None:
    examples = read(marts_dir, "ai_examples")
    assert 0 < len(examples) <= 25
    text = " ".join(examples[["question_template", "generated_masked", "ground_truth_masked"]].astype(str).sum(axis=1))
    assert not re.search(r"C\d{3,}", text), "customer IDs must be masked"


def test_ai_by_type_rates(marts_dir: Path) -> None:
    by_type = read(marts_dir, "mart_ai_by_type").set_index("hallucination_type")
    assert by_type.loc["NONE", "hallucination_rate_pct"] == 0
    assert (by_type.drop(index="NONE")["hallucination_rate_pct"] == 100).all()


def test_committed_marts_are_under_25_mb() -> None:
    total = sum(p.stat().st_size for p in COMMITTED_MARTS.glob("*.parquet"))
    assert 0 < total < 25e6
    assert all(p.stat().st_size < 25e6 for p in COMMITTED_MARTS.glob("*"))


def test_readme_headline_numbers_are_backed_by_committed_marts() -> None:
    """Every headline number quoted in the README is recomputed from the committed marts."""
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    detail = pd.read_parquet(COMMITTED_MARTS / "mart_case_detail.parquet")
    approved = detail[detail["decision"] == "Approve"]
    breach = approved["breach_approved_id_or_address"].mean()
    agree = detail["engine_agrees"].mean()
    for figure in (
        f"{len(detail):,}",
        f"{len(approved):,}",
        f"{100 * breach:.1f}%",
        f"{100 * agree:.0f}%",
        f"{int(approved['breach_approved_id_or_address'].sum()):,}",
        f"{int(detail['review_overdue'].sum()):,}",
    ):
        assert figure in readme, f"README is missing computed figure {figure}"
