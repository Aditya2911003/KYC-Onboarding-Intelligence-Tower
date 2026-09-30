"""Page 13 - About: problem statement, answers to Q1-Q6, author card, stack."""

from __future__ import annotations

import streamlit as st

from app import components as ui
from app import data
from app.state import Filters
from app.theme import fmt_days, fmt_int, fmt_pct

AUTHOR = "AUTHOR_NAME"
GITHUB = "GITHUB_USERNAME"
LINKEDIN = "LINKEDIN_URL"
REPO_URL = f"https://github.com/{GITHUB}/kyc-onboarding-control-tower"

ui.page_header("About", "Client Onboarding & KYC Operations Dashboard: from onboarding speed to control assurance")
st.caption("Slicers do not apply here: the answers below are computed on all cases.")

start, end = data.date_bounds()
k = ui.kpi_snapshot(Filters(start, end))
funnel = data.query("SELECT stage, cases, dropped FROM analysis_funnel ORDER BY stage_order")
worst_gate = funnel.dropna(subset=["dropped"]).sort_values("dropped", ascending=False).iloc[0]
docs = data.query(
    "SELECT SUM(failed_docs) / SUM(docs) AS fail, SUM(low_conf_docs) / SUM(docs) AS low FROM mart_doc_quality"
).iloc[0]
backlog = data.query(
    "SELECT SUM(overdue) / SUM(customers) AS pct, SUM(overdue) FILTER (WHERE risk_category = 'High') "
    "AS high FROM mart_review_backlog"
).iloc[0]
ai = data.query("SELECT SUM(hallucinated) / SUM(answers) AS rate FROM mart_ai_by_type").iloc[0]
ui.insight_strip(
    [
        f"Built over {fmt_int(k['cases'])} synthetic onboarding cases with a tested DuckDB warehouse, "
        f"{len(data.available_marts())} Parquet marts and 13 report pages.",
        "Operational timing fields are SIMULATED (seed 42) and marked wherever they appear.",
    ]
)

with ui.tile("problem", "Problem statement", "Verbatim from the project brief"):
    st.markdown(
        "**Title:** Client Onboarding & KYC Operations Dashboard: from onboarding speed to control assurance\n\n"
        "**Problem.** A retail bank must verify every new client (identity, address, sanctions, politically exposed "
        "person status, risk tier and supporting documents) before opening an account. Operations leaders track how "
        "*fast* cases move; compliance leaders need to know whether decisions are *right*, follow policy, and whether "
        "the verification controls were actually passed. Today these views live in separate reports, so nobody can "
        "answer the questions that matter to both: where do applications stall, are decisions consistent with the AML "
        "rules, are customers being approved despite failed verification, is document verification reliable, and can "
        "analysts trust the AI assistant that drafts case answers?\n\n"
        "**Solution.** One interactive dashboard over 100,000 synthetic onboarding cases that joins **operational "
        "efficiency** (funnel, turnaround, SLA, workload) with **control assurance** (policy reconciliation, control "
        "breaches, document quality, periodic-review backlog, AI-answer quality), backed by a tested SQL warehouse "
        "and a "
        "reproducible pipeline."
    )

with ui.tile("answers", "The six business questions, answered from the data", "Each has a page, a KPI and a headline"):
    rows = [
        (
            "Q1",
            "Is onboarding healthy: volume, approval rate, turnaround, SLA?",
            "Executive",
            f"{fmt_int(k['cases'])} cases, {fmt_pct(k['approval_rate'])} approved, average turnaround "
            f"{fmt_days(k['avg_tat_days'])} and SLA breach {fmt_pct(k['sla_breach_pct'])} (both SIMULATED).",
        ),
        (
            "Q2",
            "Where do customers drop out of the funnel and why?",
            "Funnel",
            f"At policy gates; the largest drop is before '{worst_gate['stage']}' "
            f"({fmt_int(worst_gate['dropped'])} cases).",
        ),
        (
            "Q3",
            "Do decisions follow policy? Can we prove it for 100% of cases?",
            "Controls",
            f"Yes: the recovered rule engine reproduces {fmt_pct(k['engine_agreement'])} of labelled decisions.",
        ),
        (
            "Q4",
            "Are customers approved despite a failed identity or address check?",
            "Controls",
            f"Yes: {fmt_pct(k['control_breach_rate'])} of approvals — a control gap, not a logic error.",
        ),
        (
            "Q5",
            "Is document verification and OCR reliable, and is the periodic-review backlog under control?",
            "Documents, Review backlog",
            f"{fmt_pct(docs['fail'])} of documents fail verification and {fmt_pct(docs['low'])} have low OCR "
            "confidence; "
            f"{fmt_pct(backlog['pct'])} of customers are overdue for review ({fmt_int(backlog['high'])} High-risk).",
        ),
        (
            "Q6",
            "Can analysts trust the AI copilot's answers?",
            "AI Copilot",
            f"Not on this benchmark: {fmt_pct(ai['rate'])} of answers are hallucinated and the answers are templated.",
        ),
    ]
    for q, question, page, answer in rows:
        st.markdown(f"**{q}. {question}** · *{page} page*  \n{answer}")

left, right = st.columns([1, 1])
with left:
    with ui.tile("author", "Author", "Portfolio project"):
        st.markdown(
            f'<div class="author-card"><b>{AUTHOR}</b><br>GitHub: <a href="https://github.com/{GITHUB}">{GITHUB}</a>'
            f'<br>LinkedIn: <a href="{LINKEDIN}">{LINKEDIN}</a>'
            f'<br>Repository: <a href="{REPO_URL}">{REPO_URL}</a></div>',
            unsafe_allow_html=True,
        )
with right:
    with ui.tile("stack", "Tech stack", "Pinned in requirements.txt"):
        st.markdown(
            "- **Warehouse:** Python 3.11, DuckDB, SQL (CTEs, window functions, FILTER, UNPIVOT, QUALIFY, "
            "GROUPING SETS, ANTI JOIN)\n"
            "- **Pipeline:** pandas, NumPy, PyArrow · zstd Parquet marts\n"
            "- **App:** Streamlit multipage (st.navigation, st.dialog, st.fragment, cross-filter), Plotly\n"
            "- **Quality:** pytest (unit, data-quality and Streamlit AppTest smoke tests), ruff, GitHub Actions CI\n"
            "- **ML (dev only):** scikit-learn HistGradientBoosting, permutation importance, SHAP"
        )
ui.footnote("All data is synthetic. Names and IDs are generated; no real customer is represented.")
