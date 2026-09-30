"""Page 5 - Documents and OCR (Q5a: is document verification and OCR reliable?)."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from app import components as ui
from app import data, insights, kpis
from app.theme import CHARCOAL, DECISION_COLORS, DECISION_ORDER, RED, TEAL, fmt_int, fmt_pct

filters = ui.page_header("Documents and OCR", "Q5 · Is document verification and OCR reliable?")
where, params = data.where_clause(filters, prefix="c.")
JOIN = "FROM mart_customer_docs AS d JOIN mart_case_detail AS c USING (customer_id)"

by_type = data.query(
    f"""
    SELECT d.doc_type, COUNT(*) AS docs, COUNT(*) FILTER (WHERE NOT d.verified) AS failed,
           AVG(d.confidence) AS avg_conf,
           COUNT(*) FILTER (WHERE d.confidence < {kpis.LOW_CONFIDENCE_THRESHOLD}) AS low_conf
    {JOIN} {where} GROUP BY d.doc_type ORDER BY d.doc_type
    """,
    params,
)
docs_total = int(by_type["docs"].sum()) if not by_type.empty else 0
low_rate = by_type["low_conf"].sum() / docs_total if docs_total else float("nan")
fail_rate = by_type["failed"].sum() / docs_total if docs_total else float("nan")
ui.insight_strip(insights.documents_insights(by_type, low_rate))

cols = st.columns(4)
with cols[0]:
    ui.kpi_card("docs", "Documents", fmt_int(docs_total), foot="5 per customer")
with cols[1]:
    ui.kpi_card("doc_fail", "Document fail rate", fmt_pct(fail_rate), foot="unverified / documents")
with cols[2]:
    ui.kpi_card("low_conf", "Low-confidence rate", fmt_pct(low_rate), foot="OCR confidence < 0.85")
with cols[3]:
    avg_conf = (by_type["avg_conf"] * by_type["docs"]).sum() / docs_total if docs_total else float("nan")
    ui.kpi_card("avg_conf", "Mean OCR confidence", f"{avg_conf:.3f}" if docs_total else "—", foot="0.80 to 0.99")

left, right = st.columns(2)
with left:
    with ui.tile("fail_type", "Fail rate by document type", "Unverified documents / documents"):
        if by_type.empty:
            st.info(insights.EMPTY_MESSAGE)
        else:
            rate = by_type["failed"] / by_type["docs"]
            fig = go.Figure(
                go.Bar(
                    x=by_type["doc_type"],
                    y=rate,
                    marker_color=RED,
                    text=[fmt_pct(v) for v in rate],
                    textposition="outside",
                    customdata=by_type[["failed", "docs"]].to_numpy(),
                    hovertemplate="%{x}: %{y:.2%} (%{customdata[0]:,} of %{customdata[1]:,})<extra></extra>",
                )
            )
            flat = insights.is_flat(rate, threshold_pp=1.0)
            fig.update_layout(yaxis=dict(tickformat=".1%", range=[0, max(rate.max() * 1.4, 0.01)]))
            ui.flat_badge("FLAT: about the same for every document type", flat)
            ui.chart(fig, "fail_type_chart", height=300)
with right:
    with ui.tile("conf_hist", "OCR-confidence histogram", "0.01-wide bins; red = unverified documents"):
        hist = data.query(
            f"""
            SELECT ROUND(FLOOR(d.confidence * 100) / 100, 2) AS conf_bin,
                   COUNT(*) FILTER (WHERE d.verified) AS verified,
                   COUNT(*) FILTER (WHERE NOT d.verified) AS failed
            {JOIN} {where} GROUP BY conf_bin ORDER BY conf_bin
            """,
            params,
        )
        fig = go.Figure(
            [
                go.Bar(
                    x=hist["conf_bin"],
                    y=hist["verified"],
                    name="Verified",
                    marker_color=TEAL,
                    hovertemplate="confidence %{x:.2f}: %{y:,} verified<extra></extra>",
                ),
                go.Bar(
                    x=hist["conf_bin"],
                    y=hist["failed"],
                    name="Unverified",
                    marker_color=RED,
                    marker_pattern_shape="/",
                    hovertemplate="confidence %{x:.2f}: %{y:,} unverified<extra></extra>",
                ),
            ]
        )
        fig.add_vline(
            x=kpis.LOW_CONFIDENCE_THRESHOLD,
            line_dash="dash",
            line_color=CHARCOAL,
            annotation_text="0.85 low-confidence threshold",
            annotation_position="top",
        )
        fig.update_layout(barmode="stack", bargap=0.05, xaxis=dict(title="OCR confidence"))
        ui.chart(fig, "conf_hist_chart", height=300)
        ui.footnote(
            "Confidence is uniform and independent of verification: failed documents appear in every bin "
            "at the same share."
        )

left, right = st.columns(2)
with left:
    with ui.tile("lowconf_country", "Low-confidence share by issue country", "Documents with confidence < 0.85"):
        lc = data.query(
            f"""
            SELECT d.issue_country, COUNT(*) AS docs,
                   AVG((d.confidence < {kpis.LOW_CONFIDENCE_THRESHOLD})::INT) AS low_conf_rate,
                   AVG((NOT d.verified)::INT) AS fail_rate
            {JOIN} {where} GROUP BY d.issue_country ORDER BY d.issue_country
            """,
            params,
        )
        fig = go.Figure(
            go.Bar(
                x=lc["issue_country"],
                y=lc["low_conf_rate"],
                marker_color=CHARCOAL,
                text=[fmt_pct(v) for v in lc["low_conf_rate"]],
                textposition="outside",
                hovertemplate="%{x}: %{y:.1%} low confidence<extra></extra>",
            )
        )
        fig.update_layout(yaxis=dict(tickformat=".0%", range=[0, 0.4]))
        ui.chart(fig, "lowconf_chart", height=280)
        ui.footnote(
            insights.flat_note(
                lc.set_index("issue_country")["low_conf_rate"],
                "the low-confidence share",
                "issuing countries",
                threshold_pp=1.0,
            )
        )
with right:
    with ui.tile(
        "docs_by_decision", "Verified documents per case by decision", "Cases with fewer than 5 verified documents"
    ):
        vd = data.query(
            f"SELECT decision, verified_docs, COUNT(*) AS cases FROM mart_case_detail c {where} GROUP BY ALL", params
        )
        fig = go.Figure()
        for decision in DECISION_ORDER:
            part = vd[vd["decision"] == decision].sort_values("verified_docs")
            if not part.empty:
                fig.add_trace(
                    go.Bar(
                        x=part["verified_docs"].astype(str),
                        y=part["cases"],
                        name=decision,
                        marker_color=DECISION_COLORS[decision],
                        hovertemplate=decision + " · %{x} verified: %{y:,}<extra></extra>",
                    )
                )
        fig.update_layout(
            barmode="stack", xaxis_title="Verified documents (of 5)", yaxis_type="log", yaxis_title="Cases (log scale)"
        )
        ui.chart(fig, "docs_decision_chart", height=280)
        ui.footnote(
            "Approvals with 4 verified documents are allowed by policy (threshold is 4) but show as the "
            "'fewer than 5 verified docs' breach component on the Controls page."
        )

with ui.tile("under5", "Cases with fewer than 5 verified documents", "Drill through to Customer 360"):
    under = data.query(
        f"""
        SELECT customer_id, case_id, decision, verified_docs, risk_category, country
        FROM mart_case_detail c {where} AND verified_docs < 5 ORDER BY verified_docs, case_id
        LIMIT {data.EXPORT_ROW_CAP}
        """,
        params,
    )
    n_under = data.query(f"SELECT COUNT(*) AS n FROM mart_case_detail c {where} AND verified_docs < 5", params)
    st.caption(
        f"{fmt_int(n_under.iloc[0]['n'])} cases in view; first {fmt_int(len(under))} shown (fewest documents first)."
    )
    ui.case_table(under, "under5", height=260)

with ui.tile(
    "doc_matrix", "Reference: mart_doc_quality (all documents)", "Fail % and low-confidence % by type × issue country"
):
    matrix = data.query(
        "SELECT doc_type, issue_country, docs, fail_pct, low_conf_pct, avg_conf FROM mart_doc_quality "
        "ORDER BY doc_type, issue_country"
    )
    ui.table(matrix, hide_index=True, width="stretch", height=240)
    facts = data.query(
        f"""
        SELECT AVG(d.confidence) FILTER (WHERE d.verified)     AS conf_verified,
               AVG(d.confidence) FILTER (WHERE NOT d.verified) AS conf_failed,
               MIN(year(d.expiry_date)) AS first_expiry, MAX(year(d.expiry_date)) AS last_expiry
        {JOIN} {where}
        """,
        params,
    ).iloc[0]
    if docs_total:
        even = insights.is_flat(by_type["failed"] / by_type["docs"], threshold_pp=1.0)
        st.markdown(
            f"**Q5 (documents) answer:** verification fails for {fmt_pct(fail_rate)} of documents in view"
            f"{', evenly across document types' if even else ''}. Mean OCR confidence is "
            f"{facts['conf_verified']:.3f} for verified vs {facts['conf_failed']:.3f} for failed documents, so "
            'confidence does not separate them. "Expired documents" is not a metric: every document expires '
            f"between {int(facts['first_expiry'])} and {int(facts['last_expiry'])}."
        )
