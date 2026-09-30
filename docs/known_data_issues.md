# Known data issues and claimed-vs-measured check

This file has two parts: (1) every fact the project brief asserted, recomputed from the data by
`etl/quality_checks.py` (table `mart_claims_check`, also shown on the Data quality page), and (2) every trap in
the data with how the pipeline handles it. Both are regenerated from the marts; nothing here is typed in by hand
except the explanations.

## 1. Claimed vs measured (73 of 74 match)

| ID | Claim | Claimed | Measured | Match |
|---|---|---|---|---|
| C01 | Rule engine reconciles with labelled decisions (%) | 100% | 100 | yes |
| C02 | Approved customers | 63,001 | 63,001 | yes |
| C03 | Approved with IdentityVerified = No | 31,377 | 31,377 | yes |
| C04 | Approved with identity or address unverified | 47,157 | 47,157 | yes |
| C05 | Share of approvals with identity or address unverified (%) | 74.9% | 74.9 | yes |
| C06 | Profiles more than 12 months old at 2026-06-30 | 49,828 | 50,620 | **NO** |
| C06b | Profiles more than 365 days old at the extract date (max LastUpdated) | 49,828 | 49,828 | yes |
| C07 | Decision Enhanced Due Diligence | 23,121 | 23,121 | yes |
| C08 | Decision Reject | 7,877 | 7,877 | yes |
| C09 | Decision Manual Review | 4,577 | 4,577 | yes |
| C10 | Decision Pending Documents | 1,424 | 1,424 | yes |
| C11 | PEP = Yes | 20,030 | 20,030 | yes |
| C12 | Sanction = Yes | 7,877 | 7,877 | yes |
| C13 | Risk tier High | 35,575 | 35,575 | yes |
| C14 | Risk tier Medium | 36,671 | 36,671 | yes |
| C15 | Risk tier Low | 27,754 | 27,754 | yes |
| C16 | Countries (each about 20%) | 5 | 5 | yes |
| C17 | Largest country share (%) | about 20% | 20.12 | yes |
| C18 | Smallest country share (%) | about 20% | 19.85 | yes |
| C19 | Account types | 4 | 4 | yes |
| C20 | Occupations | 10 | 10 | yes |
| C21 | Verified documents | 475,052 | 475,052 | yes |
| C22 | Unverified documents | 24,948 | 24,948 | yes |
| C23 | Lowest document-type fail rate (%) | about 5% | 4.9 | yes |
| C24 | Highest document-type fail rate (%) | about 5% | 5.08 | yes |
| C25 | OCR confidence minimum | 0.80 | 0.8 | yes |
| C26 | OCR confidence maximum | 0.99 | 0.99 | yes |
| C27 | OCR confidence mean | 0.895 | 0.895 | yes |
| C28 | Cases with VerifiedDocuments = 5 | 77,387 | 77,387 | yes |
| C29 | Cases with VerifiedDocuments = 4 | 20,414 | 20,414 | yes |
| C30 | Cases with VerifiedDocuments = 3 | 2,068 | 2,068 | yes |
| C31 | Cases with VerifiedDocuments = 2 | 126 | 126 | yes |
| C32 | Cases with VerifiedDocuments = 1 | 5 | 5 | yes |
| C33 | VerifiedDocuments equals verified document rows (% of customers) | 100% | 100 | yes |
| C34 | Funnel: passed sanctions | 92,123 | 92,123 | yes |
| C35 | Funnel: passed PEP | 73,648 | 73,648 | yes |
| C36 | Funnel: passed risk | 64,425 | 64,425 | yes |
| C37 | High-risk non-PEP escalations sent to EDD (%) | about 50% | 50.37 | yes |
| C38 | Lowest sanction rate by country (%) | 7.6% | 7.6 | yes |
| C39 | Highest sanction rate by country (%) | 8.2% | 8.2 | yes |
| C40 | Minimum income | 200k | 200,012 | yes |
| C41 | Maximum income | 10M | 9,999,911 | yes |
| C42 | IdentityVerified = Yes (%) | about 50% | 50.26 | yes |
| C43 | AddressVerified = Yes (%) | about 50% | 50 | yes |
| C44 | Earliest document expiry year | 2027 | 2,027 | yes |
| C45 | Latest document expiry year | 2036 | 2,036 | yes |
| C46 | Distinct masked generated-answer templates | 25 | 25 | yes |
| C47 | Lowest hallucination % by question template | 66.5% | 66.5 | yes |
| C48 | Highest hallucination % by question template | 66.9% | 66.9 | yes |
| C49 | Faithful benchmark answers | 50,000 | 50,000 | yes |
| C50 | Hallucinated benchmark answers | 100,000 | 100,000 | yes |
| C51 | Smallest hallucination type (answers) | about 20,000 | 19,859 | yes |
| C52 | Largest hallucination type (answers) | about 20,000 | 20,069 | yes |
| C53 | Rules without a guideline | about 117 | 117 | yes |
| C54 | Rule categories | 7 | 7 | yes |
| C55 | SIMULATED average turnaround (days) | about 4.6 | 4.61 | yes |
| C56 | SIMULATED SLA breach (%) | about 25% | 25 | yes |
| C57 | SIMULATED open cases | about 500 | 503 | yes |
| F00 | Raw CSV files in archive | 14 | 14 | yes |
| F01 | Raw CSV size (MB, decimal) | about 645 MB | 623.3 | yes |
| F02 | Rows in customer_profiles.csv | 100,000 | 100,000 | yes |
| F03 | Rows in kyc_cases.csv | 100,000 | 100,000 | yes |
| F04 | Rows in customer_documents.csv | 500,000 | 500,000 | yes |
| F05 | Rows in aml_rules.csv | 3,000 | 3,000 | yes |
| F06 | Rows in kyc_guidelines.csv | 10,000 | 10,000 | yes |
| F07 | Rows in benchmark_dataset.csv | 150,000 | 150,000 | yes |
| F08 | Rows in hallucinated_answers.csv | 100,000 | 100,000 | yes |
| F09 | Rows in ground_truth_answers.csv | 500,000 | 500,000 | yes |
| F10 | Rows in kyc_questions.csv | 500,000 | 500,000 | yes |
| F11 | Rows in hallucination_labels.csv | 100k to 200k | 100,000 | yes |
| F12 | Rows in hallucination_training_dataset.csv | 100k to 200k | 150,000 | yes |
| F13 | Rows in hallucination_training_dataset_v2.csv | 100k to 200k | 150,000 | yes |
| F14 | Rows in nli_dataset.csv | 100k to 200k | 200,000 | yes |
| F15 | Rows in nli_dataset_dedup.csv | 100k to 200k | 162,722 | yes |

