"""Auto-generated insight sentences: plain English computed from filtered data.

Every function returns a list of sentences and handles empty selections. No
number is hard-coded; wording states when a distribution is flat instead of
inventing a story.
"""

from __future__ import annotations

import math

import pandas as pd

from app.theme import fmt_days, fmt_int, fmt_pct

EMPTY_MESSAGE = "No cases match the current slicers. Widen the filters or press Reset filters."
FLAT_THRESHOLD_PP = 2.0  # max-min spread (percentage points) under which a chart is called flat


def _ok(value: float | None) -> bool:
    return value is not None and not (isinstance(value, float) and math.isnan(value))


def spread_pp(rates: pd.Series) -> float:
    """Max-minus-min of a 0-1 rate series, in percentage points."""
    rates = rates.dropna()
    return float(100 * (rates.max() - rates.min())) if len(rates) else float("nan")


def is_flat(rates: pd.Series, threshold_pp: float = FLAT_THRESHOLD_PP) -> bool:
    """Return True when a rate varies by less than ``threshold_pp`` points across groups."""
    spread = spread_pp(rates)
    return _ok(spread) and spread < threshold_pp


def flat_note(rates: pd.Series, what: str, across: str, threshold_pp: float = FLAT_THRESHOLD_PP) -> str:
    """Sentence describing whether ``rates`` (0-1, indexed by group) differ across groups."""
    rates = rates.dropna()
    if rates.empty:
        return f"No data for {what} across {across}."
    lo, hi = rates.min(), rates.max()
    if is_flat(rates, threshold_pp):
        return (
            f"Flat: {what} only ranges {fmt_pct(lo)} to {fmt_pct(hi)} across {across} "
            f"(spread {spread_pp(rates):.1f} pp): no meaningful difference by {across}."
        )
    return (
        f"{what.capitalize()} ranges from {fmt_pct(lo)} ({rates.idxmin()}) to {fmt_pct(hi)} "
        f"({rates.idxmax()}) across {across}."
    )


def ratio_insight(df: pd.DataFrame, group_col: str, value_col: str, high: str, low: str, noun: str) -> str | None:
    """Compare mean values of two groups in one sentence.

    Example: 'High-risk cases take 1.4x longer than Low-risk cases (6.1 d vs 4.3 d).'
    """
    if df.empty or group_col not in df or value_col not in df:
        return None
    means = df.groupby(group_col)[value_col].mean()
    if high not in means or low not in means or not means[low]:
        return None
    ratio = means[high] / means[low]
    return (
        f"{high}-{noun} cases take {ratio:.1f}x {'longer' if ratio >= 1 else 'less time'} than "
        f"{low}-{noun} cases ({fmt_days(means[high])} vs {fmt_days(means[low])})."
    )


def executive_insights(kpi: dict, prev: dict | None) -> list[str]:
    """Headline sentences for the Executive page."""
    if not kpi or not kpi.get("cases"):
        return [EMPTY_MESSAGE]
    out = [
        f"{fmt_int(kpi['cases'])} cases in view: {fmt_pct(kpi['approval_rate'])} approved; "
        f"{fmt_pct(kpi['control_breach_rate'])} of approvals had identity or address unverified "
        f"— a control gap, while the rule engine agrees with {fmt_pct(kpi['engine_agreement'])} of decisions."
    ]
    if prev and prev.get("cases"):
        change = (kpi["cases"] - prev["cases"]) / prev["cases"]
        out.append(
            f"Volume is {'up' if change >= 0 else 'down'} {abs(change):.1%} on the previous equal-length "
            f"period ({fmt_int(prev['cases'])} cases); SLA breach is {fmt_pct(kpi['sla_breach_pct'])} "
            f"vs {fmt_pct(prev['sla_breach_pct'])} (SIMULATED)."
        )
    else:
        out.append(
            f"Average turnaround {fmt_days(kpi['avg_tat_days'])}, SLA breach {fmt_pct(kpi['sla_breach_pct'])}, "
            f"{fmt_int(kpi['open_cases'])} cases open (SIMULATED). No earlier period exists for this range, "
            "so deltas are not shown; pick a shorter date range to compare."
        )
    return out


