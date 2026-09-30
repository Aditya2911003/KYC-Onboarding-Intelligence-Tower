"""Page 10 - AI Copilot quality (Q6: can analysts trust the AI copilot's answers?)."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from app import components as ui
from app import data, insights, kpis
from app.theme import BAD, CHARCOAL, GREY, ORANGE, RED, TEAL, YELLOW, fmt_int, fmt_pct

ui.page_header("AI Copilot quality", "Q6 · Can analysts trust the AI copilot's answers?")
st.caption(
    "Slicers do not apply here: the AI benchmark is a separate dataset with no case dates, channels or countries."
)

st.error(
    "Caveat: the benchmark answers are TEMPLATED. Once customer IDs are masked, every generated answer is one of "
    f"{fmt_int(data.query('SELECT COUNT(*) AS n FROM ai_examples').iloc[0]['n'])} templates, so any detector "
    "(including the rule-based one below) scores about 100% by construction. These numbers describe the "
    "benchmark, not how a real copilot behaves in production.",
    icon=":material/warning:",
)

by_type = data.query("SELECT * FROM mart_ai_by_type ORDER BY hallucination_type")
by_q = data.query("SELECT * FROM mart_ai_by_question ORDER BY question_template")
severity = data.query("SELECT * FROM mart_ai_severity")
metrics = data.query("SELECT * FROM mart_ai_detector_metrics")
confusion = data.query("SELECT * FROM mart_ai_detector_confusion")
ui.insight_strip(insights.ai_insights(by_type, by_q))

answers = int(by_type["answers"].sum())
halluc = int(by_type["hallucinated"].sum())
accuracy = confusion.loc[confusion.true_type == confusion.predicted_type, "answers"].sum() / confusion["answers"].sum()
cols = st.columns(4)
with cols[0]:
    ui.kpi_card("ai_answers", "Benchmark answers", fmt_int(answers), foot="benchmark_dataset.csv")
with cols[1]:
    ui.kpi_card(
        "ai_rate",
        "Hallucination rate",
        fmt_pct(kpis.hallucination_rate(halluc, answers)),
        foot="hallucinated / all answers",
    )
with cols[2]:
    ui.kpi_card(
        "ai_templates",
        "Answer templates",
        fmt_int(len(data.query("SELECT 1 FROM ai_examples"))),
        foot="distinct masked generated answers",
    )
with cols[3]:
    ui.kpi_card("ai_detector", "Detector accuracy", fmt_pct(accuracy), foot="by construction (templated)")

TYPE_COLORS = {
    "Contradiction": RED,
    "Fabricated Regulation": ORANGE,
    "Missing Evidence": YELLOW,
    "Unsupported Claim": CHARCOAL,
    "Wrong Risk Score": GREY,
    "NONE": TEAL,
}
left, right = st.columns(2)
with left:
    with ui.tile("ai_type", "Answers by hallucination type", "NONE = faithful answers (the control group)"):
        fig = go.Figure(
            go.Bar(
                x=by_type["hallucination_type"],
                y=by_type["answers"],
                marker_color=[TYPE_COLORS.get(t, GREY) for t in by_type["hallucination_type"]],
                text=[fmt_int(v) for v in by_type["answers"]],
                textposition="outside",
                customdata=by_type[["hallucination_rate_pct", "avg_len_diff_chars"]].to_numpy(),
                hovertemplate="%{x}: %{y:,} answers<br>hallucinated %{customdata[0]:.0f}%<br>"
                "avg length change %{customdata[1]:+.0f} chars<extra></extra>",
            )
        )
        ui.chart(fig, "ai_type_chart", height=300)
with right:
    with ui.tile("ai_sev", "Severity by hallucination type", "Share of each type's hallucinations (evenly spread)"):
        fig = go.Figure()
        for sev, color in zip(["Low", "Medium", "High", "Critical"], [TEAL, YELLOW, ORANGE, BAD], strict=True):
            part = severity[severity["severity"] == sev].sort_values("hallucination_type")
            fig.add_trace(
                go.Bar(
                    x=part["hallucination_type"],
                    y=part["pct_of_type"] / 100,
                    name=sev,
                    marker_color=color,
                    customdata=part["answers"],
                    hovertemplate="%{x} · " + sev + ": %{y:.1%} (%{customdata:,})<extra></extra>",
                )
            )
        flat = insights.is_flat(severity["pct_of_type"] / 100, threshold_pp=2.0)
        fig.update_layout(barmode="stack", yaxis=dict(tickformat=".0%"))
        ui.flat_badge("FLAT: severity is evenly spread in every type", flat)
        ui.chart(fig, "ai_sev_chart", height=300)

with ui.tile(
    "ai_q",
    "Hallucination rate by question template",
    "Customer IDs masked with regexp_replace(Question, 'C[0-9]+', 'C#')",
):
    fig = go.Figure(
        go.Bar(
            y=by_q["question_template"],
            x=by_q["hallucination_pct"] / 100,
            orientation="h",
            marker_color=CHARCOAL,
            text=[fmt_pct(v / 100) for v in by_q["hallucination_pct"]],
            textposition="auto",
            customdata=by_q["answers"],
            hovertemplate="%{y}<br>%{x:.1%} of %{customdata:,} answers<extra></extra>",
        )
    )
    flat = insights.is_flat(by_q["hallucination_pct"] / 100, threshold_pp=1.0)
    fig.update_layout(xaxis=dict(tickformat=".0%", range=[0, 1]))
    ui.flat_badge("FLAT: the question asked does not change the hallucination rate", flat)
    ui.chart(fig, "ai_q_chart", height=260)

left, right = st.columns([1.1, 1])
with left:
    with ui.tile("ai_cm", "Detector confusion matrix", "Rule-based, reference-grounded detector (etl/ai_qa_marts.py)"):
        labels = sorted(set(confusion["true_type"]) | set(confusion["predicted_type"]))
        grid = (
            confusion.pivot(index="true_type", columns="predicted_type", values="answers")
            .reindex(index=labels, columns=labels)
            .fillna(0)
        )
        fig = go.Figure(
            go.Heatmap(
                z=grid.to_numpy(),
                x=labels,
                y=labels,
                colorscale=[[0, "#F3F7F7"], [1, TEAL]],
                showscale=False,
                text=[[fmt_int(v) for v in row] for row in grid.to_numpy()],
                texttemplate="%{text}",
                hovertemplate="true %{y} → predicted %{x}: %{text}<extra></extra>",
            )
        )
        fig.update_layout(xaxis_title="Predicted", yaxis_title="True", yaxis=dict(autorange="reversed"))
        ui.chart(fig, "ai_cm_chart", height=340)
with right:
    with ui.tile("ai_pr", "Precision and recall per type", "From the confusion matrix"):
        ui.table(
            metrics,
            hide_index=True,
            width="stretch",
            height=260,
            column_config={
                "precision": st.column_config.NumberColumn(format="%.3f"),
                "recall": st.column_config.NumberColumn(format="%.3f"),
                "f1": st.column_config.NumberColumn(format="%.3f"),
            },
        )
        ui.footnote(
            "Detector rules: identical text → faithful; ground truth kept plus an appended sentence → typed by "
            "its content (cited regulation, risk level, other claim); ground truth replaced → Contradiction "
            "if a different definite outcome is asserted, else Missing Evidence."
        )

with ui.tile(
    "ai_examples", "Example answers (one per masked template, max 25)", "Flagged claim = what the detector objected to"
):
    examples = data.query(
        "SELECT hallucination_type, severity, question_template, generated_masked, flagged_claim, "
        "detector_prediction, answers_with_template FROM ai_examples ORDER BY example_id"
    )
    ui.table(examples, hide_index=True, width="stretch", height=420)
    rate = kpis.hallucination_rate(halluc, answers)
    q_flat = insights.is_flat(by_q["hallucination_pct"] / 100, threshold_pp=1.0)
    st.markdown(
        f"**Q6 answer:** not on this evidence. {fmt_pct(rate)} of benchmark answers are hallucinated"
        f"{', at the same rate for every question template' if q_flat else ''}, and the benchmark is too "
        "templated to measure a detector honestly. Before trusting the "
        "copilot, evaluate it on real, varied answers with human-labelled claims."
    )
