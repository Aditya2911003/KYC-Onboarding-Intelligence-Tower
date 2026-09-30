"""Page 2 - Funnel and decisions (Q2: where do customers drop out and why?)."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app import components as ui
from app import data, insights
from app.theme import DECISION_COLORS, DECISION_ORDER, RISK_COLORS, RISK_ORDER, TEAL, fmt_int, fmt_pct

filters = ui.page_header("Funnel and decisions", "Q2 · Where do customers drop out of the funnel, and why?")
where, params = data.where_clause(filters)

STAGES_SQL = f"""
    SELECT
        COUNT(*)                                                                   AS opened,
        COUNT(*) FILTER (WHERE NOT is_sanctioned)                                  AS passed_sanctions,
        COUNT(*) FILTER (WHERE NOT is_sanctioned AND NOT is_pep)                   AS passed_pep,
        COUNT(*) FILTER (WHERE NOT is_sanctioned AND NOT is_pep AND risk_category <> 'High') AS passed_risk,
        COUNT(*) FILTER (WHERE decision = 'Approve')                               AS approved
    FROM mart_case_detail {where}
"""
row = data.query(STAGES_SQL, params).iloc[0]
labels = ["Opened", "Passed sanctions", "Passed PEP", "Passed risk", "Approved"]
values = [int(row[c]) for c in ("opened", "passed_sanctions", "passed_pep", "passed_risk", "approved")]
funnel = pd.DataFrame({"stage_order": range(1, 6), "stage": labels, "cases": values})
ui.insight_strip(insights.funnel_insights(funnel))

left, right = st.columns([1.3, 1])
with left:
    with ui.tile("funnel", "Onboarding funnel", "Each stage keeps only cases that passed every earlier policy gate"):
        drop_text = ["100% of opened"] + [
            (
                f"{fmt_pct(v / values[0]) if values[0] else '—'} of opened · "
                f"−{fmt_pct((values[i] - v) / values[i]) if values[i] else '—'} step drop"
            )
            for i, v in enumerate(values[1:])
        ]
        fig = go.Figure(
            go.Funnel(
                y=labels,
                x=values,
                text=[f"{fmt_int(v)}<br>{t}" for v, t in zip(values, drop_text, strict=True)],
                textinfo="text",
                marker=dict(color=[TEAL, "#2FC5B8", "#5ED1C8", "#8DDED8", "#374649"]),
                hovertemplate="%{y}: %{x:,} cases<extra></extra>",
                connector=dict(line=dict(color="#D9D9D9")),
            )
        )
        ui.chart(fig, "funnel_chart", height=340)
with right:
    with ui.tile("reasons", "Decision reasons", "Labelled DecisionReason · click a bar to cross-filter by decision"):
        reasons = data.query(
            f"SELECT decision, decision_reason, COUNT(*) AS cases FROM mart_case_detail {where} "
            "GROUP BY decision, decision_reason ORDER BY cases",
            params,
        )
        fig = go.Figure(
            go.Bar(
                x=reasons["cases"],
                y=reasons["decision_reason"] + " → " + reasons["decision"],
                orientation="h",
                marker_color=[DECISION_COLORS[d] for d in reasons["decision"]],
                customdata=reasons[["decision"]].to_numpy(),
                text=[fmt_int(v) for v in reasons["cases"]],
                textposition="auto",
                hovertemplate="%{y}<br>%{x:,} cases<extra></extra>",
            )
        )
        fig.update_layout(yaxis=dict(tickfont=dict(size=11)))
        ui.xf_chart(fig, "reasons", "decision", height=340)

left, right = st.columns([1.3, 1])
with left:
    with ui.tile(
        "sankey",
        "Risk tier → decision (Sankey)",
        "High-risk non-PEP cases split about 50/50 between EDD and Manual Review; no field explains which",
    ):
        flows = data.query(
            f"SELECT risk_category, decision, COUNT(*) AS cases FROM mart_case_detail {where} GROUP BY ALL", params
        )
        risks = [r for r in RISK_ORDER if r in set(flows["risk_category"])]
        decisions = [d for d in DECISION_ORDER if d in set(flows["decision"])]
        nodes = [f"{r} risk" for r in risks] + decisions
        index = {n: i for i, n in enumerate(nodes)}
        fig = go.Figure(
            go.Sankey(
                node=dict(
                    label=nodes,
                    pad=14,
                    thickness=16,
                    color=[RISK_COLORS[r] for r in risks] + [DECISION_COLORS[d] for d in decisions],
                ),
                link=dict(
                    source=[index[f"{r} risk"] for r in flows["risk_category"]],
                    target=[index[d] for d in flows["decision"]],
                    value=flows["cases"],
                    color="rgba(95,107,109,0.25)",
                    hovertemplate="%{source.label} → %{target.label}: %{value:,} cases<extra></extra>",
                ),
            )
        )
        ui.chart(fig, "sankey_chart", height=340)
with right:
    with ui.tile("dropoff_country", "Drop-off by country", "Share of each country's opened cases lost at each gate"):
        by_country = data.query(
            f"""
            SELECT country,
                   COUNT(*) AS opened,
                   ROUND(100.0 * COUNT(*) FILTER (WHERE is_sanctioned) / COUNT(*), 1) AS "sanctions drop %",
                   ROUND(100.0 * COUNT(*) FILTER (WHERE NOT is_sanctioned AND is_pep) / COUNT(*), 1) AS "PEP drop %",
                   ROUND(100.0 * COUNT(*) FILTER (WHERE NOT is_sanctioned AND NOT is_pep
                                                   AND risk_category = 'High') / COUNT(*), 1) AS "risk drop %",
                   ROUND(100.0 * COUNT(*) FILTER (WHERE decision = 'Pending Documents') / COUNT(*), 1)
                       AS "docs drop %",
                   ROUND(100.0 * COUNT(*) FILTER (WHERE decision = 'Approve') / COUNT(*), 1) AS "approved %"
            FROM mart_case_detail {where}
            GROUP BY country ORDER BY country
            """,
            params,
        )
        ui.table(
            by_country,
            hide_index=True,
            width="stretch",
            height=240,
            column_config={"opened": st.column_config.NumberColumn(format="localized")},
        )
        if len(by_country) > 1:
            st.caption(
                insights.flat_note(
                    by_country.set_index("country")["approved %"] / 100, "the approval rate", "countries"
                )
            )

with ui.tile(
    "funnel_proof",
    "Warehouse proof: sql/04_analysis.sql query (1), all cases",
    "Conditional aggregation (FILTER) → UNPIVOT → FIRST_VALUE / LAG; validated against mart_funnel at build",
):
    proof = data.query(
        "SELECT stage, cases, dropped, drop_off_pct, pct_of_opened FROM analysis_funnel ORDER BY stage_order"
    )
    ui.table(
        proof,
        hide_index=True,
        width="stretch",
        column_config={
            "cases": st.column_config.NumberColumn(format="localized"),
            "dropped": st.column_config.NumberColumn(format="localized"),
        },
    )
    gate_names = {
        "passed_sanctions": "sanctions (reject)",
        "passed_pep": "PEP (to EDD)",
        "passed_risk": "High-risk escalation (EDD/Manual)",
        "approved": "documents (pending)",
    }
    ranked = proof.dropna(subset=["dropped"]).sort_values("dropped", ascending=False)
    order = ", then ".join(f"{gate_names.get(r.stage, r.stage)} {fmt_int(r.dropped)}" for r in ranked.itertuples())
    st.markdown(
        f"**Q2 answer:** customers leave at policy gates, not through process friction. Largest to smallest "
        f"drop: {order}. The labelled DecisionReason always matches the gate that removed the case."
    )