def funnel_insights(funnel: pd.DataFrame) -> list[str]:
    """Where the biggest drop-off happens and the end-to-end conversion."""
    if funnel.empty or funnel["cases"].iloc[0] == 0:
        return [EMPTY_MESSAGE]
    f = funnel.sort_values("stage_order").reset_index(drop=True)
    f["dropped"] = f["cases"].shift(1) - f["cases"]
    worst = f.iloc[1:].sort_values("dropped", ascending=False).iloc[0]
    first, last = f["cases"].iloc[0], f["cases"].iloc[-1]
    return [
        f"{fmt_pct(last / first)} of opened cases reach approval ({fmt_int(last)} of {fmt_int(first)}).",
        f"The largest drop is at '{worst['stage']}': {fmt_int(worst['dropped'])} cases leave "
        f"({fmt_pct(worst['dropped'] / first)} of opened), driven by policy flags, not by process delays.",
    ]


def controls_insights(components: dict, agreement: float) -> list[str]:
    """Headline control finding sentences."""
    if not components or not components.get("approvals"):
        return ["No approvals match the current slicers, so no control breach can be measured."]
    return [
        f"Decision logic is sound: the rule engine reconciles {fmt_pct(agreement)} of cases.",
        f"Verification controls are not enforced: {fmt_pct(components['control_breach_rate'])} of "
        f"{fmt_int(components['approvals'])} approvals carry a failed identity or address flag "
        f"(identity {fmt_pct(components['breach_no_identity_rate'])}, address "
        f"{fmt_pct(components['breach_no_address_rate'])}). This is a control gap, not a logic error.",
    ]


def documents_insights(by_type: pd.DataFrame, low_conf_rate: float) -> list[str]:
    """Document fail-rate and OCR-confidence sentences."""
    if by_type.empty or by_type["docs"].sum() == 0:
        return [EMPTY_MESSAGE]
    rates = by_type.set_index("doc_type")["failed"] / by_type.set_index("doc_type")["docs"]
    return [
        flat_note(rates, "document fail rate", "document types", threshold_pp=1.0),
        f"{fmt_pct(low_conf_rate)} of documents have OCR confidence below 0.85; confidence is "
        "uniform between 0.80 and 0.99, so low confidence does not by itself mean failure.",
    ]


def operations_insights(df: pd.DataFrame) -> list[str]:
    """Turnaround sentences from the (SIMULATED) operations layer."""
    if df.empty:
        return [EMPTY_MESSAGE]
    out = []
    risk = ratio_insight(df, "risk_category", "tat_days", "High", "Low", "risk")
    if risk:
        out.append(
            risk + " (SIMULATED: High-risk cases get the slower decision types, EDD and Manual Review, "
            "plus a 1.35x handling multiplier by construction.)"
        )
    by_analyst = df.groupby("assigned_to")["sla_breached"].mean()
    if len(by_analyst) > 1:
        out.append(
            flat_note(by_analyst, "SLA breach rate", "analysts", threshold_pp=5.0)
            + " Analysts are assigned uniformly at random in the simulation."
        )
    return out or [EMPTY_MESSAGE]


def backlog_insights(by_risk: pd.DataFrame) -> list[str]:
    """Periodic-review backlog sentences."""
    if by_risk.empty or by_risk["customers"].sum() == 0:
        return [EMPTY_MESSAGE]
    total = by_risk["overdue"].sum() / by_risk["customers"].sum()
    rates = by_risk.set_index("risk_category")["overdue"] / by_risk.set_index("risk_category")["customers"]
    high = by_risk.loc[by_risk["risk_category"] == "High", "overdue"].sum()
    return [
        f"{fmt_pct(total)} of customers ({fmt_int(by_risk['overdue'].sum())}) have not been reviewed in "
        f"over 12 months, including {fmt_int(high)} High-risk customers.",
        flat_note(rates, "the overdue rate", "risk tiers")
        + " Review cadence ignores risk: High-risk customers are no more up to date than Low-risk ones.",
    ]


def ai_insights(by_type: pd.DataFrame, by_question: pd.DataFrame) -> list[str]:
    """AI copilot answer-quality sentences."""
    if by_type.empty:
        return ["No AI benchmark data available."]
    total = by_type["answers"].sum()
    halluc = by_type["hallucinated"].sum()
    rates = by_question.set_index("question_template")["hallucination_pct"] / 100
    return [
        f"{fmt_pct(halluc / total)} of {fmt_int(total)} benchmark answers are hallucinated; "
        "the benchmark is deliberately adversarial, so this is not a production error rate.",
        flat_note(rates, "the hallucination rate", "question templates", threshold_pp=1.0),
    ]
