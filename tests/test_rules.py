"""Rule-engine reconciliation: SQL engine, Python engine and labels agree."""

from __future__ import annotations

import itertools

import duckdb

from app import kpis
from tests.conftest import scalar


def test_engine_agrees_for_every_case(con: duckdb.DuckDBPyConnection) -> None:
    assert scalar(con, "SELECT COUNT(*) FROM fact_case WHERE NOT engine_agrees") == 0
    assert scalar(con, "SELECT COUNT(*) FROM fact_case") > 0


def test_python_engine_matches_sql_engine(con: duckdb.DuckDBPyConnection) -> None:
    rows = con.execute(
        "SELECT is_sanctioned, is_pep, risk_category, verified_docs, engine_decision, engine_rule, decision "
        "FROM fact_case"
    ).fetchall()
    for sanctioned, pep, risk, docs, engine, rule, decision in rows:
        result = kpis.engine_decision(sanctioned, pep, risk, docs)
        assert (result.decision, result.rule) == (engine, rule)
        assert kpis.engine_agrees(result.decision, decision)


def test_python_engine_matches_sql_case_on_every_input_combination() -> None:
    combos = list(itertools.product([True, False], [True, False], ["Low", "Medium", "High"], range(0, 6)))
    con = duckdb.connect()
    con.execute("CREATE TABLE t (s BOOLEAN, p BOOLEAN, r VARCHAR, d INTEGER)")
    con.executemany("INSERT INTO t VALUES (?, ?, ?, ?)", combos)
    sql_out = con.execute(
        "SELECT s, p, r, d, CASE WHEN s THEN 'Reject' WHEN p THEN 'Enhanced Due Diligence' "
        "WHEN r = 'High' THEN 'Escalate (EDD/Manual)' WHEN d < 4 THEN 'Pending Documents' ELSE 'Approve' END "
        "FROM t"
    ).fetchall()
    for s, p, r, d, expected in sql_out:
        assert kpis.engine_decision(s, p, r, d).decision == expected


def test_sanction_takes_precedence_over_pep_and_risk() -> None:
    assert kpis.engine_decision(True, True, "High", 1).decision == "Reject"
    assert kpis.engine_decision(False, True, "High", 1).decision == "Enhanced Due Diligence"


def test_document_threshold_is_four() -> None:
    assert kpis.engine_decision(False, False, "Low", 3).decision == "Pending Documents"
    assert kpis.engine_decision(False, False, "Low", 4).decision == "Approve"


def test_escalation_matches_edd_or_manual_review() -> None:
    assert kpis.engine_agrees("Escalate (EDD/Manual)", "Manual Review")
    assert kpis.engine_agrees("Escalate (EDD/Manual)", "Enhanced Due Diligence")
    assert not kpis.engine_agrees("Escalate (EDD/Manual)", "Approve")
    assert not kpis.engine_agrees("Approve", "Reject")


def test_no_sanctioned_customer_is_approved(con: duckdb.DuckDBPyConnection) -> None:
    assert scalar(con, "SELECT COUNT(*) FROM fact_case WHERE is_sanctioned AND decision = 'Approve'") == 0


def test_each_rule_maps_to_one_decision_reason(con: duckdb.DuckDBPyConnection) -> None:
    assert (
        scalar(
            con,
            "SELECT COUNT(*) FROM (SELECT engine_rule FROM fact_case GROUP BY 1 "
            "HAVING COUNT(DISTINCT decision_reason) > 1)",
        )
        == 0
    )


def test_risk_score_components_and_cap() -> None:
    score, parts = kpis.risk_score_breakdown(True, True, "High", False, False, 0)
    assert score == 100  # capped
    assert sum(p for _, p in parts) > 100
    score, parts = kpis.risk_score_breakdown(False, True, "High", True, False, 4)
    assert score == 30 + 25 + 10 + 5
    assert [name for name, _ in parts] == ["PEP", "High risk tier", "Address unverified", "1 unverified document(s)"]


def test_risk_score_zero_for_clean_customer() -> None:
    assert kpis.risk_score_breakdown(False, False, "Low", True, True, 5) == (0, [])
