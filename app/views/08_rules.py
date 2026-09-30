"""Page 8 - Rules and policy: rule library coverage, orphan rules, guideline timeline, search."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from app import components as ui
from app import data
from app.theme import BAD, CHARCOAL, PALETTE, TEAL, fmt_int, fmt_pct

ui.page_header("Rules and policy", "Is every AML rule backed by an implementing guideline?")
st.caption("Slicers do not apply here: rules and guidelines have no case, country-of-customer or date dimension.")

coverage = data.query("SELECT * FROM mart_rule_coverage")
rules_total = int(coverage["rules"].sum())
orphans = int(coverage["rules_without_guideline"].sum())
guidelines = int(coverage["guidelines"].sum())
distinct = data.query("SELECT COUNT(DISTINCT rule_text) AS rt FROM mart_rules").iloc[0]["rt"]
distinct_par = data.query("SELECT COUNT(DISTINCT paragraph) AS p FROM mart_guidelines").iloc[0]["p"]
ui.insight_strip(
    [
        f"{fmt_int(orphans)} of {fmt_int(rules_total)} rules ({fmt_pct(orphans / rules_total)}) have no implementing "
        f"guideline; {fmt_int(guidelines)} guidelines cover the rest.",
        f"The library is templated: only {fmt_int(distinct)} distinct rule texts and {fmt_int(distinct_par)} distinct "
        "guideline paragraphs, so keyword search returns many near-identical rules.",
    ]
)

cols = st.columns(4)
with cols[0]:
    ui.kpi_card("rules", "Rules", fmt_int(rules_total), foot="aml_rules.csv")
with cols[1]:
    ui.kpi_card("guidelines", "Guidelines", fmt_int(guidelines), foot="kyc_guidelines.csv")
with cols[2]:
    ui.kpi_card("orphans", "Orphan rules", fmt_int(orphans), foot="no guideline (ANTI JOIN)")
with cols[3]:
    ui.kpi_card("coverage", "Rule coverage", fmt_pct(1 - orphans / rules_total), foot="rules with ≥1 guideline")

left, mid, right = st.columns(3)
for column, dim, key in ((left, "rule_category", "cat"), (mid, "jurisdiction", "jur"), (right, "priority", "pri")):
    with column:
        with ui.tile(f"rules_{key}", f"Rules by {dim.replace('_', ' ')}", "Orphans in red"):
            agg = coverage.groupby(dim, as_index=False)[["rules", "rules_without_guideline"]].sum()
            if dim == "priority":
                agg = agg.set_index(dim).reindex(["Critical", "High", "Medium", "Low"]).dropna().reset_index()
            fig = go.Figure(
                [
                    go.Bar(
                        x=agg[dim],
                        y=agg["rules"] - agg["rules_without_guideline"],
                        name="With guideline",
                        marker_color=TEAL,
                        hovertemplate="%{x}: %{y:,} covered<extra></extra>",
                    ),
                    go.Bar(
                        x=agg[dim],
                        y=agg["rules_without_guideline"],
                        name="Orphan",
                        marker_color=BAD,
                        marker_pattern_shape="x",
                        hovertemplate="%{x}: %{y:,} orphan<extra></extra>",
                    ),
                ]
            )
            fig.update_layout(barmode="stack")
            ui.chart(fig, f"rules_{key}_chart", height=280)

left, right = st.columns([1, 1.2])
with left:
    with ui.tile("orphans_list", "Orphan rules (no guideline)", "sql/04_analysis.sql query (7): ANTI JOIN"):
        orphan_df = data.query("SELECT * FROM analysis_rule_orphans")
        ui.table(orphan_df, hide_index=True, width="stretch", height=330)
with right:
    with ui.tile("timeline", "Guideline versions by effective year", "EffectiveDate parsed explicitly as dd-mm-yyyy"):
        tl = data.query("SELECT * FROM mart_guideline_timeline ORDER BY effective_year, version")
        fig = go.Figure()
        for i, version in enumerate(sorted(tl["version"].unique())):
            part = tl[tl["version"] == version]
            fig.add_trace(
                go.Bar(
                    x=part["effective_year"].astype(str),
                    y=part["guidelines"],
                    name=version,
                    marker_color=PALETTE[i % len(PALETTE)],
                    hovertemplate=version + " · %{x}: %{y:,} guidelines<extra></extra>",
                )
            )
        fig.update_layout(barmode="stack", xaxis_title="Effective year", yaxis_title="Guidelines")
        ui.chart(fig, "timeline_chart", height=330)
        span = data.query("SELECT MIN(effective_date) AS lo, MAX(effective_date) AS hi FROM mart_guidelines").iloc[0]
        ui.footnote(f"Effective dates span {span['lo']:%d %b %Y} to {span['hi']:%d %b %Y}.")


@st.fragment
def keyword_search() -> None:
    """Parameterised keyword search over rule text and guideline paragraphs."""
    with ui.tile(
        "search", "Keyword search", "Case-insensitive match on rule text and guideline paragraphs (max 200 rows each)"
    ):
        term = st.text_input("Search term", value="sanction", max_chars=60, key="rule_search").strip()
        if len(term) < 3:
            st.info("Type at least 3 characters.")
            return
        rules = data.query(
            "SELECT rule_id, rule_title, rule_category, jurisdiction, priority, n_guidelines, rule_text "
            "FROM mart_rules WHERE rule_text ILIKE '%' || ? || '%' OR rule_title ILIKE '%' || ? || '%' "
            "ORDER BY rule_id LIMIT 200",
            (term, term),
        )
        paras = data.query(
            "SELECT guideline_id, rule_id, section, version, effective_date, paragraph FROM mart_guidelines "
            "WHERE paragraph ILIKE '%' || ? || '%' ORDER BY guideline_id LIMIT 200",
            (term,),
        )
        counts = data.query(
            "SELECT (SELECT COUNT(*) FROM mart_rules WHERE rule_text ILIKE '%' || ? || '%' "
            "OR rule_title ILIKE '%' || ? || '%') AS r, "
            "(SELECT COUNT(*) FROM mart_guidelines WHERE paragraph ILIKE '%' || ? || '%') AS g",
            (term, term, term),
        ).iloc[0]
        st.markdown(
            f"**{fmt_int(counts['r'])} rules** and **{fmt_int(counts['g'])} guideline paragraphs** match "
            f"'{term}' (showing up to 200 of each)."
        )
        tab_r, tab_g = st.tabs(["Rules", "Guidelines"])
        with tab_r:
            ui.table(rules, hide_index=True, width="stretch", height=260)
        with tab_g:
            ui.table(paras, hide_index=True, width="stretch", height=260)


keyword_search()
st.markdown(
    f'<span style="color:{CHARCOAL}">Search runs inside an <code>st.fragment</code>, so typing does not '
    "re-render the rest of the page.</span>",
    unsafe_allow_html=True,
)