### Differences explained

* **C06 — profiles more than 12 months old at 2026-06-30.** The brief says 49,828; the data gives **50,620** at the
  dashboard's AS_OF (2026-06-30, rule: `last_updated` more than 365 days before AS_OF). The brief's figure is the
  count at the data's **extract date, 2026-06-24** (the latest `LastUpdated`), which C06b reproduces exactly
  (49,828). Customers whose last review fell between 2025-06-24 and 2025-06-29 crossed the 365-day line in the six
  days between the two dates. The dashboard uses AS_OF consistently for every time-based metric.
* **F01 — raw size.** The 14 CSVs total 623.3 MB in decimal megabytes (594 MiB); the brief's "about 645 MB" is within
  the ±5% tolerance used, so it is marked as a match, but the exact figure is 623.3 MB.
* **ML accuracy (reported by `ml/decision_model.py`, `mart_ml_results`).** The brief expected about 95.4% (experiment A)
  and about 64.3% (experiment B) against a 63.0% baseline. Measured: **95.5%** (0.9545) and **64.5%** (0.6455) against
  **63.0%**. The small differences come from the estimator configuration (ordinal-coded categoricals so SHAP can
  explain the trees, see `docs/decisions.md`).

## 2. Traps in the data and how they are handled

| # | Issue (verified by profiling) | Evidence | Handling |
|---|---|---|---|
| 1 | **No case timestamps, analysts, channels or SLA fields.** Turnaround, SLA and workload cannot be measured. | `kyc_cases.csv` has only case attributes and the labelled decision. | A seeded **simulated operations layer** (`sim_case_ops`, seed 42, parameters in `etl/build_warehouse.py`) is stored separately and every visual using it carries a SIMULATED badge and footnote. The date slicer is labelled "Opened date (SIMULATED)". |
| 2 | **IdentityVerified and AddressVerified are ~50/50 and unrelated to the decision.** | 50.3% / 50.0% verified overall and ~50% inside every decision class (notebook §4). | Reported as the headline **control-breach finding**, not hidden: 47,157 of 63,001 approvals (74.9%) have identity or address unverified. |
| 3 | **Country, occupation, income and age carry no signal.** | Sanction rate 7.6%–8.2% by country; income uniform 200k–10M in every occupation with no currency. | Charts compute a max–min spread and print "FLAT …" plus an insight sentence; no story is invented. Income is shown only as quintiles. |
| 4 | **Gender does not match names**; names and IDs are synthetic. | e.g. "Michael Ray", Female (C000000). | Names, DOB and document numbers stay in staging and are **never exported** to marts (tested). Gender is not visualised. |
| 5 | **Documents all expire 2027–2036.** | `MIN/MAX(ExpiryDate)` = 2027-06-25 / 2036-06-23. | "Expired documents" is not a metric. OCR confidence (< 0.85) and verification failure are used instead. |
| 6 | **`kyc_guidelines.EffectiveDate` is dd-mm-yyyy.** | e.g. `08-01-2023` for GUIDE_00001. | Parsed with `dateformat='%d-%m-%Y'` and `types={'EffectiveDate':'DATE'}`; a test asserts GUIDE_00001 = 2023-01-08. |
| 7 | **AI answers reduce to 25 templates** once IDs are masked; hallucination is a flat 66.5%–66.9% per question and severity is evenly spread. | `COUNT(DISTINCT regexp_replace(GeneratedAnswer,'C[0-9]+','C#'))` = 25. | The detector's ~100% scores are labelled "by construction"; only 25 masked examples are shipped; raw answer text is never exported. |
| 8 | **DuckDB auto-casts Yes/No to BOOLEAN.** | `DESCRIBE` shows BOOLEAN for PEPStatus etc. | Relied on deliberately (`WHERE is_pep`), with explicit `CAST(PEPStatus AS BOOLEAN)` in staging so the type is guaranteed. |
| 9 | **DocumentID is not unique** (found during profiling, not in the brief). | 13,533 surplus rows: 12,947 IDs appear twice, 287 three times, 4 four times — always for *different* customers. | The document key is `(customer_id, doc_type)` (unique, tested). DocumentID duplicates are a documented `warn` in `mart_dq_report`. |
| 10 | **Age is as of the extract date (2026-06-24), not AS_OF** (found during profiling). | Age matches DOB exactly at 2026-06-24; 1,693 customers had a birthday between 2026-06-24 and 2026-06-30. | Source Age is used for age bands; the DQ check accepts age at either date and reports the 1,693 as a `warn`. |
| 11 | **Risk tier is partly derived from PEP/sanction** (found during profiling). | 100% of PEP or sanctioned customers are High risk; 100% of High-risk non-PEP non-sanctioned customers have AMLFlag = Yes. | Stated on the Risk and Model pages; explains why experiment B's only lift comes from AMLFlag and verified documents. |
| 12 | **EDD vs Manual Review for High-risk escalations is ~50/50** with no explanatory field. | 4,646 EDD vs 4,577 Manual Review (50.4% / 49.6%). | The rule engine returns "Escalate (EDD/Manual)" and treats either label as compliant; this is the only source of error in ML experiment A. |
| 13 | **Benchmark AnswerIDs repeat.** 150,000 rows but 100,000 AnswerIDs: each faithful answer reuses the AnswerID of a hallucinated one. | Join on AnswerID gives 150,000 rows. | Severity is joined only for hallucinated rows (`ON answer_id AND is_hallucinated`). |
| 14 | **The rule library is templated.** | 3,000 rules but 15 distinct rule texts; 10,000 guidelines but 75 distinct paragraphs. | Stated on the Rules page so keyword-search results are not mistaken for 3,000 distinct policies. 117 rules (3.9%) have no guideline (ANTI JOIN). |
| 15 | **OCRText is ~100 MB of free text.** | `customer_documents.csv` is 99 MB. | Never read (projection in staging), never in marts, samples or Git. |
