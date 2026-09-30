"""Page 3 - Risk and screening: where PEP, sanction and High-risk flags concentrate."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from app import components as ui
from app import data, insights
from app.theme import CHARCOAL, RED, RISK_COLORS, RISK_ORDER, YELLOW, fmt_int, fmt_pct

filters = ui.page_header("Risk and screening", "Where do PEP, sanction and High-risk flags concentrate?")
where, params = data.where_clause(filters)

SEGMENTS = {
    "Country": "country",
    "Occupation": "occupation",
    "Account type": "account_type",
    "Age band": "age_band",
    "Income quintile": "income_quintile",
}

by_country = data.query(
    f"""
    SELECT country, COUNT(*) AS cases,
           AVG(is_sanctioned::INT) AS sanction_rate, AVG(is_pep::INT) AS pep_rate,
           AVG((risk_category = 'High')::INT) AS high_rate
    FROM mart_case_detail {where} GROUP BY country ORDER BY country
    """,
    params,
)
if by_country.empty:
    ui.insight_strip([insights.EMPTY_MESSAGE])
    st.stop()
derived = data.query(
    f"SELECT AVG((risk_category = 'High')::INT) AS high_share, COUNT(*) AS n FROM mart_case_detail {where} "
    "AND (is_pep OR is_sanctioned)",
    params,
).iloc[0]
ui.insight_strip(
    [
        insights.flat_note(by_country.set_index("country")["sanction_rate"], "the sanction rate", "countries"),
        insights.flat_note(by_country.set_index("country")["pep_rate"], "the PEP rate", "countries"),
        f"{fmt_pct(derived['high_share'])} of the {fmt_int(derived['n'])} PEP or sanctioned customers are High risk, "
        "so the risk tier is partly derived from those flags (see Known data issues).",
    ]
)

left, right = st.columns([1.1, 1])
with left:
    with ui.tile("heat", "Country × risk tier", "Cases per cell; colour = share of the country's cases"):
        cells = data.query(
            f"SELECT country, risk_category, COUNT(*) AS cases FROM mart_case_detail {where} GROUP BY ALL", params
        )
        pivot = (
            cells.pivot(index="country", columns="risk_category", values="cases")
            .reindex(columns=[r for r in RISK_ORDER if r in set(cells["risk_category"])])
            .fillna(0)
        )
        share = pivot.div(pivot.sum(axis=1), axis=0)
        fig = go.Figure(
            go.Heatmap(
                z=share.to_numpy(),
                x=list(share.columns),
                y=list(share.index),
                colorscale=[[0, "#F3F7F7"], [1, CHARCOAL]],
                zmin=0,
                zmax=1,
                text=[
                    [f"{fmt_int(pivot.iat[i, j])}<br>{fmt_pct(share.iat[i, j])}" for j in range(share.shape[1])]
                    for i in range(share.shape[0])
                ],
                texttemplate="%{text}",
                hovertemplate="%{y} · %{x}: %{text}<extra></extra>",
                showscale=False,
            )
        )
        ui.chart(fig, "heat_chart", height=320)
        ui.footnote(insights.flat_note(share.get("High", share.iloc[:, -1]), "the High-risk share", "countries"))
with right:
    with ui.tile("country_bars", "Screening hit rates by country", "Click a country to cross-filter"):
        fig = go.Figure()
        for col, name, color in (
            ("sanction_rate", "Sanction", RED),
            ("pep_rate", "PEP", YELLOW),
            ("high_rate", "High risk", CHARCOAL),
        ):
            fig.add_trace(
                go.Bar(
                    x=by_country["country"],
                    y=by_country[col],
                    name=name,
                    marker_color=color,
                    customdata=by_country[["country"]].to_numpy(),
                    text=[fmt_pct(v) for v in by_country[col]],
                    textposition="outside",
                    hovertemplate="%{x} · " + name + ": %{y:.1%}<extra></extra>",
                )
            )
        fig.update_layout(barmode="group", yaxis=dict(tickformat=".0%", title=None))
        ui.xf_chart(fig, "country_bars", "country", height=320)

with ui.tile("segments", "PEP, sanction and High-risk rates by segment", "Pick a segment; flat charts say so"):
    segment_label = st.segmented_control("Segment", list(SEGMENTS), default="Occupation", key="risk_segment")
    column = SEGMENTS[segment_label or "Occupation"]
    seg = data.query(
        f"""
        SELECT CAST({column} AS VARCHAR) AS segment, COUNT(*) AS cases,
               AVG(is_sanctioned::INT) AS sanction_rate, AVG(is_pep::INT) AS pep_rate,
               AVG((risk_category = 'High')::INT) AS high_rate
        FROM mart_case_detail {where} GROUP BY segment ORDER BY segment
        """,
        params,
    )
    fig = go.Figure()
    for col, name, color in (
        ("sanction_rate", "Sanction", RED),
        ("pep_rate", "PEP", YELLOW),
        ("high_rate", "High risk", CHARCOAL),
    ):
        fig.add_trace(
            go.Bar(
                x=seg["segment"],
                y=seg[col],
                name=name,
                marker_color=color,
                hovertemplate="%{x} · " + name + ": %{y:.1%} of %{customdata:,} cases<extra></extra>",
                customdata=seg["cases"],
            )
        )
    notes = [
        insights.flat_note(seg.set_index("segment")[c], label, segment_label.lower() if segment_label else "segment")
        for c, label in (
            ("sanction_rate", "the sanction rate"),
            ("pep_rate", "the PEP rate"),
            ("high_rate", "the High-risk rate"),
        )
    ]
    all_flat = all(insights.is_flat(seg[c]) for c in ("sanction_rate", "pep_rate", "high_rate"))
    fig.update_layout(barmode="group", yaxis=dict(tickformat=".0%"))
    ui.flat_badge("FLAT: no meaningful difference across segments", all_flat)
    ui.chart(fig, "segment_chart", height=320)
    for note in notes:
        ui.footnote(note)

with ui.tile("quintile", "Income quintile by risk tier", "Share of each income quintile in each risk tier"):
    q = data.query(
        f"SELECT income_quintile, risk_category, COUNT(*) AS cases FROM mart_case_detail {where} GROUP BY ALL",
        params,
    )
    totals = q.groupby("income_quintile")["cases"].transform("sum")
    q["share"] = q["cases"] / totals
    fig = go.Figure()
    for risk in RISK_ORDER:
        part = q[q["risk_category"] == risk].sort_values("income_quintile")
        fig.add_trace(
            go.Bar(
                x="Q" + part["income_quintile"].astype(str),
                y=part["share"],
                name=risk,
                marker_color=RISK_COLORS[risk],
                text=[fmt_pct(v) for v in part["share"]],
                hovertemplate="%{x} · " + risk + ": %{y:.1%}<extra></extra>",
            )
        )
    high = q[q["risk_category"] == "High"].set_index("income_quintile")["share"]
    flat = insights.is_flat(high)
    fig.update_layout(barmode="stack", yaxis=dict(tickformat=".0%"))
    ui.flat_badge("FLAT: income does not change the risk mix", flat)
    ui.chart(fig, "quintile_chart", height=300)
    ui.footnote(
        insights.flat_note(high.rename(lambda v: f"Q{v}"), "the High-risk share", "income quintiles")
        + " Income is uniform 200k-10M in every occupation and has no currency."
    )
