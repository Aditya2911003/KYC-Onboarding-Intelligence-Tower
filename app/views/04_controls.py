"""Page 4 - Controls and compliance (Q3: do decisions follow policy? Q4: approved despite failed checks?)."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from app import components as ui
from app import data, insights
from app.theme import BAD, CHARCOAL, GOOD, ORANGE, RED, YELLOW, fmt_int, fmt_pct

filters = ui.page_header(
    "Controls and compliance",
    "Q3 · Do decisions follow policy for 100% of cases?  Q4 · Are customers approved despite a failed check?",
    simulated=True,
)
where, params = data.where_clause(filters)
now = ui.kpi_snapshot(filters)
approvals = now.get("approvals") or 0
components = {
    "approvals": approvals,
    "control_breach_rate": now.get("control_breach_rate"),
    "breach_no_identity_rate": now.get("breach_no_identity_rate"),
    "breach_no_address_rate": now.get("breach_no_address_rate"),
}
agreement = now.get("engine_agreement")
if agreement is not None and agreement < 1.0:
    st.markdown(
        f'<div class="alert-banner">ALERT: rule-engine agreement is {fmt_pct(agreement, 2)} — some labelled '
        "decisions do not follow the recovered policy. Investigate before relying on any KPI.</div>",
        unsafe_allow_html=True,
    )
ui.insight_strip(insights.controls_insights(components, agreement if agreement is not None else float("nan")))
ui.headline_finding()

c1, c2 = st.columns(2)
with c1:
    with ui.tile("big_agree", "Rule-engine agreement (Q3)", "engine_agrees over all cases in view"):
        st.markdown(
            f'<div class="big-card"><div class="v" style="color:{GOOD if (agreement or 0) >= 1 else BAD}">'
            f'{fmt_pct(agreement)}</div><div class="l">of {fmt_int(now.get("cases"))} decisions reproduced by the '
            "5-rule policy (sanction → PEP → High risk → &lt;4 docs → approve)</div></div>",
            unsafe_allow_html=True,
        )
with c2:
    with ui.tile("big_breach", "Approvals with failed identity or address (Q4)", "Control-breach rate"):
        st.markdown(
            f'<div class="big-card"><div class="v" style="color:{BAD}">{fmt_pct(now.get("control_breach_rate"))}'
            f'</div><div class="l">of {fmt_int(approvals)} approvals · identity unverified '
            f"{fmt_pct(now.get('breach_no_identity_rate'))} · address unverified "
            f"{fmt_pct(now.get('breach_no_address_rate'))} · fewer than 5 verified docs "
            f"{fmt_pct(now.get('breach_missing_doc_rate'))}</div></div>",
            unsafe_allow_html=True,
        )

BREACH_SQL = """
    SELECT {dim} AS dim,
           COUNT(*) FILTER (WHERE decision = 'Approve')                       AS approvals,
           COUNT(*) FILTER (WHERE breach_approved_no_identity)                AS no_identity,
           COUNT(*) FILTER (WHERE breach_approved_no_address)                 AS no_address,
           COUNT(*) FILTER (WHERE breach_approved_id_or_address)              AS id_or_address,
           COUNT(*) FILTER (WHERE breach_approved_missing_doc)                AS missing_doc
    FROM mart_case_detail {where} GROUP BY dim ORDER BY dim
