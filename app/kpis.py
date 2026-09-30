"""KPI definitions (section 8): implemented once, reused by the dashboard and the tests.

Every KPI exists as a pure function over a pandas DataFrame and, where the
dashboard aggregates in DuckDB, as a SQL snippet in ``KPI_SQL``. The tests assert
that both forms agree on a hand-built fixture. ``KPI_DEFINITIONS`` is printed on
the Data quality page and mirrored in ``docs/kpi_definitions.md``.

This module is pure Python (no Streamlit import) so it is importable anywhere.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

AS_OF = date(2026, 6, 30)
REVIEW_OVERDUE_DAYS = 365
LOW_CONFIDENCE_THRESHOLD = 0.85

KPI_DEFINITIONS: dict[str, str] = {
    "Cases": "Count of case_id.",
    "Approval rate": "Approve / Cases. EDD rate, Reject rate, Pending rate analogous.",
    "Avg turnaround (SIMULATED)": "Mean tat_days; p90 turnaround = 90th percentile.",
    "SLA breach %": "Share of cases with tat_days greater than sla_days. Open cases = count where is_open.",
    "Control-breach rate": (
        "Approvals with identity_verified = No OR address_verified = No, divided by approvals. "
        "Also report each component separately."
    ),
    "Rule-engine agreement": "Share of cases where engine_agrees; a value below 100% raises a red alert banner.",
    "Review overdue %": "Share of customers whose last_updated is more than 365 days before 2026-06-30.",
    "Document fail rate": "Unverified documents / documents; low-confidence rate = Confidence below 0.85.",
    "Hallucination rate": "Hallucinated answers / all answers, by type, severity and question template.",
    "Period-over-period delta": (
        "(Current minus previous equal-length period) / previous, previous period ending the day "
        "before the selected range starts."
    ),
}

# SQL snippets over mart_case_detail; each returns one value per group.
KPI_SQL: dict[str, str] = {
    "cases": "COUNT(*)",
    "approval_rate": "AVG(CASE WHEN decision = 'Approve' THEN 1.0 ELSE 0.0 END)",
    "edd_rate": "AVG(CASE WHEN decision = 'Enhanced Due Diligence' THEN 1.0 ELSE 0.0 END)",
    "reject_rate": "AVG(CASE WHEN decision = 'Reject' THEN 1.0 ELSE 0.0 END)",
    "pending_rate": "AVG(CASE WHEN decision = 'Pending Documents' THEN 1.0 ELSE 0.0 END)",
    "avg_tat_days": "AVG(tat_days)",
    "p90_tat_days": "quantile_cont(tat_days, 0.9)",
    "sla_breach_pct": "AVG(CASE WHEN tat_days > sla_days THEN 1.0 ELSE 0.0 END)",
    "open_cases": "COUNT(*) FILTER (WHERE is_open)",
    "approvals": "COUNT(*) FILTER (WHERE decision = 'Approve')",
    "control_breach_rate": (
        "COUNT(*) FILTER (WHERE decision = 'Approve' AND (NOT identity_verified OR NOT address_verified))"
        " / NULLIF(COUNT(*) FILTER (WHERE decision = 'Approve'), 0)"
    ),
    "breach_no_identity_rate": (
        "COUNT(*) FILTER (WHERE decision = 'Approve' AND NOT identity_verified)"
        " / NULLIF(COUNT(*) FILTER (WHERE decision = 'Approve'), 0)"
    ),
    "breach_no_address_rate": (
        "COUNT(*) FILTER (WHERE decision = 'Approve' AND NOT address_verified)"
        " / NULLIF(COUNT(*) FILTER (WHERE decision = 'Approve'), 0)"
    ),
    "breach_missing_doc_rate": (
        "COUNT(*) FILTER (WHERE decision = 'Approve' AND verified_docs < 5)"
        " / NULLIF(COUNT(*) FILTER (WHERE decision = 'Approve'), 0)"
    ),
    "engine_agreement": "AVG(CASE WHEN engine_agrees THEN 1.0 ELSE 0.0 END)",
    "review_overdue_pct": "AVG(CASE WHEN review_overdue THEN 1.0 ELSE 0.0 END)",
}

# Which direction is good for each KPI (drives delta colour): +1 up is good, -1 down is good.
KPI_POLARITY: dict[str, int] = {
    "cases": 1,
    "approval_rate": 1,
    "avg_tat_days": -1,
    "p90_tat_days": -1,
    "sla_breach_pct": -1,
    "open_cases": -1,
    "control_breach_rate": -1,
    "engine_agreement": 1,
    "review_overdue_pct": -1,
}


def _safe_div(num: float, den: float) -> float:
    return float(num) / float(den) if den else float("nan")


def cases(df: pd.DataFrame) -> int:
    """Count of cases."""
    return len(df)


def decision_rate(df: pd.DataFrame, decision: str) -> float:
    """Share of cases with the given labelled decision."""
    return _safe_div((df["decision"] == decision).sum(), len(df))


def approval_rate(df: pd.DataFrame) -> float:
    """Approve / Cases."""
    return decision_rate(df, "Approve")


def avg_turnaround(df: pd.DataFrame) -> float:
    """Mean simulated turnaround in days (SIMULATED)."""
    return float(df["tat_days"].mean()) if len(df) else float("nan")


def p90_turnaround(df: pd.DataFrame) -> float:
    """90th percentile of simulated turnaround (linear interpolation, like quantile_cont)."""
    return float(df["tat_days"].quantile(0.9)) if len(df) else float("nan")


def sla_breach_pct(df: pd.DataFrame) -> float:
    """Share of cases with tat_days > sla_days (SIMULATED)."""
    return _safe_div((df["tat_days"] > df["sla_days"]).sum(), len(df))


def open_cases(df: pd.DataFrame) -> int:
    """Count of cases still open at AS_OF (SIMULATED)."""
    return int(df["is_open"].sum())


def control_breach_components(df: pd.DataFrame) -> dict[str, float]:
    """Control-breach rate and each component, all as share of approvals."""
    approved = df[df["decision"] == "Approve"]
    n = len(approved)
    no_id = ~approved["identity_verified"].astype(bool)
    no_addr = ~approved["address_verified"].astype(bool)
    return {
        "approvals": float(n),
        "control_breach_rate": _safe_div((no_id | no_addr).sum(), n),
        "breach_no_identity_rate": _safe_div(no_id.sum(), n),
        "breach_no_address_rate": _safe_div(no_addr.sum(), n),
        "breach_missing_doc_rate": _safe_div((approved["verified_docs"] < 5).sum(), n),
    }


def control_breach_rate(df: pd.DataFrame) -> float:
    """Approvals with identity OR address unverified / approvals."""
    return control_breach_components(df)["control_breach_rate"]


def rule_engine_agreement(df: pd.DataFrame) -> float:
    """Share of cases where the rule engine agrees with the labelled decision."""
    return _safe_div(df["engine_agrees"].astype(bool).sum(), len(df))


def review_overdue_pct(df: pd.DataFrame, as_of: date = AS_OF) -> float:
    """Share of customers whose last review is more than 365 days before AS_OF."""
    if not len(df):
        return float("nan")
    last = pd.to_datetime(df["last_updated"])
    overdue = (pd.Timestamp(as_of) - last).dt.days > REVIEW_OVERDUE_DAYS
    return _safe_div(overdue.sum(), len(df))


def document_fail_rate(docs: pd.DataFrame) -> float:
    """Unverified documents / documents."""
    return _safe_div((~docs["verified"].astype(bool)).sum(), len(docs))


def low_confidence_rate(docs: pd.DataFrame) -> float:
    """Share of documents with OCR confidence below 0.85."""
    return _safe_div((docs["confidence"] < LOW_CONFIDENCE_THRESHOLD).sum(), len(docs))


def hallucination_rate(hallucinated: float, answers: float) -> float:
    """Hallucinated answers / all answers."""
    return _safe_div(hallucinated, answers)


def period_delta(current: float, previous: float) -> float | None:
    """Return (current - previous) / previous, or None when the previous period is empty or zero."""
    if previous is None or current is None or pd.isna(previous) or pd.isna(current) or previous == 0:
        return None
    return (float(current) - float(previous)) / float(previous)


def previous_period(start: date, end: date) -> tuple[date, date]:
    """Previous equal-length period ending the day before ``start``."""
    length = end - start
    prev_end = start - timedelta(days=1)
    return prev_end - length, prev_end


# ---------------------------------------------------------------------------
# Rule engine (same precedence as sql/02_model.sql) and the what-if simulator.
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class EngineResult:
    """Outcome of the recovered decision policy for one case."""

    decision: str
    rule: str
    explanation: str


def engine_decision(is_sanctioned: bool, is_pep: bool, risk_category: str, verified_docs: int) -> EngineResult:
    """Apply the recovered policy in precedence order and explain which rule fired."""
    if is_sanctioned:
        return EngineResult("Reject", "R1 Sanctions screening", "Customer is on a sanctions list: reject.")
    if is_pep:
        return EngineResult(
            "Enhanced Due Diligence",
            "R2 PEP enhanced due diligence",
            "Customer is a politically exposed person: enhanced due diligence.",
        )
    if risk_category == "High":
        return EngineResult(
            "Escalate (EDD/Manual)",
            "R3 High-risk escalation",
            "High risk tier: escalate to EDD or Manual Review (the data splits about 50/50 "
            "between the two and no field explains which).",
        )
    if verified_docs < 4:
        return EngineResult(
            "Pending Documents",
            "R4 Document sufficiency",
            f"Only {verified_docs} of 5 documents verified (policy needs at least 4): pending documents.",
        )
    return EngineResult(
        "Approve", "R5 Standard approval", "No sanction, PEP or high-risk flag and ≥4 verified documents."
    )


def engine_agrees(engine: str, decision: str) -> bool:
    """Return True when the engine outcome matches the label (Escalate matches EDD or Manual)."""
    if engine == "Escalate (EDD/Manual)":
        return decision in ("Enhanced Due Diligence", "Manual Review")
    return engine == decision


# Illustrative additive risk score (NOT a calibrated model).
RISK_SCORE_WEIGHTS: dict[str, int] = {
    "Sanctioned": 100,
    "PEP": 30,
    "High risk tier": 25,
    "Identity unverified": 10,
    "Address unverified": 10,
    "Per unverified document": 5,
}


def risk_score_breakdown(
    is_sanctioned: bool,
    is_pep: bool,
    risk_category: str,
    identity_verified: bool,
    address_verified: bool,
    verified_docs: int,
    total_docs: int = 5,
) -> tuple[int, list[tuple[str, int]]]:
    """Return the capped 0-100 score and its per-component contributions.

    Weights: sanction 100, PEP 30, High risk 25, identity unverified 10,
    address unverified 10, each unverified document 5; capped at 100.
    """
    parts: list[tuple[str, int]] = []
    if is_sanctioned:
        parts.append(("Sanctioned", RISK_SCORE_WEIGHTS["Sanctioned"]))
    if is_pep:
        parts.append(("PEP", RISK_SCORE_WEIGHTS["PEP"]))
    if risk_category == "High":
        parts.append(("High risk tier", RISK_SCORE_WEIGHTS["High risk tier"]))
    if not identity_verified:
        parts.append(("Identity unverified", RISK_SCORE_WEIGHTS["Identity unverified"]))
    if not address_verified:
        parts.append(("Address unverified", RISK_SCORE_WEIGHTS["Address unverified"]))
    unverified = max(total_docs - int(verified_docs), 0)
    if unverified:
        parts.append(
            (f"{unverified} unverified document(s)", unverified * RISK_SCORE_WEIGHTS["Per unverified document"])
        )
    return min(sum(p for _, p in parts), 100), parts
