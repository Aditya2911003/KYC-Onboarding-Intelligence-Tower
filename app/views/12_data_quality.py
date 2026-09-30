"""Page 12 - Data quality and definitions: DQ scorecard, claims check, KPI definitions, issues, lineage."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from app import components as ui
from app import data, kpis
from app.theme import BAD, GOOD, YELLOW, fmt_int

ui.page_header("Data quality and definitions", "Can the numbers be trusted? Every check, definition and lineage step.")
st.caption("Slicers do not apply here: checks run once over the whole warehouse at build time.")

dq = data.query("SELECT * FROM mart_dq_report")
claims = data.query("SELECT * FROM mart_claims_check ORDER BY claim_id")
counts = dq["status"].value_counts()
extract = data.query("SELECT MAX(last_updated) AS d FROM mart_case_detail").iloc[0]["d"]
extract_date = f"{extract:%Y-%m-%d}"


def dq_value(name: str) -> float:
    """Result of one named DQ check (NaN when absent)."""
    hit = dq.loc[dq["check_name"] == name, "result"]
    return float(hit.iloc[0]) if len(hit) else float("nan")


ui.insight_strip(
    [
        f"{fmt_int(counts.get('pass', 0))} checks pass, {fmt_int(counts.get('warn', 0))} warn and "
        f"{fmt_int(counts.get('fail', 0))} fail. Warnings are documented source-data quirks, not pipeline errors.",
        f"{fmt_int(int(claims['matches'].sum()))} of {fmt_int(len(claims))} facts claimed in the project brief were "
        f"reproduced exactly; {fmt_int(int((~claims['matches']).sum()))} differ and are explained below.",
    ]
)

cols = st.columns(3)
for col, status, color in zip(cols, ("pass", "warn", "fail"), (GOOD, YELLOW, BAD), strict=True):
    with col:
        with ui.tile(f"dq_{status}", status.upper(), "data-quality checks"):
            st.markdown(
                f'<div class="big-card"><div class="v" style="color:{color}">'
                f"{fmt_int(counts.get(status, 0))}</div></div>",
                unsafe_allow_html=True,
            )

with ui.tile(
    "dq_table",
    "mart_dq_report scorecard",
    "Row counts, nulls, duplicate keys, referential integrity, consistency, simulation sanity, mart checks",
):
    status_filter = st.segmented_control("Show", ["all", "pass", "warn", "fail"], default="all", key="dq_show")
    shown = dq if status_filter in (None, "all") else dq[dq["status"] == status_filter]
    st.dataframe(
        shown.style.map(
            lambda s: f"color: {GOOD if s == 'pass' else (YELLOW if s == 'warn' else BAD)}; font-weight: 600",
            subset=["status"],
        ),
        hide_index=True,
        width="stretch",
        height=360,
        column_config={"result": st.column_config.NumberColumn(format="localized")},
    )

with ui.tile("claims", "Claimed vs measured", "Every fact in the project brief recomputed from the data"):
    ui.table(
        claims,
        hide_index=True,
        width="stretch",
        height=360,
        column_config={
            "measured": st.column_config.NumberColumn(format="localized"),
            "matches": st.column_config.CheckboxColumn("matches"),
        },
    )
    diffs = claims[~claims["matches"]]
    for row in diffs.itertuples():
        st.markdown(f"- **{row.claim_id} {row.claim}:** claimed {row.claimed}, measured {row.measured:,.0f}.")
    if "C06" in set(diffs["claim_id"]):
        st.caption(
            f"C06: the brief's figure equals the overdue count at the data's extract date ({extract_date}); "
            "at the dashboard's AS_OF (2026-06-30) more profiles cross the 365-day line. The dashboard uses AS_OF."
        )

left, right = st.columns([1, 1])
with left:
    with ui.tile("kpi_defs", "KPI definitions (app/kpis.py)", "Implemented once; the dashboard and tests import them"):
        for name, text in kpis.KPI_DEFINITIONS.items():
            st.markdown(f"- **{name}** = {text}")
with right:
    with ui.tile("issues", "Known data issues and how they are handled", "Full list: docs/known_data_issues.md"):
        st.markdown(
            "- **No timestamps, analysts, channels or SLAs** in the source → a seeded SIMULATED operations layer "
            "(`sim_case_ops`), disclosed wherever used.\n"
            "- **IdentityVerified / AddressVerified are ~50/50 and unrelated to the decision** → reported as the "
            "control-breach finding.\n"
            "- **Country, occupation, income and age carry no signal** → flat charts say so.\n"
            f"- **DocumentID is not unique** ({fmt_int(dq_value('duplicate_document_id_stg_documents'))} surplus rows "
            "reuse another customer's ID) → the document key is (customer_id, doc_type).\n"
            f"- **Age is as of the extract date ({extract_date})**, not AS_OF: "
            f"{fmt_int(dq_value('age_differs_from_dob_at_as_of'))} "
            "customers had a birthday in between → age bands use the source Age.\n"
            "- **Gender does not match names; all names and IDs are synthetic** → names, DOB and document numbers are "
            "never exported to the marts.\n"
            "- **Documents all expire 2027-2036** → OCR confidence and verification failure are used instead "
            "of expiry.\n"
            "- **kyc_guidelines.EffectiveDate is dd-mm-yyyy** → parsed with an explicit format.\n"
            "- **AI answers collapse to 25 templates** → detector scores are ~100% by construction (caveat on page 10)."
        )

with ui.tile("lineage", "Data lineage", "From raw CSV to this page"):
    st.graphviz_chart(
        """
        digraph lineage {
          rankdir=LR; node [shape=box, style="rounded,filled", fillcolor="#FFFFFF", color="#D9D9D9",
                             fontname="Helvetica", fontsize=10];
          raw [label="data/raw/*.csv\\n14 synthetic files\\n(gitignored)", fillcolor="#F3F7F7"];
          stg [label="sql/01_staging.sql\\nstg_* typed tables\\n(OCRText skipped)"];
          sim [label="build_warehouse.py\\nsim_case_ops\\nSIMULATED, seed 42", fillcolor="#EBD9E6"];
          model [label="sql/02_model.sql\\ndim_* / fact_*\\nrule engine + breach flags"];
          marts [label="sql/03_marts.sql\\nmart_*"];
          analysis [label="sql/04_analysis.sql\\nanalysis_*"];
          ai [label="etl/ai_qa_marts.py\\nmart_ai_*, ai_examples"];
          ml [label="ml/decision_model.py\\nmart_ml_results"];
          dq [label="etl/quality_checks.py\\nmart_dq_report\\nmart_claims_check"];
          parquet [label="data/marts/*.parquet\\n(committed, < 25 MB)", fillcolor="#E6F7F5"];
          app [label="Streamlit app\\nDuckDB views + st.cache_data", fillcolor="#374649", fontcolor="#FFFFFF"];
          raw -> stg -> model; stg -> sim -> model; model -> marts; model -> analysis; raw -> ai;
          model -> ml; marts -> dq; analysis -> dq;
          marts -> parquet; analysis -> parquet; ai -> parquet; ml -> parquet; dq -> parquet; parquet -> app;
        }
        """,
        width="stretch",
    )

sizes = data.query("SELECT check_name, result FROM mart_dq_report WHERE check_name = 'marts_total_size_mb'")
if len(sizes):
    fig = go.Figure(
        go.Indicator(
            mode="number",
            value=float(sizes.iloc[0]["result"]),
            number=dict(suffix=" MB"),
            title=dict(text="Committed marts on disk (limit 25 MB)"),
        )
    )
    ui.chart(fig, "size_indicator", height=150)