"""


def breach_bars(dim: str, key: str, slicer: str, title: str, simulated: bool) -> None:
    """Grouped breach-rate bars by one dimension, clickable to cross-filter."""
    frame = data.query(BREACH_SQL.format(dim=dim, where=where), params)
    with ui.tile(key, title, "Share of approvals · click a group to cross-filter", simulated=simulated):
        if frame.empty or frame["approvals"].sum() == 0:
            st.info("No approvals in the current selection.")
            return
        fig = go.Figure()
        for col, name, color in (
            ("id_or_address", "ID or address unverified", RED),
            ("no_identity", "Identity unverified", ORANGE),
            ("no_address", "Address unverified", YELLOW),
            ("missing_doc", "Fewer than 5 verified docs", CHARCOAL),
        ):
            rate = frame[col] / frame["approvals"].where(frame["approvals"] > 0)
            fig.add_trace(
                go.Bar(
                    x=frame["dim"],
                    y=rate,
                    name=name,
                    marker_color=color,
                    customdata=frame[["dim"]].to_numpy(),
                    hovertemplate="%{x} · " + name + ": %{y:.1%}<extra></extra>",
                )
            )
        fig.update_layout(barmode="group", yaxis=dict(tickformat=".0%"))
        ui.xf_chart(fig, key, slicer, height=300)
        rates = frame.set_index("dim")["id_or_address"] / frame.set_index("dim")["approvals"]
        ui.footnote(insights.flat_note(rates, "the control-breach rate", title.split(" by ")[-1].lower()))


left, right = st.columns(2)
with left:
    breach_bars("country", "breach_country", "country", "Control breaches by country", simulated=False)
with right:
    breach_bars("channel", "breach_channel", "channel", "Control breaches by channel", simulated=True)

with ui.tile("breach_trend", "Breach trend by month", "Monthly control-breach rate among approvals", simulated=True):
    trend = data.query(
        f"""
        SELECT opened_month,
               COUNT(*) FILTER (WHERE breach_approved_id_or_address)
                 / NULLIF(COUNT(*) FILTER (WHERE decision = 'Approve'), 0) AS breach_rate,
               COUNT(*) FILTER (WHERE decision = 'Approve') AS approvals
        FROM mart_case_detail {where} GROUP BY opened_month ORDER BY opened_month
        """,
        params,
    )
    fig = go.Figure(
        go.Scatter(
            x=trend["opened_month"],
            y=trend["breach_rate"],
            mode="lines+markers",
            line=dict(color=BAD, width=3),
            customdata=trend["approvals"],
            hovertemplate="%{x|%b %Y}: %{y:.1%} of %{customdata:,} approvals<extra></extra>",
        )
    )
    fig.update_layout(yaxis=dict(tickformat=".0%", range=[0, 1]))
    ui.chart(fig, "breach_trend_chart", height=260)
    ui.footnote(
        insights.flat_note(
            trend.set_index("opened_month")["breach_rate"], "the monthly breach rate", "months", threshold_pp=10.0
        )
        + (
            " The breach is structural, not a recent deterioration."
            if insights.is_flat(trend["breach_rate"], threshold_pp=10.0)
            else ""
        )
    )

with ui.tile(
    "breach_table", "Approved despite failed control", "Drill through to Customer 360 · export capped at 5,000 rows"
):
    breaches = data.query(
        f"""
        SELECT customer_id, case_id, country, channel, risk_category, verified_docs,
               identity_verified, address_verified, opened_date
        FROM mart_case_detail {where} AND breach_approved_id_or_address
        ORDER BY case_id
        LIMIT {data.EXPORT_ROW_CAP}
        """,
        params,
    )
    total = data.query(
        f"SELECT COUNT(*) AS n FROM mart_case_detail {where} AND breach_approved_id_or_address", params
    ).iloc[0]["n"]
    st.caption(
        f"{fmt_int(total)} breached approvals in view; showing the first {fmt_int(len(breaches))} by case ID. "
        "Channel and opened date are SIMULATED."
    )
    ui.case_table(breaches, "breach_cases", height=300)
    ui.export_button(breaches, "synthetic_breach_list.csv", "Export breach list", key="export_breaches")

with ui.tile(
    "breach_proof",
    "Warehouse proof: sql/04_analysis.sql query (4), all cases",
    "GROUPING SETS: channel × country, both margins and the grand total in one pass",
    simulated=True,
):
    proof = data.query(
        "SELECT channel, country, approvals, approved_failed_id_or_address, breach_pct FROM "
        "analysis_breach_by_channel_country WHERE grouping_level > 0 ORDER BY grouping_level, channel, country"
    )
    ui.table(proof, hide_index=True, width="stretch", height=260)
