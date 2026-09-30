"""Page 7 - Periodic review backlog (Q5b: is the periodic-review backlog under control?)."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from app import components as ui
from app import data, insights
from app.theme import BAD, CHARCOAL, GOOD, RISK_ORDER, TEAL, YELLOW, fmt_int, fmt_pct

filters = ui.page_header(
    "Periodic review backlog",
    "Q5 · Is the periodic-review backlog under control? (overdue = last review > 365 days before 2026-06-30)",
)
where, params = data.where_clause(filters)
by_risk = data.query(
    f"""
    SELECT risk_category, COUNT(*) AS customers, COUNT(*) FILTER (WHERE review_overdue) AS overdue
    FROM mart_case_detail {where} GROUP BY risk_category
    """,
    params,
)
ui.insight_strip(insights.backlog_insights(by_risk))
customers = int(by_risk["customers"].sum()) if not by_risk.empty else 0
overdue = int(by_risk["overdue"].sum()) if not by_risk.empty else 0
overdue_pct = overdue / customers if customers else float("nan")
high_overdue = int(by_risk.loc[by_risk["risk_category"] == "High", "overdue"].sum()) if customers else 0

cols = st.columns(4)
with cols[0]:
    ui.kpi_card("rev_customers", "Customers", fmt_int(customers), foot="one case per customer")
with cols[1]:
    ui.kpi_card("rev_overdue", "Review overdue %", fmt_pct(overdue_pct), foot=f"{fmt_int(overdue)} customers")
with cols[2]:
    ui.kpi_card("rev_high", "High-risk overdue", fmt_int(high_overdue), foot="highest-priority reviews")
with cols[3]:
    ui.kpi_card(
        "rev_recent",
        "Reviewed in last 12 months",
        fmt_pct(1 - overdue_pct) if customers else "—",
        foot="complement of overdue %",
    )

left, right = st.columns([1, 1.3])
with left:
    with ui.tile("gauge", "Reviewed in last 12 months", "Gauge against an illustrative 90% policy target"):
        value = (1 - overdue_pct) * 100 if customers else 0
        fig = go.Figure(
            go.Indicator(
                mode="gauge+number",
                value=value,
                number=dict(suffix="%", valueformat=".1f"),
                gauge=dict(
                    axis=dict(range=[0, 100], ticksuffix="%"),
                    bar=dict(color=CHARCOAL),
                    steps=[
                        dict(range=[0, 70], color="#F9D5D4"),
                        dict(range=[70, 90], color="#FBEFC2"),
                        dict(range=[90, 100], color="#CDEFD0"),
                    ],
                    threshold=dict(line=dict(color=GOOD, width=4), value=90),
                ),
            )
        )
        ui.chart(fig, "gauge_chart", height=280)
        ui.footnote("The 90% target is illustrative (not in the source data); bands: red < 70%, amber 70-90%.")
with right:
    with ui.tile("overdue_age", "Overdue % by risk tier and age band", "Share of customers overdue for review"):
        grid = data.query(
            f"""
            SELECT risk_category, age_band, COUNT(*) AS customers, AVG(review_overdue::INT) AS overdue_rate
            FROM mart_case_detail {where} GROUP BY ALL
            """,
            params,
        )
        fig = go.Figure()
        for risk, color in zip(RISK_ORDER, (TEAL, YELLOW, BAD), strict=True):
            part = grid[grid["risk_category"] == risk].sort_values("age_band")
            fig.add_trace(
                go.Bar(
                    x=part["age_band"],
                    y=part["overdue_rate"],
                    name=risk,
                    marker_color=color,
                    customdata=part["customers"],
                    hovertemplate=risk + " · %{x}: %{y:.1%} of %{customdata:,}<extra></extra>",
                )
            )
        flat = insights.is_flat(grid["overdue_rate"], threshold_pp=4.0)
        fig.update_layout(barmode="group", yaxis=dict(tickformat=".0%", range=[0, 0.8]))
        ui.flat_badge("FLAT: overdue share is the same for every tier and age band", flat)
        ui.chart(fig, "overdue_age_chart", height=280)

with ui.tile("overdue_high", "Overdue High-risk customers", "Oldest reviews first · drill through to Customer 360"):
    listing = data.query(
        f"""
        SELECT customer_id, case_id, country, decision, days_since_review, last_updated, is_pep, is_sanctioned
        FROM mart_case_detail {where} AND review_overdue AND risk_category = 'High'
        ORDER BY days_since_review DESC, customer_id LIMIT {data.EXPORT_ROW_CAP}
        """,
        params,
    )
    st.caption(f"{fmt_int(high_overdue)} High-risk customers overdue; first {fmt_int(len(listing))} shown.")
    ui.case_table(listing, "overdue_high", height=300)
    ui.export_button(listing, "synthetic_overdue_high_risk.csv", "Export overdue High-risk list", key="export_overdue")

with ui.tile(
    "backlog_proof",
    "Warehouse proof: sql/04_analysis.sql query (3), all customers",
    "Backlog by risk tier with FILTER aggregates; validated against mart_review_backlog at build",
):
    proof = data.query("SELECT * FROM analysis_review_backlog")
    ui.table(proof, hide_index=True, width="stretch")
    if customers:
        st.markdown(
            f"**Q5 (backlog) answer:** not under control: {fmt_pct(overdue_pct)} of customers in view are overdue "
            f"for periodic review, including {fmt_int(high_overdue)} High-risk customers, and the overdue share "
            "does not fall as risk rises."
            if insights.is_flat(
                by_risk.set_index("risk_category")["overdue"] / by_risk.set_index("risk_category")["customers"]
            )
            else f"**Q5 (backlog) answer:** {fmt_pct(overdue_pct)} of customers in view are overdue for review."
        )
