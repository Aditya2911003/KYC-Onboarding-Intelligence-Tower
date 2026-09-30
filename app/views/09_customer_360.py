"""Page 9 - Customer 360 and what-if simulator."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from app import components as ui
from app import data, kpis
from app.theme import BAD, DECISION_COLORS, MUTED, fmt_int

filters = ui.page_header(
    "Customer 360 and what-if", "Why did this customer get this decision, and what would change it?", simulated=True
)
st.caption("Search is by exact CustomerID only (privacy: no browsing of the customer table).")
where, params = data.where_clause(filters)
examples = data.query(
    f"SELECT customer_id FROM mart_case_detail {where} AND breach_approved_id_or_address ORDER BY case_id LIMIT 5",
    params,
)["customer_id"].tolist()
ui.insight_strip(
    [
        "The rule path shows which of the five policy rules fired; the what-if simulator re-runs the same rule engine "
        "the warehouse uses (app/kpis.py mirrors sql/02_model.sql and the tests prove they agree).",
        f"Example IDs from the current slicers (approved despite a failed check): {', '.join(examples) or 'none'}.",
    ]
)

default_id = st.session_state.get("c360_id", examples[0] if examples else "C000000")
search = (
    st.text_input("CustomerID (exact, e.g. C000123)", value=default_id, max_chars=7, key="c360_input").strip().upper()
)
if not ui.valid_customer_id(search):
    st.error("CustomerID must be 'C' followed by 6 digits.")
    st.stop()
st.session_state["c360_id"] = search

with ui.tile(
    "c360_profile", f"Customer 360 · {search}", "Profile, documents, rule path, risk score, timeline", simulated=True
):
    ui.render_customer_360(search, key_prefix="page")

case, _docs = ui.load_customer(search)


@st.fragment
def what_if() -> None:
    """Toggle the policy inputs and see the decision and the rule that fires."""
    base = case.iloc[0] if not case.empty else None
    with ui.tile("whatif", "What-if simulator", "Change the policy inputs; the rule engine re-evaluates instantly"):
        c1, c2, c3, c4 = st.columns(4)
        sanctioned = c1.toggle(
            "Sanctioned", value=bool(base.is_sanctioned) if base is not None else False, key=f"wi_sanc_{search}"
        )
        pep = c2.toggle("PEP", value=bool(base.is_pep) if base is not None else False, key=f"wi_pep_{search}")
        risk = c3.selectbox(
            "Risk tier",
            ["Low", "Medium", "High"],
            index=["Low", "Medium", "High"].index(base.risk_category) if base is not None else 0,
            key=f"wi_risk_{search}",
        )
        docs = c4.slider(
            "Verified documents", 0, 5, int(base.verified_docs) if base is not None else 5, key=f"wi_docs_{search}"
        )
        c5, c6 = st.columns(2)
        identity = c5.toggle(
            "Identity verified", value=bool(base.identity_verified) if base is not None else True, key=f"wi_id_{search}"
        )
        address = c6.toggle(
            "Address verified", value=bool(base.address_verified) if base is not None else True, key=f"wi_addr_{search}"
        )
        result = kpis.engine_decision(sanctioned, pep, risk, docs)
        colour = DECISION_COLORS.get(result.decision, "#F2C80F")
        st.markdown(
            f'<div style="border-left:6px solid {colour};padding:8px 14px;background:#FAFAFA">'
            f'<div style="font-size:12px;color:{MUTED};text-transform:uppercase">Engine decision</div>'
            f'<div style="font-size:28px;font-weight:600">{result.decision}</div>'
            f"<div><b>{result.rule}</b> — {result.explanation}</div></div>",
            unsafe_allow_html=True,
        )
        if result.decision == "Approve" and not (identity and address):
            st.error(
                "Control gap: the policy would APPROVE this customer although identity or address is unverified "
                "— the verification flags are not part of the decision logic."
            )
        score, parts = kpis.risk_score_breakdown(sanctioned, pep, risk, identity, address, docs)
        fig = go.Figure(
            go.Bar(
                x=[p for _, p in parts] or [0],
                y=[n for n, _ in parts] or ["No risk components"],
                orientation="h",
                marker_color=BAD,
                text=[f"+{p}" for _, p in parts] or [""],
                textposition="auto",
            )
        )
        fig.update_layout(
            title=dict(
                text=f"Additive risk score {score} / 100 (illustration, not a calibrated model)", font=dict(size=13)
            ),
            yaxis=dict(autorange="reversed"),
            margin=dict(t=40),
        )
        ui.chart(fig, "whatif_score", height=90 + 32 * max(len(parts), 1))
        if base is not None:
            changed = result.decision != base.engine_decision
            st.caption(
                f"Actual case: {base.decision} via {base.engine_rule}. "
                + ("Your changes alter the engine outcome." if changed else "Your inputs give the same engine outcome.")
            )


what_if()
n = data.query(f"SELECT COUNT(*) AS n FROM mart_case_detail {where}", params).iloc[0]["n"]
ui.footnote(f"{fmt_int(n)} customers match the current slicers; Customer 360 itself ignores slicers.")
