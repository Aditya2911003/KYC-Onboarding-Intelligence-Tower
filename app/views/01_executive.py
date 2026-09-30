"""Page 1 - Executive overview (Q1: is onboarding healthy?)."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from app import components as ui
from app import data, insights, kpis
from app.theme import CHARCOAL, DECISION_COLORS, DECISION_ORDER, DECISION_PATTERNS, TEAL, fmt_days, fmt_int, fmt_pct

filters = ui.page_header(
    "Executive overview", "Q1 · Is onboarding healthy: volume, approval rate, turnaround, SLA?", simulated=True
)
now = ui.kpi_snapshot(filters)
prev = ui.previous_snapshot(filters) if now.get("cases") else None
ui.insight_strip(insights.executive_insights(now, prev))

ui.headline_finding()

cards = [
    ("cases", "Cases", fmt_int(now.get("cases")), False, "count of case_id"),
    ("approval_rate", "Approval rate", fmt_pct(now.get("approval_rate")), False, "Approve / cases"),
    (
        "avg_tat_days",
        "Avg turnaround",
        fmt_days(now.get("avg_tat_days")),
        True,
        f"p90 {fmt_days(now.get('p90_tat_days'))}",
    ),
    ("sla_breach_pct", "SLA breach %", fmt_pct(now.get("sla_breach_pct")), True, "tat_days > sla_days"),
    ("open_cases", "Open cases", fmt_int(now.get("open_cases")), True, "open at 2026-06-30"),
    (
        "control_breach_rate",
        "Control-breach rate",
        fmt_pct(now.get("control_breach_rate")),
        False,
        "approvals with ID or address unverified",
    ),
]
cols = st.columns(6)
for col, (key, label, value, sim, foot) in zip(cols, cards, strict=True):
    with col:
        ui.kpi_card(key, label, value, ui.kpi_delta(key, now, prev), kpis.KPI_POLARITY.get(key, 1), sim, foot)

where, params = data.where_clause(filters)
left, right = st.columns([1.7, 1])
with left:
    with ui.tile(
        "exec_month",
        "Cases by month and decision",
        "Stacked by labelled decision · click a segment to cross-filter by decision",
        simulated=True,
    ):
        monthly = data.query(
            f"SELECT opened_month, decision, COUNT(*) AS cases FROM mart_case_detail {where} "
            "GROUP BY opened_month, decision ORDER BY opened_month",
            params,
        )
        fig = go.Figure()
        for decision in DECISION_ORDER:
            part = monthly[monthly["decision"] == decision]
            if part.empty:
                continue
            fig.add_trace(
                go.Bar(
                    x=part["opened_month"],
                    y=part["cases"],
                    name=decision,
                    marker=dict(color=DECISION_COLORS[decision], pattern_shape=DECISION_PATTERNS[decision]),
                    customdata=[[decision]] * len(part),
                    hovertemplate="%{x|%b %Y}<br>" + decision + ": %{y:,} cases<extra></extra>",
                )
            )
        fig.update_layout(barmode="stack", xaxis_title=None, yaxis_title="Cases")
        ui.xf_chart(fig, "exec_month", "decision", height=320)
with right:
    with ui.tile("exec_donut", "Decision mix", "Click a segment to cross-filter every page"):
        mix = (
            data.query(f"SELECT decision, COUNT(*) AS cases FROM mart_case_detail {where} GROUP BY decision", params)
            .set_index("decision")
            .reindex(DECISION_ORDER)
            .dropna()
            .reset_index()
        )
        if mix.empty:
            st.info(insights.EMPTY_MESSAGE)
        else:
            fig = ui.donut(
                mix["decision"],
                mix["cases"],
                [DECISION_COLORS[d] for d in mix["decision"]],
                f"<b>{fmt_int(mix['cases'].sum())}</b><br>cases",
            )
            ui.xf_chart(fig, "exec_donut", "decision", height=320)

left, right = st.columns([1.7, 1])
with left:
    with ui.tile(
        "exec_ma",
        "Monthly volume with 3-month moving average",
        "Window function AVG() OVER (ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)",
        simulated=True,
    ):
        trend = data.query(
            f"""
            WITH monthly AS (
                SELECT opened_month, COUNT(*) AS cases FROM mart_case_detail {where} GROUP BY opened_month
            )
            SELECT opened_month, cases,
                   AVG(cases) OVER (ORDER BY opened_month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS ma3
            FROM monthly ORDER BY opened_month
            """,
            params,
        )
        fig = go.Figure(
            [
                go.Bar(
                    x=trend["opened_month"],
                    y=trend["cases"],
                    name="Cases",
                    marker_color="#C8D3D5",
                    hovertemplate="%{x|%b %Y}: %{y:,} cases<extra></extra>",
                ),
                go.Scatter(
                    x=trend["opened_month"],
                    y=trend["ma3"],
                    name="3-month moving average",
                    line=dict(color=CHARCOAL, width=3),
                    hovertemplate="%{x|%b %Y}: %{y:,.0f} (3-mo avg)<extra></extra>",
                ),
            ]
        )
        ui.chart(fig, "exec_ma_chart", height=280)
        ui.footnote(
            "The rising curve is the simulation's opened-date distribution (Beta(1.3, 2.2) skewed "
            "to recent months), not observed growth."
        )
with right:
    with ui.tile("exec_q1", "Q1 answer", "Computed from the filtered data"):
        if now.get("cases"):
            st.markdown(
                f"- **Volume:** {fmt_int(now['cases'])} cases; **approval rate** {fmt_pct(now['approval_rate'])} "
                f"(EDD {fmt_pct(now['edd_rate'])}, reject {fmt_pct(now['reject_rate'])}, pending "
                f"{fmt_pct(now['pending_rate'])}).\n"
                f"- **Speed (SIMULATED):** average {fmt_days(now['avg_tat_days'])}, p90 "
                f"{fmt_days(now['p90_tat_days'])}; **SLA breach** {fmt_pct(now['sla_breach_pct'])}; "
                f"**open** {fmt_int(now['open_cases'])}.\n"
                f"- **Health verdict:** throughput is plausible, but "
                f"{fmt_pct(now['control_breach_rate'])} of approvals skipped a failed ID/address check, "
                "so onboarding is fast but not safe."
            )
        else:
            st.info(insights.EMPTY_MESSAGE)
        st.markdown(
            f'<span style="color:{TEAL};font-weight:600">KPI definitions:</span> Data quality page.',
            unsafe_allow_html=True,
        )
