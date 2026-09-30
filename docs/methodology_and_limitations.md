# Methodology and limitations

## 1. What is real and what is simulated

| Real (from the synthetic dataset) | Simulated (seed 42, `sim_case_ops`) |
|---|---|
| Customers, cases, labelled decisions and reasons, PEP / sanction / risk / AML flags, identity and address verification flags, the five documents with verification and OCR confidence, AML rules and guidelines, AI benchmark answers and hallucination labels | Opened and closed timestamps, turnaround (`tat_days`), SLA targets and breaches, open cases, analyst assignment, intake channel |

"Real" here means *present in the provided data*. The dataset itself is synthetic: no real person or bank is represented.

## 2. Simulation disclosure

The source has no case timestamps, analysts, channels or SLA fields. To show operational analytics without pretending the data has them, `etl/build_warehouse.py::simulate_case_ops` creates them deterministically and keeps them **only** in `sim_case_ops` (joined into `fact_case` and the marts, where every such column is documented as SIMULATED).

| Field | Rule |
|---|---|
| `AS_OF` | 2026-06-30. RNG: `numpy.random.default_rng(42)` |
| `opened_at` | `AS_OF` minus `int(beta(1.3, 2.2) * 730)` days (skewed to recent months, a growth curve) |
| `assigned_to` | uniform over `Analyst_01` to `Analyst_24` |
| `channel` | Web 40%, Branch 25%, Mobile 25%, Partner 10% |
| handling time (days) | lognormal(mean = ln(mu), sigma = 0.45) where mu = base by decision (Approve 1.5, Pending Documents 4.0, Manual Review 5.0, Enhanced Due Diligence 7.0, Reject 2.5) × 1.35 if High risk × 1.25 if PEP |
| `closed_at` | `opened_at` + handling time, clipped to `AS_OF`; `is_open` = end after `AS_OF` |
| `tat_days` | days between `opened_at` and `closed_at` |
| `sla_days` | Approve 3, Pending Documents 5, Manual Review 7, Enhanced Due Diligence 10, Reject 3; `sla_breached` = `tat_days > sla_days` |

Draw order (so results are reproducible): cases sorted by `case_id`, then offsets, analysts, channels and handling times are drawn as whole vectors in that order. Two runs give identical output (tested), and the output does not depend on input row order (tested).

**Resulting values (full data):** average turnaround 4.61 d, p90 12.31 d, SLA breach 25.0%, 503 open cases. The brief expected about 4.6 d, 25% and about 500.

Disclosure in the app: a purple SIMULATED pill on every visual and KPI card that uses these fields, a footnote under each simulated tile, a warning banner on the Operations page, "(SIMULATED)" in the date and channel slicer labels, and the parameter table on the Model and method page.

What the simulation can and cannot say: patterns such as "High-risk cases take longer" or "the volume curve rises" are consequences of the parameters above, not findings. The dashboard says so in the insight text. Analyst differences are noise from uniform random assignment; the insight strip labels the analyst breach-rate spread as flat.

## 3. Rule-engine reconciliation

The decision policy was recovered by cross-tabulating the labelled decision against the screening flags (notebook §3):

1. `SanctionStatus = Yes` → **Reject**
2. else `PEPStatus = Yes` → **Enhanced Due Diligence**
3. else `RiskCategory = High` → **EDD or Manual Review** (≈50/50; no field explains which, so either counts as agreement)
4. else fewer than 4 verified documents → **Pending Documents**
5. else **Approve**

`fact_case.engine_agrees` is TRUE for 100% of the 100,000 cases. The same engine is implemented in Python (`app/kpis.py::engine_decision`) for the what-if simulator; `tests/test_rules.py` proves the SQL CASE and the Python function agree on every combination of inputs (2 × 2 × 3 × 6) and on every real case.

## 4. Control-breach logic

A breach is an approval where a verification control failed: identity unverified, address unverified, or (a weaker signal the policy explicitly allows) fewer than 5 verified documents. The headline KPI uses identity OR address: **47,157 of 63,001 approvals (74.9%)**. Because the verification flags are ~50% in every decision class, they play no role in the decision logic; the finding is a **control gap** (the controls are not wired into the decision), not an error in the logic that exists.

## 5. ML honesty

The labels are produced by a deterministic rule engine, so no model can "predict KYC decisions" in any meaningful sense; it can only re-learn the rules. Two experiments make this explicit (`ml/decision_model.py`, `HistGradientBoostingClassifier(random_state=42)`, stratified 80/20 split):

| Experiment | Features | Accuracy | Majority baseline | Reading |
|---|---|---|---|---|
| A | all 13 features, including PEP, sanction and risk tier | **95.5%** | 63.0% | Re-learns the policy. 100% of the test errors are EDD ↔ Manual Review confusions among High-risk escalations, which the data splits at random. |
| B | without PEP, sanction and risk tier (10 features) | **64.5%** | 63.0% | +1.5 pp. The only lift comes from AMLFlag and verified documents, which are policy inputs themselves (every High-risk non-PEP non-sanctioned case has AMLFlag = Yes). Country, occupation, income, age, gender and account type add nothing. |

Permutation importance in A ranks risk tier, sanction, verified documents and PEP at the top — exactly the policy's four inputs. SHAP (TreeExplainer) is reported only because it passes a local-accuracy (additivity) check against the model's raw scores; with native categorical splits it failed that check, so categoricals are ordinal-coded instead (see `docs/decisions.md`).

**The finding: a model cannot beat the policy, and here is the proof.** The dashboard never presents ML as a decision predictor.

The additive **risk score** in Customer 360 (sanction 100, PEP 30, High risk 25, identity unverified 10, address unverified 10, 5 per unverified document, capped at 100) is an illustration of a transparent score card, **not a calibrated model**.

## 6. AI copilot evaluation

Hallucination rate = hallucinated answers / all answers in `benchmark_dataset.csv` (150,000 answers, 66.7% hallucinated). Once customer IDs are masked (`regexp_replace(GeneratedAnswer, 'C[0-9]+', 'C#', 'g')`) the generated answers collapse to 25 templates, so the detector (a transparent, reference-grounded rule set in `etl/ai_qa_marts.py`) scores 100% precision and recall per type **by construction**. The page states this prominently. Severity exists only for hallucinated answers, so it is shown as a distribution within each type (evenly spread), not as a rate.

## 7. Limitations

* Simulated operations fields (above) — not evidence about real throughput or staff.
* Synthetic data: flat distributions for country, occupation, income and age; gender does not match names; documents all expire 2027–2036.
* The periodic-review rule (365 days) is a common industry cadence applied uniformly; real programmes vary cadence by risk tier.
* The 90% "reviewed in last 12 months" gauge target is illustrative, not from the data.
* The AI benchmark cannot measure a real copilot; a real evaluation needs varied answers and human-labelled claims.
* The additive risk score is illustrative.

## 8. Reproducibility

One command per stage (`make etl`, `make ml`, `make test`, `make app`), fixed seed 42, pinned dependencies, `--raw-dir` / `--out-dir` arguments, a deterministic 1,000-customer sample for CI, and a data-quality report that fails the build on any `fail`.
