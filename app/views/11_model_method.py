"""Page 11 - Model and method: two honest ML experiments, methodology, simulation disclosure."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from app import components as ui
from app import data
from app.theme import BAD, CHARCOAL, GREY, TEAL, fmt_pct
from etl import build_warehouse as bw

ui.page_header(
    "Model and method", "Can a machine-learning model beat the policy? (No — and here is the proof.)", simulated=True
)
st.caption("Slicers do not apply here: the experiments and the simulation are run once on all cases at build time.")

if "mart_ml_results" not in data.available_marts():
    st.info("mart_ml_results.parquet is not present. Run `make ml` (python ml/decision_model.py) to create it.")
    results = pd.DataFrame(columns=["experiment", "kind", "name", "value", "std"])
else:
    results = data.query("SELECT * FROM mart_ml_results")


def metric(experiment: str, name: str) -> float:
    """Look up one metric value (NaN when missing)."""
    hit = results[(results.experiment == experiment) & (results.kind == "metric") & (results.name == name)]
    return float(hit["value"].iloc[0]) if len(hit) else float("nan")


A, B = "A_all_features", "B_without_pep_sanction_risk"
POLICY_INPUTS = {"is_sanctioned", "is_pep", "risk_category", "verified_docs"}
if not results.empty:
    ui.insight_strip(
        [
            f"With PEP, sanction and risk tier the model reaches {fmt_pct(metric(A, 'accuracy'))} accuracy: "
            "it re-learns "
            "the rules, and the remaining error is the EDD-versus-Manual-Review split that no field explains.",
            f"Without them it scores {fmt_pct(metric(B, 'accuracy'))} against a "
            f"{fmt_pct(metric(B, 'baseline_accuracy'))} "
            f"majority baseline (+{metric(B, 'lift_pp'):.1f} pp): there is no hidden signal in the other columns.",
            "A model cannot beat the policy, and here is the proof. "
            "Nothing on this dashboard 'predicts KYC decisions'.",
        ]
    )
    cols = st.columns(2)
    for col, exp, title in (
        (cols[0], A, "Experiment A · all features"),
        (cols[1], B, "Experiment B · without PEP, sanction, risk tier"),
    ):
        with col:
            with ui.tile(
                f"exp_{exp}", title, "HistGradientBoostingClassifier(random_state=42), stratified 80/20 split"
            ):
                acc, base = metric(exp, "accuracy"), metric(exp, "baseline_accuracy")
                fig = go.Figure(
                    go.Bar(
                        x=["Majority baseline", "Model accuracy", "Macro F1"],
                        y=[base, acc, metric(exp, "macro_f1")],
                        marker_color=[GREY, TEAL if exp == A else BAD, CHARCOAL],
                        text=[fmt_pct(v) for v in (base, acc, metric(exp, "macro_f1"))],
                        textposition="outside",
                        hovertemplate="%{x}: %{y:.2%}<extra></extra>",
                    )
                )
                fig.update_layout(yaxis=dict(tickformat=".0%", range=[0, 1.1]))
                ui.chart(fig, f"exp_chart_{exp}", height=260)
                imp = results[(results.experiment == exp) & (results.kind == "permutation_importance")]
                shap = results[(results.experiment == exp) & (results.kind == "shap_importance")]
                fig = go.Figure()
                fig.add_trace(
                    go.Bar(
                        y=imp["name"],
                        x=imp["value"],
                        orientation="h",
                        name="Permutation (accuracy drop)",
                        marker_color=TEAL,
                        error_x=dict(type="data", array=imp["std"]),
                        hovertemplate="%{y}: %{x:.4f}<extra></extra>",
                    )
                )
                if len(shap):
                    fig.add_trace(
                        go.Bar(
                            y=shap["name"],
                            x=shap["value"] / shap["value"].max() * imp["value"].max(),
                            orientation="h",
                            name="SHAP (mean |value|, rescaled)",
                            marker_color=CHARCOAL,
                            customdata=shap["value"],
                            hovertemplate="%{y}: mean |SHAP| %{customdata:.4f}<extra></extra>",
                        )
                    )
                fig.update_layout(
                    barmode="group", yaxis=dict(autorange="reversed"), height=420, legend=dict(orientation="h", y=-0.15)
                )
                ui.chart(fig, f"imp_chart_{exp}", height=420)

    with ui.tile("residual", "Where experiment A is wrong", "Confusion counts on the 20% test split (errors only)"):
        conf = results[(results.experiment == A) & (results.kind == "confusion")].copy()
        conf[["true", "predicted"]] = conf["name"].str.split(" -> ", expand=True)
        errors = conf[(conf["true"] != conf["predicted"]) & (conf["value"] > 0)][["true", "predicted", "value"]]
        errors = errors.rename(columns={"value": "test cases"}).sort_values("test cases", ascending=False)
        ui.table(errors, hide_index=True, width="stretch")
        share = errors["test cases"].sum()
        edd_manual = errors[
            errors["true"].isin(["Enhanced Due Diligence", "Manual Review"])
            & errors["predicted"].isin(["Enhanced Due Diligence", "Manual Review"])
        ]["test cases"].sum()
        st.markdown(
            f"{fmt_pct(edd_manual / share if share else float('nan'))} of experiment A's errors are EDD ↔ "
            "Manual Review confusions among High-risk non-PEP cases, which the source data splits at random."
        )
        top_a = results[(results.experiment == A) & (results.kind == "permutation_importance")].nlargest(4, "value")
        top_b = results[(results.experiment == B) & (results.kind == "permutation_importance")].nlargest(2, "value")
        aml = data.query(
            "SELECT AVG(aml_flag::INT) AS share, COUNT(*) AS n FROM mart_case_detail "
            "WHERE risk_category = 'High' AND NOT is_pep AND NOT is_sanctioned"
        ).iloc[0]
        st.markdown(
            f"Top permutation importances in A: {', '.join(top_a['name'])}"
            + (" — exactly the four inputs of the recovered policy." if set(top_a["name"]) == POLICY_INPUTS else ".")
            + f" In B the only lift comes from {' and '.join(top_b['name'])}: AMLFlag is itself a "
            f"policy input ({fmt_pct(aml['share'])} of the {int(aml['n']):,} High-risk, non-PEP, non-sanctioned "
            "cases have AMLFlag = Yes), not hidden signal."
        )

with ui.tile("method", "Methodology", "How every number on this dashboard is produced"):
    st.markdown(
        "1. **Warehouse:** `etl/build_warehouse.py` loads the CSVs into DuckDB (`sql/01_staging.sql`), builds a star "
        "schema with the rule engine and control-breach flags (`sql/02_model.sql`), exports small Parquet marts "
        "(`sql/03_marts.sql`) and runs the advanced-SQL analysis (`sql/04_analysis.sql`), validated against the "
        "marts.\n"
        "2. **Rule engine:** the five-rule precedence policy was recovered from the data and reproduces 100% of "
        "labelled decisions (EDD and Manual Review both count as agreement for High-risk escalations).\n"
        "3. **Data quality:** `etl/quality_checks.py` records every check in `mart_dq_report` (Data quality page).\n"
        "4. **ML honesty:** labels come from a deterministic rule engine, so a model only re-learns the rules; it "
        "is shown to prove that, not to predict decisions."
    )

with ui.tile(
    "sim_params", "Simulated-field disclosure", "Parameters of the seeded operations simulation", simulated=True
):
    params = pd.DataFrame(
        [
            ("AS_OF", f"{bw.AS_OF:%Y-%m-%d}"),
            ("RNG", f"numpy.random.default_rng({bw.SEED})"),
            (
                "opened_at",
                f"AS_OF minus int(beta({bw.OPENED_BETA_A}, {bw.OPENED_BETA_B}) × {bw.OPENED_WINDOW_DAYS}) days",
            ),
            ("assigned_to", f"uniform over Analyst_01 to Analyst_{bw.N_ANALYSTS:02d}"),
            ("channel", ", ".join(f"{c} {p:.0%}" for c, p in zip(bw.CHANNELS, bw.CHANNEL_PROBS, strict=True))),
            (
                "handling time (days)",
                f"lognormal(mean = ln(mu), sigma = {bw.HANDLING_SIGMA}); mu = "
                + ", ".join(f"{k} {v}" for k, v in bw.HANDLING_BASE_DAYS.items())
                + f"; × {bw.HIGH_RISK_MULTIPLIER} if High risk; × {bw.PEP_MULTIPLIER} if PEP",
            ),
            ("closed_at / is_open", "opened_at + handling time, clipped to AS_OF; is_open = end after AS_OF"),
            ("tat_days", "days between opened_at and closed_at"),
            (
                "sla_days",
                ", ".join(f"{k} {v}" for k, v in bw.SLA_DAYS.items()) + "; sla_breached = tat_days > sla_days",
            ),
            ("Draw order", "cases sorted by case_id; opened offset, analyst, channel, handling time"),
        ],
        columns=["field", "rule"],
    )
    ui.table(params, hide_index=True, width="stretch")
    sim = data.query(
        "SELECT AVG(tat_days) AS tat, AVG(sla_breached::INT) AS sla, COUNT(*) FILTER (WHERE is_open) AS "
        "open_cases FROM mart_case_detail"
    ).iloc[0]
    st.markdown(
        f"Resulting values (all cases): average turnaround **{sim['tat']:.2f} d**, SLA breach "
        f"**{fmt_pct(sim['sla'])}**, **{int(sim['open_cases']):,}** open cases. Pages and visuals using these "
        "fields carry the SIMULATED pill."
    )
