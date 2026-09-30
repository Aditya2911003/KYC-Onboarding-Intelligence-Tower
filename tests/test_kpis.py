"""KPI functions on a tiny hand-built fixture; SQL snippets agree with Python."""

from __future__ import annotations

import math
from datetime import date

import duckdb
import pandas as pd
import pytest

from app import insights, kpis
from app.state import Filters


@pytest.fixture()
def cases() -> pd.DataFrame:
    """Six hand-built cases with known answers."""
    return pd.DataFrame(
        {
            "decision": ["Approve", "Approve", "Approve", "Approve", "Reject", "Enhanced Due Diligence"],
            "identity_verified": [True, False, True, False, True, False],
            "address_verified": [True, True, False, False, False, True],
            "verified_docs": [5, 5, 4, 5, 5, 3],
            "tat_days": [1.0, 2.0, 4.0, 8.0, 3.0, 12.0],
            "sla_days": [3, 3, 3, 3, 3, 10],
            "is_open": [False, False, False, True, False, True],
            "engine_agrees": [True] * 6,
            "review_overdue": [True, False, False, True, False, False],
            "last_updated": pd.to_datetime(
                ["2025-01-01", "2026-01-01", "2026-06-01", "2024-12-31", "2025-07-01", "2025-06-30"]
            ),
        }
    )


def test_counts_and_rates(cases: pd.DataFrame) -> None:
    assert kpis.cases(cases) == 6
    assert kpis.approval_rate(cases) == pytest.approx(4 / 6)
    assert kpis.decision_rate(cases, "Reject") == pytest.approx(1 / 6)
    assert kpis.open_cases(cases) == 2


def test_control_breach_components(cases: pd.DataFrame) -> None:
    comp = kpis.control_breach_components(cases)
    assert comp["approvals"] == 4
    assert comp["control_breach_rate"] == pytest.approx(3 / 4)
    assert comp["breach_no_identity_rate"] == pytest.approx(2 / 4)
    assert comp["breach_no_address_rate"] == pytest.approx(2 / 4)
    assert comp["breach_missing_doc_rate"] == pytest.approx(1 / 4)
    assert kpis.control_breach_rate(cases.iloc[4:]) != kpis.control_breach_rate(cases.iloc[4:])  # NaN: no approvals


def test_turnaround_and_sla(cases: pd.DataFrame) -> None:
    assert kpis.avg_turnaround(cases) == pytest.approx(30 / 6)
    assert kpis.p90_turnaround(cases) == pytest.approx(cases["tat_days"].quantile(0.9))
    assert kpis.sla_breach_pct(cases) == pytest.approx(3 / 6)  # 4 > 3, 8 > 3, 12 > 10


def test_review_overdue_uses_365_days(cases: pd.DataFrame) -> None:
    # 2025-01-01 and 2024-12-31 are > 365 days before 2026-06-30; 2025-06-30 is exactly 365 (not overdue).
    assert kpis.review_overdue_pct(cases) == pytest.approx(2 / 6)


def test_document_rates() -> None:
    docs = pd.DataFrame({"verified": [True, False, True, True], "confidence": [0.80, 0.90, 0.849, 0.85]})
    assert kpis.document_fail_rate(docs) == pytest.approx(0.25)
    assert kpis.low_confidence_rate(docs) == pytest.approx(0.5)
    assert kpis.hallucination_rate(2, 3) == pytest.approx(2 / 3)


def test_period_delta_and_previous_period() -> None:
    assert kpis.period_delta(110, 100) == pytest.approx(0.10)
    assert kpis.period_delta(5, 0) is None
    assert kpis.period_delta(5, float("nan")) is None
    start, end = date(2026, 4, 1), date(2026, 6, 30)  # 91 days inclusive
    prev_start, prev_end = kpis.previous_period(start, end)
    assert prev_end == date(2026, 3, 31)  # the day before the range starts
    assert (prev_end - prev_start) == (end - start)  # equal length
    assert prev_start == date(2025, 12, 31)


def test_kpi_sql_snippets_match_python(cases: pd.DataFrame) -> None:
    con = duckdb.connect()
    con.register("mart_case_detail", cases)
    select = ", ".join(f"{sql} AS {name}" for name, sql in kpis.KPI_SQL.items())
    row = con.execute(f"SELECT {select} FROM mart_case_detail").df().iloc[0]
    comp = kpis.control_breach_components(cases)
    assert row["cases"] == kpis.cases(cases)
    assert row["approval_rate"] == pytest.approx(kpis.approval_rate(cases))
    assert row["avg_tat_days"] == pytest.approx(kpis.avg_turnaround(cases))
    assert row["p90_tat_days"] == pytest.approx(kpis.p90_turnaround(cases))
    assert row["sla_breach_pct"] == pytest.approx(kpis.sla_breach_pct(cases))
    assert row["open_cases"] == kpis.open_cases(cases)
    for key in ("control_breach_rate", "breach_no_identity_rate", "breach_no_address_rate", "breach_missing_doc_rate"):
        assert row[key] == pytest.approx(comp[key])
    assert row["engine_agreement"] == pytest.approx(kpis.rule_engine_agreement(cases))
    assert row["review_overdue_pct"] == pytest.approx(kpis.review_overdue_pct(cases))


def test_where_clause_is_parameterised(monkeypatch: pytest.MonkeyPatch) -> None:
    from app import data

    hostile = "UK'); DROP TABLE mart_case_detail; --"
    sql, params = data.where_clause(Filters(date(2025, 1, 1), date(2025, 12, 31), country=(hostile, "USA")))
    assert hostile not in sql and "?" in sql
    assert sql.count("?") == len(params) == 4
    assert params[2:] == (hostile, "USA")


def test_insights_handle_empty_and_flat_data() -> None:
    assert insights.executive_insights({"cases": 0}, None) == [insights.EMPTY_MESSAGE]
    assert insights.funnel_insights(pd.DataFrame({"stage_order": [], "stage": [], "cases": []})) == [
        insights.EMPTY_MESSAGE
    ]
    flat = pd.Series({"UK": 0.076, "USA": 0.082})
    assert insights.flat_note(flat, "the sanction rate", "countries").startswith("Flat:")
    steep = pd.Series({"Low": 0.10, "High": 0.60})
    assert "ranges from" in insights.flat_note(steep, "the rate", "tiers")
    assert math.isclose(insights.spread_pp(steep), 50.0)


def test_ratio_insight_wording() -> None:
    df = pd.DataFrame({"risk_category": ["High", "High", "Low"], "tat_days": [6.0, 6.2, 4.3]})
    text = insights.ratio_insight(df, "risk_category", "tat_days", "High", "Low", "risk")
    assert text == "High-risk cases take 1.4x longer than Low-risk cases (6.1 d vs 4.3 d)."
