"""Page 6 - Operations and SLA (SIMULATED): turnaround, SLA, analyst workload and ageing."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from app import components as ui
from app import data, insights, kpis
from app.theme import BAD, CHARCOAL, TEAL, YELLOW, fmt_days, fmt_int, fmt_pct

filters = ui.page_header(
    "Operations and SLA", "Where does work queue up, and who breaches SLA? (every visual is SIMULATED)", simulated=True
)
st.warning(
    "Every visual on this page is SIMULATED. The source data has no timestamps, analysts, channels or SLAs; "
    "they come from a seeded simulation (seed 42) documented on the Model and method page.",
    icon=":material/science:",
)
where, params = data.where_clause(filters)
now = ui.kpi_snapshot(filters)
prev = ui.previous_snapshot(filters) if now.get("cases") else None
cases = data.filtered_cases(filters, ("risk_category", "tat_days", "assigned_to", "sla_breached"))
ui.insight_strip(insights.operations_insights(cases))

cols = st.columns(4)
for col, (key, label, value) in zip(
    cols,
    (
        ("avg_tat_days", "Avg turnaround", fmt_days(now.get("avg_tat_days"))),
        ("p90_tat_days", "p90 turnaround", fmt_days(now.get("p90_tat_days"))),
        ("sla_breach_pct", "SLA breach %", fmt_pct(now.get("sla_breach_pct"))),
        ("open_cases", "Open cases", fmt_int(now.get("open_cases"))),
    ),
    strict=True,
):
    with col:
        ui.kpi_card(f"ops_{key}", label, value, ui.kpi_delta(key, now, prev), kpis.KPI_POLARITY[key], simulated=True)

left, right = st.columns(2)
with left:
    with ui.tile(
        "tat_trend", "Turnaround p50 and p90 by month", "quantile_cont over closed and open cases", simulated=True
    ):
        trend = data.query(
            f"""
            SELECT opened_month, quantile_cont(tat_days, 0.5) AS p50, quantile_cont(tat_days, 0.9) AS p90,
                   AVG(sla_breached::INT) AS sla_breach, COUNT(*) AS cases
            FROM mart_case_detail {where} GROUP BY opened_month ORDER BY opened_month
            """,
            params,
        )
        fig = go.Figure(
            [
                go.Scatter(
                    x=trend["opened_month"],
                    y=trend["p50"],
                    name="p50",
                    line=dict(color=TEAL, width=3),
                    hovertemplate="%{x|%b %Y} p50: %{y:.1f} d<extra></extra>",
                ),
                go.Scatter(
                    x=trend["opened_month"],
                    y=trend["p90"],
                    name="p90",
                    line=dict(color=CHARCOAL, width=3, dash="dot"),
                    hovertemplate="%{x|%b %Y} p90: %{y:.1f} d<extra></extra>",
                ),
            ]
        )
        fig.update_layout(yaxis_title="Days")
        ui.chart(fig, "tat_trend_chart", height=280)
with right:
    with ui.tile("sla_trend", "SLA breach trend", "Share of cases with tat_days > sla_days", simulated=True):
        fig = go.Figure(
            go.Scatter(
                x=trend["opened_month"],
                y=trend["sla_breach"],
                mode="lines+markers",
                line=dict(color=BAD, width=3),
                customdata=trend["cases"],
                hovertemplate="%{x|%b %Y}: %{y:.1%} of %{customdata:,} cases<extra></extra>",
            )
        )
        fig.update_layout(yaxis=dict(tickformat=".0%", range=[0, 0.5]))
        ui.chart(fig, "sla_trend_chart", height=280)

left, right = st.columns([1.1, 1])
with left:
    with ui.tile("league", "Analyst league table", "Ranked by SLA breach rate (RANK() OVER)", simulated=True):
        league = data.query(
            f"""
            WITH per_analyst AS (
                SELECT assigned_to, COUNT(*) AS cases, AVG(tat_days) AS avg_tat,
                       quantile_cont(tat_days, 0.9) AS p90_tat, AVG(sla_breached::INT) AS breach_rate,
                       COUNT(*) FILTER (WHERE risk_category = 'High') AS high_risk_cases
                FROM mart_case_detail {where} GROUP BY assigned_to
            )
            SELECT RANK() OVER (ORDER BY breach_rate DESC) AS rank, assigned_to AS analyst, cases,
                   ROUND(avg_tat, 2) AS avg_tat_d, ROUND(p90_tat, 2) AS p90_tat_d,
                   ROUND(100 * breach_rate, 1) AS breach_pct, high_risk_cases
            FROM per_analyst ORDER BY rank, analyst
            """,
            params,
        )
        ui.table(
            league,
            hide_index=True,
            width="stretch",
            height=330,
            column_config={
                "breach_pct": st.column_config.ProgressColumn("breach %", min_value=0, max_value=50, format="%.1f%%")
            },
        )
with right:
    with ui.tile("ageing", "Open-case ageing", "Open cases at 2026-06-30 by days open", simulated=True):
        ageing = (
            data.query(
                f"""
            SELECT CASE WHEN tat_days <= 3 THEN '0-3 d' WHEN tat_days <= 7 THEN '4-7 d'
                        WHEN tat_days <= 14 THEN '8-14 d' ELSE '15+ d' END AS bucket,
                   COUNT(*) AS cases
            FROM mart_case_detail {where} AND is_open GROUP BY bucket
            """,
                params,
            )
            .set_index("bucket")
            .reindex(["0-3 d", "4-7 d", "8-14 d", "15+ d"])
            .fillna(0)
            .reset_index()
        )
        fig = go.Figure(
            go.Bar(
                x=ageing["bucket"],
                y=ageing["cases"],
                marker_color=[TEAL, YELLOW, "#FE9666", BAD],
                text=[fmt_int(v) for v in ageing["cases"]],
                textposition="outside",
                hovertemplate="%{x}: %{y:,} open cases<extra></extra>",
            )
        )
        fig.update_layout(yaxis_title="Open cases")
        ui.chart(fig, "ageing_chart", height=300)

with ui.tile("workload", "Workload heat map: analyst × month", "Cases opened per analyst per month", simulated=True):
    wl = data.query(
        f"SELECT assigned_to, opened_month, COUNT(*) AS cases FROM mart_case_detail {where} GROUP BY ALL", params
    )
    if wl.empty:
        st.info(insights.EMPTY_MESSAGE)
    else:
        grid = wl.pivot(index="assigned_to", columns="opened_month", values="cases").fillna(0).sort_index()
        fig = go.Figure(
            go.Heatmap(
                z=grid.to_numpy(),
                x=[c.strftime("%b %Y") for c in grid.columns],
                y=list(grid.index),
                colorscale=[[0, "#F3F7F7"], [1, TEAL]],
                hovertemplate="%{y} · %{x}: %{z:,} cases<extra></extra>",
                colorbar=dict(title="cases", thickness=10),
            )
        )
        ui.chart(fig, "workload_chart", height=520)

with ui.tile(
    "worst",
    "Warehouse proof: worst analyst per month (sql/04_analysis.sql query 2, all cases)",
    "CTE aggregate first, then QUALIFY ROW_NUMBER() OVER (PARTITION BY month)",
    simulated=True,
):
    worst = data.query(
        "SELECT opened_month, assigned_to, cases, sla_breaches, breach_pct "
        "FROM analysis_worst_analyst_month ORDER BY opened_month DESC"
    )
    ui.table(worst, hide_index=True, width="stretch", height=240)
