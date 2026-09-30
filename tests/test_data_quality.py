"""Data quality, simulation sanity and the AI detector."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from etl import ai_qa_marts, build_warehouse
from tests.conftest import scalar


def test_dq_report_has_no_fail(marts_dir: Path) -> None:
    report = pd.read_parquet(marts_dir / "mart_dq_report.parquet")
    assert len(report) > 30
    assert set(report["status"]) <= {"pass", "warn", "fail"}
    assert (report["status"] != "fail").all(), report[report["status"] == "fail"].to_dict("records")


def test_verified_documents_equals_verified_rows(con: duckdb.DuckDBPyConnection) -> None:
    assert scalar(con, "SELECT COUNT(*) FROM fact_case WHERE verified_docs <> verified_doc_rows") == 0


def test_every_customer_has_one_case_and_five_documents(con: duckdb.DuckDBPyConnection) -> None:
    assert scalar(con, "SELECT COUNT(*) FROM fact_case WHERE doc_rows <> 5") == 0
    assert scalar(con, "SELECT COUNT(*) - COUNT(DISTINCT customer_id) FROM stg_cases") == 0
    assert scalar(con, "SELECT COUNT(*) - COUNT(DISTINCT (customer_id, doc_type)) FROM stg_documents") == 0


def test_guideline_dates_parsed_day_first(con: duckdb.DuckDBPyConnection) -> None:
    # The sample contains GUIDE_00001 with EffectiveDate '08-01-2023' = 8 January 2023 (dd-mm-yyyy).
    assert (
        str(scalar(con, "SELECT effective_date FROM stg_guidelines WHERE guideline_id = 'GUIDE_00001'")) == "2023-01-08"
    )


def test_simulated_dates_are_ordered(con: duckdb.DuckDBPyConnection) -> None:
    assert scalar(con, "SELECT COUNT(*) FROM sim_case_ops WHERE closed_at < opened_at") == 0
    assert scalar(con, "SELECT COUNT(*) FROM sim_case_ops WHERE closed_at > TIMESTAMP '2026-06-30'") == 0
    assert scalar(con, "SELECT COUNT(*) FROM sim_case_ops WHERE is_open AND closed_at <> TIMESTAMP '2026-06-30'") == 0
    assert scalar(con, "SELECT COUNT(*) FROM sim_case_ops WHERE sla_breached <> (tat_days > sla_days)") == 0


def _cases(n: int = 500) -> pd.DataFrame:
    decisions = list(build_warehouse.HANDLING_BASE_DAYS)
    return pd.DataFrame(
        {
            "case_id": [f"CASE_{i:06d}" for i in range(n)],
            "decision": [decisions[i % len(decisions)] for i in range(n)],
            "risk_category": ["High" if i % 3 == 0 else "Low" for i in range(n)],
            "is_pep": [i % 5 == 0 for i in range(n)],
        }
    )


def test_simulation_is_reproducible_with_seed_42() -> None:
    first = build_warehouse.simulate_case_ops(_cases())
    second = build_warehouse.simulate_case_ops(_cases().sample(frac=1, random_state=7))  # order-independent
    pd.testing.assert_frame_equal(first, second)


def test_simulation_changes_with_seed() -> None:
    a = build_warehouse.simulate_case_ops(_cases(), seed=42)
    b = build_warehouse.simulate_case_ops(_cases(), seed=43)
    assert not a["tat_days"].equals(b["tat_days"])


def test_simulation_respects_parameters() -> None:
    sim = build_warehouse.simulate_case_ops(_cases(2_000))
    assert sim["assigned_to"].str.match(r"^Analyst_(0[1-9]|1\d|2[0-4])$").all()
    assert set(sim["channel"]) <= set(build_warehouse.CHANNELS)
    offsets = (pd.Timestamp(build_warehouse.AS_OF) - sim["opened_at"]).dt.days
    assert offsets.between(0, build_warehouse.OPENED_WINDOW_DAYS - 1).all()
    assert (sim["tat_days"] >= 0).all() and (sim["closed_at"] >= sim["opened_at"]).all()


def test_detector_classifies_each_pattern() -> None:
    gt = "Customer C# can be approved for onboarding. The customer satisfies KYC requirements."
    assert ai_qa_marts.detect(gt, gt)[0] == "NONE"
    assert ai_qa_marts.detect(gt, gt + " As per AML Regulation Section 99.7, onboarding must be delayed.")[0] == (
        "Fabricated Regulation"
    )
    assert ai_qa_marts.detect(gt, gt + " The customer has a Low AML Risk classification.")[0] == "Wrong Risk Score"
    assert ai_qa_marts.detect(gt, gt + " The customer was previously investigated.")[0] == "Unsupported Claim"
    assert ai_qa_marts.detect(gt, "Customer C# must be rejected due to AML concerns.")[0] == "Contradiction"
    assert ai_qa_marts.detect(gt, "Customer C# requires additional review.")[0] == "Missing Evidence"


def test_detector_metrics_from_confusion() -> None:
    confusion = pd.DataFrame(
        {
            "true_type": ["NONE", "NONE", "Contradiction"],
            "predicted_type": ["NONE", "Contradiction", "Contradiction"],
            "answers": [8, 2, 10],
        }
    )
    metrics = ai_qa_marts.detector_metrics(confusion).set_index("hallucination_type")
    assert metrics.loc["NONE", "recall"] == 0.8
    assert metrics.loc["Contradiction", "precision"] == round(10 / 12, 4)
