# Interview Q&A (20 questions)

**1. What is the project in one sentence?**
A Power BI-style Streamlit dashboard over 100,000 synthetic KYC onboarding cases, backed by a tested DuckDB warehouse, that joins operational speed with control assurance and shows that the decision logic is 100% policy-compliant while 74.9% of approvals skipped a failed identity or address check.

**2. What is the headline finding and why do you call it a control gap, not a logic error?**
A five-rule engine reproduces 100% of labelled decisions, so the logic that exists is applied consistently. But identity and address verification are ~50% "No" in every decision class — they are simply not inputs to the decision. 47,157 of 63,001 approvals carry at least one failed flag. The fix is to add a control (make verification a hard gate), not to repair the existing logic.

**3. How did you validate the rule engine?**
I recovered the precedence by cross-tabulating the label against the flags, wrote it as a `CASE` in `sql/02_model.sql` with an `engine_agrees` flag, and required 100%. I mirrored it in Python for the what-if simulator, and a test runs both on every combination of inputs (2×2×3×6) and on every real case. The only ambiguity — High-risk escalations split ~50/50 between EDD and Manual Review with no explanatory field — is modelled explicitly as "Escalate (EDD/Manual)".

**4. Why DuckDB and Parquet marts instead of Postgres or a live database?**
It is an analytical, read-only workload over ~600 MB of CSV. DuckDB builds the whole warehouse in about 30 seconds in-process, speaks rich SQL (FILTER, UNPIVOT, QUALIFY, GROUPING SETS), and writes zstd Parquet. The app then reads 2.7 MB of marts through lazy DuckDB views: no server, no credentials, fits Streamlit Cloud's free tier, and every query is cached.

**5. Why is the simulation honest?**
Because it is disclosed and contained. The source has no timestamps, analysts, channels or SLAs, so I generated them with a fixed seed and published parameters, stored them only in `sim_case_ops`, labelled every visual that uses them with a SIMULATED pill and footnote, put "(SIMULATED)" on the date and channel slicers, and wrote insight text that attributes patterns to the parameters ("High risk multiplies handling time by construction") rather than presenting them as findings.

**6. Why don't you claim the ML model predicts KYC decisions?**
Because the labels are a deterministic function of four inputs. Experiment A (all features) gets 95.5%, and every error is the random EDD/Manual split. Experiment B (without PEP, sanction, risk) gets 64.5% versus a 63.0% majority baseline, and its lift comes only from AMLFlag and document counts, which are policy inputs. The honest conclusion is "a model cannot beat the policy" — the page exists to prove that.

**7. How did you check that SHAP was trustworthy?**
I test SHAP's local accuracy: base value plus the sum of SHAP values must reproduce the model's raw scores. With native categorical splits it failed, so I ordinal-encoded categoricals; now it passes and SHAP ranks the same policy inputs on top as permutation importance. If the check fails, the pipeline records "SHAP skipped" instead of showing numbers.

**8. What did profiling find that the brief did not mention?**
DocumentID is not unique (13,533 surplus rows reuse IDs across customers), Age is computed at the extract date 2026-06-24 not the snapshot date (1,693 differ), the risk tier is derived from PEP/sanction/AML flags, and the review-overdue count in the brief (49,828) is correct only at the extract date — at AS_OF it is 50,620. All are in `known_data_issues.md` and the DQ report.

**9. How do you make sure numbers in the README and docs are not stale?**
The claims table (`mart_claims_check`) recomputes 74 facts from the brief on every build, and a test recomputes the README's headline figures from the committed marts and fails if they are missing. Page text is generated from queries, including flat/not-flat wording.

**10. How do you handle charts where nothing is going on?**
A computed rule: if the max–min spread of a rate across groups is under a threshold (2 pp by default), the chart gets a red "FLAT" label and the insight says "no meaningful difference". Country, occupation, income and age are all flat here, and the dashboard says so instead of inventing stories.

**11. How is SQL injection prevented?**
All SQL goes through `app/data.py::query(sql, params)` with `?` placeholders; `where_clause(filters)` builds placeholders and a parameter tuple. Column names in dynamic SQL come only from whitelists. Keyword search uses `ILIKE '%' || ? || '%'`. A test passes a hostile country value and asserts it appears only in the parameters.

**12. How would you secure PII in a real deployment?**
Keep PII out of analytical marts (as here: no names, DOB, document numbers or OCR text), tokenise customer IDs, enforce role-based access (operations vs compliance), mask Customer 360 for non-privileged roles, cap and log exports, encrypt at rest and in transit, and keep the raw zone in a restricted account with retention policies. Row-level security in the warehouse would enforce it centrally.

**13. How would the design change with real timestamps?**
Replace `sim_case_ops` with a case-event log (opened, assigned, document requested, decided). Turnaround would come from events, and I could add queue time vs work time, rework loops, SLA pause states, and survival analysis for open cases. The marts and pages stay the same shape; the SIMULATED badges disappear.

**14. How would you monitor drift?**
Daily DQ checks become alerts: rule-engine agreement must stay 100% (a drop means policy changed or labels are wrong), approval and breach rates by segment tracked with control limits, PSI on input distributions (risk mix, document fail rate, OCR confidence), and the claims table turned into expectations. For the copilot, track hallucination rate on a rotating human-labelled sample.

**15. Why Streamlit rather than Power BI?**
The brief asked for a Power BI look in an open, reviewable stack: one link, code in GitHub, CI. I reproduced Power BI behaviours explicitly: report-level slicers in session state, KPI cards with coloured deltas, click-to-cross-filter, drill-through dialogs, reset, tooltips and insight strips.

**16. What was technically hard in Streamlit?**
Three things: slicer state across pages (widget state is dropped on navigation, so I keep canonical keys and sync them), cross-filtering (Plotly pie slices emit no selection events, so the donut is built from scatter markers; chart keys carry a nonce so a click applies once), and drill-through (the table selection is cleared by a key nonce so the dialog opens once).

**17. How is the project tested?**
86 pytest tests: rule reconciliation, key uniqueness, lossless joins, document consistency, no approved sanctioned customer, simulation ordering and seed reproducibility, KPI functions on a hand-built fixture and SQL-equals-Python, marts schema and privacy, AI detector rules, and an AppTest that renders all 13 pages and proves a slicer changes KPIs. They assert invariants, so they pass on the 1,000-customer sample in CI and on the full data.

**18. How did you evaluate the AI copilot, and what is the limitation?**
Hallucination rate by type, severity and question template, plus a transparent reference-grounded detector with a confusion matrix. The limitation is the data: 150,000 answers collapse to 25 templates, so the detector is perfect by construction and the rate is flat by question. I say this on the page and recommend a real evaluation with varied, human-labelled answers.

**19. What would you do next?**
Wire identity/address verification into the decision as a hard gate and add a regression test; move to Postgres + dbt with dbt tests; real event timestamps; role-based access; and a risk-based review cadence (High risk yearly, Low risk every three years) instead of a flat 365 days.

**20. What trade-offs did you make?**
Default date range is all dates (headline stability) at the cost of deltas showing n/a on first load; slicers do not apply to non-case datasets (honesty over uniformity); the donut is marker-based (interactivity over pixel-perfect arcs); SHAP only when verified (fewer charts, more trust).
