# Data dictionary

Every column of every staging table, model table and mart. Types come from the DuckDB warehouse (or the Parquet file for marts written outside SQL). Columns marked **SIM** are produced by the seeded simulation (seed 42) because the source has no timestamps, analysts, channels or SLAs.

Rows are for the full data build (`python etl/build_warehouse.py`).

## Staging (sql/01_staging.sql, etl/ai_qa_marts.py) - warehouse only, not exported

### `stg_customers` (100,000 rows)

| Column | Type | Description |
|---|---|---|
| `customer_id` | VARCHAR | CustomerID (synthetic) |
| `full_name` | VARCHAR | Full name (synthetic; never exported to marts) |
| `dob` | DATE | Date of birth (synthetic; never exported to marts) |
| `age` | INTEGER | Age in completed years as of the data extract date (source column) |
| `gender` | VARCHAR | Gender (does not match names; synthetic) |
| `nationality` | VARCHAR | Nationality |
| `country` | VARCHAR | Customer country (5 values) |
| `occupation` | VARCHAR | Occupation (10 values) |
| `income` | BIGINT | Income (no currency in the source; uniform 200k-10M) |
| `tax_resident` | VARCHAR | Tax residence country |
| `is_pep` | BOOLEAN | PEPStatus (BOOLEAN) |
| `is_sanctioned` | BOOLEAN | SanctionStatus (BOOLEAN) |
| `address_verified` | BOOLEAN | AddressVerified flag from the profile (Yes/No → BOOLEAN) |
| `identity_verified` | BOOLEAN | IdentityVerified flag (Yes/No → BOOLEAN) |
| `risk_category` | VARCHAR | Risk tier (Low/Medium/High) |
| `aml_flag` | BOOLEAN | AMLFlag from the source (Yes/No → BOOLEAN) |
| `account_type` | VARCHAR | Account type (Business, Current, Salary, Savings) |
| `last_updated` | DATE | Profile LastUpdated (last periodic review) |

### `stg_cases` (100,000 rows)

| Column | Type | Description |
|---|---|---|
| `case_id` | VARCHAR | CaseID (one case per customer) |
| `customer_id` | VARCHAR | CustomerID (synthetic) |
| `country` | VARCHAR | Customer country (5 values) |
| `occupation` | VARCHAR | Occupation (10 values) |
| `income` | BIGINT | Income (no currency in the source; uniform 200k-10M) |
| `is_pep` | BOOLEAN | PEPStatus (BOOLEAN) |
| `is_sanctioned` | BOOLEAN | SanctionStatus (BOOLEAN) |
| `risk_category` | VARCHAR | Risk tier (Low/Medium/High) |
| `aml_flag` | BOOLEAN | AMLFlag from the source (Yes/No → BOOLEAN) |
| `verified_docs` | INTEGER | VerifiedDocuments from kyc_cases (0-5) |
| `decision` | VARCHAR | Labelled decision (ExpectedDecision) |
| `decision_reason` | VARCHAR | Labelled DecisionReason |

### `stg_documents` (500,000 rows)

| Column | Type | Description |
|---|---|---|
| `document_id` | VARCHAR | DocumentID (not unique across customers; see known issues) |
| `customer_id` | VARCHAR | CustomerID (synthetic) |
| `doc_type` | VARCHAR | Document type (Passport, PAN, Aadhaar, Driving License, Utility Bill) |
| `document_number` | VARCHAR | Document number (synthetic; never exported to marts) |
| `issue_country` | VARCHAR | Document issuing country |
| `expiry_date` | DATE | Document expiry date |
| `is_verified` | BOOLEAN | Document verified (BOOLEAN) |
| `confidence` | DOUBLE | OCR confidence (0.80-0.99) |
| `source` | VARCHAR | Document Source (always "Synthetic") |

### `stg_rules` (3,000 rows)

| Column | Type | Description |
|---|---|---|
| `rule_id` | VARCHAR | RuleID |
| `rule_title` | VARCHAR | Rule title |
| `rule_category` | VARCHAR | Rule category (7 values) |
| `rule_text` | VARCHAR | Rule text (policy text) |
| `jurisdiction` | VARCHAR | Rule country (UK, USA, India, Global) |
| `priority` | VARCHAR | Rule priority (Low/Medium/High/Critical) |
| `version` | VARCHAR | Rule or guideline version |

### `stg_guidelines` (10,000 rows)

| Column | Type | Description |
|---|---|---|
| `guideline_id` | VARCHAR | GuidelineID |
| `rule_id` | VARCHAR | RuleID |
| `section` | VARCHAR | Guideline section |
| `paragraph` | VARCHAR | Guideline paragraph text (policy text, no PII) |
| `version` | VARCHAR | Rule or guideline version |
| `effective_date` | DATE | Guideline effective date (parsed from dd-mm-yyyy) |

### `stg_benchmark` (150,000 rows)

| Column | Type | Description |
|---|---|---|
| `benchmark_id` | VARCHAR | BenchmarkID |
| `answer_id` | VARCHAR | AnswerID of the benchmark answer |
| `customer_id` | VARCHAR | CustomerID (synthetic) |
| `question_template` | VARCHAR | Question with customer IDs masked (C#) |
| `ground_truth_masked` | VARCHAR | Ground-truth answer with IDs masked |
| `generated_masked` | VARCHAR | Generated answer with customer IDs masked as C# |
| `len_diff_chars` | BIGINT | Characters of generated answer minus ground truth |
| `hallucination_type` | VARCHAR | Hallucination type (NONE = faithful) |
| `is_hallucinated` | BOOLEAN | Hallucinated flag |
| `expected_label` | INTEGER | ExpectedLabel (1 = hallucinated) |

### `stg_hallucinated` (100,000 rows)

| Column | Type | Description |
|---|---|---|
| `hallucination_id` | VARCHAR | HallucinationID |
| `answer_id` | VARCHAR | AnswerID of the benchmark answer |
| `hallucination_type` | VARCHAR | Hallucination type (NONE = faithful) |
| `severity` | VARCHAR | Hallucination severity (Low/Medium/High/Critical; n/a for faithful answers) |
| `is_hallucinated` | BOOLEAN | Hallucinated flag |

## Simulated operations layer (etl/build_warehouse.py) - SIMULATED, warehouse only

### `sim_case_ops` (100,000 rows)

| Column | Type | Description |
|---|---|---|
| `case_id` | VARCHAR | CaseID (one case per customer) |
| `opened_at` | TIMESTAMP | SIMULATED open timestamp: AS_OF minus int(beta(1.3,2.2)*730) days **SIM** |
| `closed_at` | TIMESTAMP_NS | SIMULATED close timestamp (opened_at + handling time, clipped to AS_OF) **SIM** |
| `handling_days` | DOUBLE | SIMULATED lognormal handling time in days **SIM** |
| `tat_days` | DOUBLE | SIMULATED turnaround in days (opened_at to closed_at) **SIM** |
| `sla_days` | BIGINT | SLA target by decision: Approve 3, Pending 5, Manual 7, EDD 10, Reject 3 (policy assumption) **SIM** |
| `sla_breached` | BOOLEAN | SIMULATED: tat_days > sla_days **SIM** |
| `is_open` | BOOLEAN | SIMULATED: case still open at AS_OF **SIM** |
| `assigned_to` | VARCHAR | SIMULATED analyst (Analyst_01..Analyst_24, uniform) **SIM** |
| `channel` | VARCHAR | SIMULATED intake channel (Web 40%, Branch 25%, Mobile 25%, Partner 10%) **SIM** |

## Model (sql/02_model.sql) - warehouse only

### `dim_date` (1,096 rows)

| Column | Type | Description |
|---|---|---|
| `date_key` | DATE | Calendar date |
| `year` | BIGINT | Calendar year |
| `quarter` | BIGINT | Calendar quarter |
| `month` | BIGINT | Month number |
| `year_month` | VARCHAR | YYYY-MM |
| `month_start` | DATE | First day of month |
| `day_of_week` | BIGINT | Day of week (0 = Sunday) |
| `is_weekend` | BOOLEAN | Saturday or Sunday |

### `dim_customer` (100,000 rows)

| Column | Type | Description |
|---|---|---|
| `customer_id` | VARCHAR | CustomerID (synthetic) |
| `full_name` | VARCHAR | Full name (synthetic; never exported to marts) |
| `dob` | DATE | Date of birth (synthetic; never exported to marts) |
| `age` | INTEGER | Age in completed years as of the data extract date (source column) |
| `age_band` | VARCHAR | Age band 18-24 / 25-34 / 35-49 / 50-64 / 65+ |
| `gender` | VARCHAR | Gender (does not match names; synthetic) |
| `nationality` | VARCHAR | Nationality |
| `country` | VARCHAR | Customer country (5 values) |
| `occupation` | VARCHAR | Occupation (10 values) |
| `income` | BIGINT | Income (no currency in the source; uniform 200k-10M) |
| `income_quintile` | BIGINT | NTILE(5) of income (ties broken by customer_id) |
| `tax_resident` | VARCHAR | Tax residence country |
| `is_pep` | BOOLEAN | PEPStatus (BOOLEAN) |
| `is_sanctioned` | BOOLEAN | SanctionStatus (BOOLEAN) |
| `address_verified` | BOOLEAN | AddressVerified flag from the profile (Yes/No → BOOLEAN) |
| `identity_verified` | BOOLEAN | IdentityVerified flag (Yes/No → BOOLEAN) |
| `risk_category` | VARCHAR | Risk tier (Low/Medium/High) |
| `aml_flag` | BOOLEAN | AMLFlag from the source (Yes/No → BOOLEAN) |
| `account_type` | VARCHAR | Account type (Business, Current, Salary, Savings) |
| `last_updated` | DATE | Profile LastUpdated (last periodic review) |
| `days_since_review` | BIGINT | Days between last_updated and AS_OF (2026-06-30) |
| `review_overdue` | BOOLEAN | last_updated more than 365 days before AS_OF |

### `dim_rule` (3,000 rows)

| Column | Type | Description |
|---|---|---|
| `rule_id` | VARCHAR | RuleID |
| `rule_title` | VARCHAR | Rule title |
| `rule_category` | VARCHAR | Rule category (7 values) |
| `rule_text` | VARCHAR | Rule text (policy text) |
| `jurisdiction` | VARCHAR | Rule country (UK, USA, India, Global) |
| `priority` | VARCHAR | Rule priority (Low/Medium/High/Critical) |
| `priority_rank` | INTEGER | 1 = Critical, 2 = High, 3 = Medium, 4 = Low |
| `version` | VARCHAR | Rule or guideline version |
| `n_guidelines` | BIGINT | Guidelines implementing the rule (LEFT JOIN count) |
| `is_orphan` | BOOLEAN | Rule has no guideline |

### `fact_document` (500,000 rows)

| Column | Type | Description |
|---|---|---|
| `document_id` | VARCHAR | DocumentID (not unique across customers; see known issues) |
| `customer_id` | VARCHAR | CustomerID (synthetic) |
| `doc_type` | VARCHAR | Document type (Passport, PAN, Aadhaar, Driving License, Utility Bill) |
| `issue_country` | VARCHAR | Document issuing country |
| `expiry_date` | DATE | Document expiry date |
| `is_verified` | BOOLEAN | Document verified (BOOLEAN) |
| `confidence` | DOUBLE | OCR confidence (0.80-0.99) |
| `low_confidence` | BOOLEAN | Confidence < 0.85 |
| `source` | VARCHAR | Document Source (always "Synthetic") |

### `fact_case` (100,000 rows)

| Column | Type | Description |
|---|---|---|
| `case_id` | VARCHAR | CaseID (one case per customer) |
| `customer_id` | VARCHAR | CustomerID (synthetic) |
| `country` | VARCHAR | Customer country (5 values) |
| `occupation` | VARCHAR | Occupation (10 values) |
| `income` | BIGINT | Income (no currency in the source; uniform 200k-10M) |
| `is_pep` | BOOLEAN | PEPStatus (BOOLEAN) |
| `is_sanctioned` | BOOLEAN | SanctionStatus (BOOLEAN) |
| `risk_category` | VARCHAR | Risk tier (Low/Medium/High) |
| `aml_flag` | BOOLEAN | AMLFlag from the source (Yes/No → BOOLEAN) |
| `verified_docs` | INTEGER | VerifiedDocuments from kyc_cases (0-5) |
| `doc_rows` | BIGINT | Document rows for the customer |
| `verified_doc_rows` | BIGINT | Verified document rows recounted from documents |
| `decision` | VARCHAR | Labelled decision (ExpectedDecision) |
| `decision_reason` | VARCHAR | Labelled DecisionReason |
| `engine_decision` | VARCHAR | Rule-engine outcome (Reject, Enhanced Due Diligence, Escalate (EDD/Manual), Pending Documents, Approve) |
| `engine_rule` | VARCHAR | Rule that fired (R1-R5) |
| `engine_agrees` | BOOLEAN | Engine outcome equals the label (Escalate matches EDD or Manual Review) |
| `identity_verified` | BOOLEAN | IdentityVerified flag (Yes/No → BOOLEAN) |
| `address_verified` | BOOLEAN | AddressVerified flag from the profile (Yes/No → BOOLEAN) |
| `account_type` | VARCHAR | Account type (Business, Current, Salary, Savings) |
| `age_band` | VARCHAR | Age band 18-24 / 25-34 / 35-49 / 50-64 / 65+ |
| `income_quintile` | BIGINT | NTILE(5) of income (ties broken by customer_id) |
| `review_overdue` | BOOLEAN | last_updated more than 365 days before AS_OF |
| `days_since_review` | BIGINT | Days between last_updated and AS_OF (2026-06-30) |
| `last_updated` | DATE | Profile LastUpdated (last periodic review) |
| `breach_approved_no_identity` | BOOLEAN | Approved although identity is unverified |
| `breach_approved_no_address` | BOOLEAN | Approved although address is unverified |
| `breach_approved_missing_doc` | BOOLEAN | Approved with fewer than 5 verified documents |
| `breach_approved_id_or_address` | BOOLEAN | Approved although identity OR address is unverified (the control-breach KPI) |
| `any_kyc_breach` | BOOLEAN | Approved AND (identity unverified OR address unverified OR fewer than 5 verified documents) |
| `opened_at` | TIMESTAMP | SIMULATED open timestamp: AS_OF minus int(beta(1.3,2.2)*730) days **SIM** |
| `closed_at` | TIMESTAMP_NS | SIMULATED close timestamp (opened_at + handling time, clipped to AS_OF) **SIM** |
| `opened_date` | DATE | SIMULATED open date **SIM** |
| `opened_month` | DATE | SIMULATED open month **SIM** |
| `assigned_to` | VARCHAR | SIMULATED analyst (Analyst_01..Analyst_24, uniform) **SIM** |
| `channel` | VARCHAR | SIMULATED intake channel (Web 40%, Branch 25%, Mobile 25%, Partner 10%) **SIM** |
| `handling_days` | DOUBLE | SIMULATED lognormal handling time in days **SIM** |
| `tat_days` | DOUBLE | SIMULATED turnaround in days (opened_at to closed_at) **SIM** |
| `sla_days` | BIGINT | SLA target by decision: Approve 3, Pending 5, Manual 7, EDD 10, Reject 3 (policy assumption) **SIM** |
| `sla_breached` | BOOLEAN | SIMULATED: tat_days > sla_days **SIM** |
| `is_open` | BOOLEAN | SIMULATED: case still open at AS_OF **SIM** |

## Marts (sql/03_marts.sql) - exported to data/marts

### `mart_case_detail` (100,000 rows)

| Column | Type | Description |
|---|---|---|
| `case_id` | VARCHAR | CaseID (one case per customer) |
| `customer_id` | VARCHAR | CustomerID (synthetic) |
| `country` | VARCHAR | Customer country (5 values) |
| `occupation` | VARCHAR | Occupation (10 values) |
| `account_type` | VARCHAR | Account type (Business, Current, Salary, Savings) |
| `risk_category` | VARCHAR | Risk tier (Low/Medium/High) |
| `is_pep` | BOOLEAN | PEPStatus (BOOLEAN) |
| `is_sanctioned` | BOOLEAN | SanctionStatus (BOOLEAN) |
| `aml_flag` | BOOLEAN | AMLFlag from the source (Yes/No → BOOLEAN) |
| `decision` | VARCHAR | Labelled decision (ExpectedDecision) |
| `decision_reason` | VARCHAR | Labelled DecisionReason |
| `engine_decision` | VARCHAR | Rule-engine outcome (Reject, Enhanced Due Diligence, Escalate (EDD/Manual), Pending Documents, Approve) |
| `engine_rule` | VARCHAR | Rule that fired (R1-R5) |
| `engine_agrees` | BOOLEAN | Engine outcome equals the label (Escalate matches EDD or Manual Review) |
| `verified_docs` | INTEGER | VerifiedDocuments from kyc_cases (0-5) |
| `income_quintile` | BIGINT | NTILE(5) of income (ties broken by customer_id) |
| `age_band` | VARCHAR | Age band 18-24 / 25-34 / 35-49 / 50-64 / 65+ |
| `channel` | VARCHAR | SIMULATED intake channel (Web 40%, Branch 25%, Mobile 25%, Partner 10%) **SIM** |
| `assigned_to` | VARCHAR | SIMULATED analyst (Analyst_01..Analyst_24, uniform) **SIM** |
| `opened_date` | DATE | SIMULATED open date **SIM** |
| `opened_month` | DATE | SIMULATED open month **SIM** |
| `tat_days` | DOUBLE | SIMULATED turnaround in days (opened_at to closed_at) **SIM** |
| `sla_days` | BIGINT | SLA target by decision: Approve 3, Pending 5, Manual 7, EDD 10, Reject 3 (policy assumption) **SIM** |
| `sla_breached` | BOOLEAN | SIMULATED: tat_days > sla_days **SIM** |
| `is_open` | BOOLEAN | SIMULATED: case still open at AS_OF **SIM** |
| `breach_approved_no_identity` | BOOLEAN | Approved although identity is unverified |
| `breach_approved_no_address` | BOOLEAN | Approved although address is unverified |
| `breach_approved_missing_doc` | BOOLEAN | Approved with fewer than 5 verified documents |
| `breach_approved_id_or_address` | BOOLEAN | Approved although identity OR address is unverified (the control-breach KPI) |
| `any_kyc_breach` | BOOLEAN | Approved AND (identity unverified OR address unverified OR fewer than 5 verified documents) |
| `review_overdue` | BOOLEAN | last_updated more than 365 days before AS_OF |
| `days_since_review` | BIGINT | Days between last_updated and AS_OF (2026-06-30) |
| `last_updated` | DATE | Profile LastUpdated (last periodic review) |
| `identity_verified` | BOOLEAN | IdentityVerified flag (Yes/No → BOOLEAN) |
| `address_verified` | BOOLEAN | AddressVerified flag from the profile (Yes/No → BOOLEAN) |

### `mart_monthly_kpi` (822 rows)

| Column | Type | Description |
|---|---|---|
| `opened_month` | DATE | SIMULATED open month **SIM** |
| `decision` | VARCHAR | Labelled decision (ExpectedDecision) |
| `country` | VARCHAR | Customer country (5 values) |
| `risk_category` | VARCHAR | Risk tier (Low/Medium/High) |
| `cases` | BIGINT | Number of cases **SIM** |
| `avg_tat_days` | DOUBLE | Mean SIMULATED turnaround (days) **SIM** |
| `sla_breaches` | BIGINT | Count of SIMULATED SLA breaches **SIM** |
| `still_open` | BIGINT | SIMULATED open cases **SIM** |

### `mart_mom` (24 rows)

| Column | Type | Description |
|---|---|---|
| `opened_month` | DATE | SIMULATED open month **SIM** |
| `cases` | BIGINT | Number of cases **SIM** |
| `prev_cases` | BIGINT | Previous month cases (LAG) **SIM** |
| `cases_delta` | BIGINT | Cases minus previous month (LAG) **SIM** |
| `mom_pct` | DOUBLE | Month-over-month change in % **SIM** |
| `cases_ma3` | DOUBLE | 3-month moving average of cases **SIM** |
| `approval_rate` | DOUBLE | Approvals / cases |
| `breach_rate` | DOUBLE | Control breaches / approvals |
| `sla_breach_rate` | DOUBLE | SIMULATED SLA breaches / cases **SIM** |

### `mart_analyst` (24 rows)

| Column | Type | Description |
|---|---|---|
| `assigned_to` | VARCHAR | SIMULATED analyst (Analyst_01..Analyst_24, uniform) **SIM** |
| `cases` | BIGINT | Number of cases **SIM** |
| `avg_tat_days` | DOUBLE | Mean SIMULATED turnaround (days) **SIM** |
| `p90_tat_days` | DOUBLE | 90th percentile SIMULATED turnaround (quantile_cont) **SIM** |
| `sla_breaches` | BIGINT | Count of SIMULATED SLA breaches **SIM** |
| `high_risk_cases` | BIGINT | Cases with risk_category = High |
| `breach_pct` | DOUBLE | SIMULATED SLA breaches as % of cases **SIM** |
| `breach_rank` | BIGINT | RANK() by breach rate, 1 = worst **SIM** |

### `mart_funnel` (5 rows)

| Column | Type | Description |
|---|---|---|
| `stage_order` | INTEGER | Funnel stage order |
| `stage` | VARCHAR | Funnel stage |
| `cases` | BIGINT | Number of cases |

### `mart_control_breaches` (20 rows)

| Column | Type | Description |
|---|---|---|
| `country` | VARCHAR | Customer country (5 values) |
| `channel` | VARCHAR | SIMULATED intake channel (Web 40%, Branch 25%, Mobile 25%, Partner 10%) **SIM** |
| `approvals` | BIGINT | Cases with decision = Approve |
| `breach_no_identity` | BIGINT | Count of approvals with identity unverified |
| `breach_no_address` | BIGINT | Count of approvals with address unverified |
| `breach_missing_doc` | BIGINT | Count of approvals with fewer than 5 verified documents |
| `breach_id_or_address` | BIGINT | Count of approvals with identity or address unverified |
| `any_kyc_breach` | BIGINT | Approved AND (identity unverified OR address unverified OR fewer than 5 verified documents) |

### `mart_doc_quality` (25 rows)

| Column | Type | Description |
|---|---|---|
| `doc_type` | VARCHAR | Document type (Passport, PAN, Aadhaar, Driving License, Utility Bill) |
| `issue_country` | VARCHAR | Document issuing country |
| `docs` | BIGINT | Number of documents |
| `failed_docs` | BIGINT | Unverified documents |
| `fail_pct` | DOUBLE | Unverified documents as % of documents |
| `avg_conf` | DOUBLE | Mean OCR confidence |
| `low_conf_docs` | BIGINT | Documents with confidence < 0.85 |
| `low_conf_pct` | DOUBLE | Low-confidence documents as % |

### `mart_doc_conf_hist` (100 rows)

| Column | Type | Description |
|---|---|---|
| `doc_type` | VARCHAR | Document type (Passport, PAN, Aadhaar, Driving License, Utility Bill) |
| `conf_bin` | DOUBLE | OCR confidence bin (0.01 wide, floor) |
| `docs` | BIGINT | Number of documents |
| `failed_docs` | BIGINT | Unverified documents |

### `mart_review_backlog` (3 rows)

| Column | Type | Description |
|---|---|---|
| `risk_category` | VARCHAR | Risk tier (Low/Medium/High) |
| `customers` | BIGINT | Number of customers |
| `overdue` | BIGINT | Customers overdue for periodic review |
| `overdue_pct` | DOUBLE | Overdue customers as % |

### `mart_review_backlog_age` (15 rows)

| Column | Type | Description |
|---|---|---|
| `risk_category` | VARCHAR | Risk tier (Low/Medium/High) |
| `age_band` | VARCHAR | Age band 18-24 / 25-34 / 35-49 / 50-64 / 65+ |
| `customers` | BIGINT | Number of customers |
| `overdue` | BIGINT | Customers overdue for periodic review |
| `overdue_pct` | DOUBLE | Overdue customers as % |

### `mart_rule_coverage` (112 rows)

| Column | Type | Description |
|---|---|---|
| `rule_category` | VARCHAR | Rule category (7 values) |
| `jurisdiction` | VARCHAR | Rule country (UK, USA, India, Global) |
| `priority` | VARCHAR | Rule priority (Low/Medium/High/Critical) |
| `rules` | BIGINT | Number of rules |
| `rules_without_guideline` | BIGINT | Rules with no guideline (orphans) |
| `guidelines` | HUGEINT | Number of guidelines |

### `mart_guideline_timeline` (30 rows)

| Column | Type | Description |
|---|---|---|
| `version` | VARCHAR | Rule or guideline version |
| `effective_year` | BIGINT | Year of effective_date |
| `guidelines` | BIGINT | Number of guidelines |

### `mart_rules` (3,000 rows)

| Column | Type | Description |
|---|---|---|
| `rule_id` | VARCHAR | RuleID |
| `rule_title` | VARCHAR | Rule title |
| `rule_category` | VARCHAR | Rule category (7 values) |
| `jurisdiction` | VARCHAR | Rule country (UK, USA, India, Global) |
| `priority` | VARCHAR | Rule priority (Low/Medium/High/Critical) |
| `version` | VARCHAR | Rule or guideline version |
| `n_guidelines` | BIGINT | Guidelines implementing the rule (LEFT JOIN count) |
| `is_orphan` | BOOLEAN | Rule has no guideline |
| `rule_text` | VARCHAR | Rule text (policy text) |

### `mart_guidelines` (10,000 rows)

| Column | Type | Description |
|---|---|---|
| `guideline_id` | VARCHAR | GuidelineID |
| `rule_id` | VARCHAR | RuleID |
| `section` | VARCHAR | Guideline section |
| `version` | VARCHAR | Rule or guideline version |
| `effective_date` | DATE | Guideline effective date (parsed from dd-mm-yyyy) |
| `paragraph` | VARCHAR | Guideline paragraph text (policy text, no PII) |

### `mart_customer_docs` (500,000 rows)

| Column | Type | Description |
|---|---|---|
| `customer_id` | VARCHAR | CustomerID (synthetic) |
| `doc_type` | VARCHAR | Document type (Passport, PAN, Aadhaar, Driving License, Utility Bill) |
| `verified` | BOOLEAN | Document verified |
| `confidence` | DOUBLE | OCR confidence (0.80-0.99) |
| `issue_country` | VARCHAR | Document issuing country |
| `expiry_date` | DATE | Document expiry date |

## Analysis results (sql/04_analysis.sql) - exported to data/marts

### `analysis_funnel` (5 rows)

| Column | Type | Description |
|---|---|---|
| `stage_order` | INTEGER | Funnel stage order |
| `stage` | VARCHAR | Funnel stage |
| `cases` | BIGINT | Number of cases |
| `dropped` | BIGINT | Cases lost at this stage |
| `drop_off_pct` | DOUBLE | Cases lost at this stage as % of the previous stage |
| `pct_of_opened` | DOUBLE | Stage cases as % of opened (FIRST_VALUE) |

### `analysis_worst_analyst_month` (24 rows)

| Column | Type | Description |
|---|---|---|
| `opened_month` | DATE | SIMULATED open month **SIM** |
| `assigned_to` | VARCHAR | SIMULATED analyst (Analyst_01..Analyst_24, uniform) **SIM** |
| `cases` | BIGINT | Number of cases **SIM** |
| `sla_breaches` | BIGINT | Count of SIMULATED SLA breaches **SIM** |
| `breach_pct` | DOUBLE | Breach rate in percent (SLA breach for analysts; control breach for channel/country) **SIM** |

### `analysis_review_backlog` (3 rows)

| Column | Type | Description |
|---|---|---|
| `risk_category` | VARCHAR | Risk tier (Low/Medium/High) |
| `customers` | BIGINT | Number of customers |
| `overdue` | BIGINT | Customers overdue for periodic review |
| `overdue_pct` | DOUBLE | Overdue customers as % |
| `max_days_since_review` | BIGINT | Oldest review in days |
| `avg_days_overdue_customers` | DOUBLE | Mean days since review among overdue customers |

### `analysis_breach_by_channel_country` (30 rows)

| Column | Type | Description |
|---|---|---|
| `channel` | VARCHAR | SIMULATED intake channel (Web 40%, Branch 25%, Mobile 25%, Partner 10%) **SIM** |
| `country` | VARCHAR | Customer country (5 values) |
| `approvals` | BIGINT | Cases with decision = Approve |
| `approved_failed_id_or_address` | BIGINT | Approvals with identity or address unverified |
| `breach_pct` | DOUBLE | Approvals with identity or address unverified, % of approvals |
| `grouping_level` | BIGINT | GROUPING(channel, country): 0 cross, 1 channel total, 2 country total, 3 grand total |

### `analysis_mom` (24 rows)

| Column | Type | Description |
|---|---|---|
| `opened_month` | DATE | SIMULATED open month **SIM** |
| `cases` | BIGINT | Number of cases **SIM** |
| `mom_delta` | BIGINT | Cases minus previous month **SIM** |
| `mom_pct` | DOUBLE | Month-over-month change in % **SIM** |
| `moving_avg_3m` | DOUBLE | 3-month moving average of cases **SIM** |

### `analysis_analyst_rank` (24 rows)

| Column | Type | Description |
|---|---|---|
| `assigned_to` | VARCHAR | SIMULATED analyst (Analyst_01..Analyst_24, uniform) **SIM** |
| `cases` | BIGINT | Number of cases **SIM** |
| `p50_tat_days` | DOUBLE | Median SIMULATED turnaround **SIM** |
| `p90_tat_days` | DOUBLE | 90th percentile SIMULATED turnaround (quantile_cont) **SIM** |
| `breach_pct` | DOUBLE | Breach rate in percent (SLA breach for analysts; control breach for channel/country) **SIM** |
| `breach_rank` | BIGINT | RANK() by breach rate, 1 = worst **SIM** |
| `p90_rank` | BIGINT | DENSE_RANK by p90 turnaround **SIM** |
| `breach_quartile` | BIGINT | NTILE(4) quartile of analysts by SLA breach rate **SIM** |

### `analysis_rule_orphans` (117 rows)

| Column | Type | Description |
|---|---|---|
| `rule_id` | VARCHAR | RuleID |
| `rule_title` | VARCHAR | Rule title |
| `rule_category` | VARCHAR | Rule category (7 values) |
| `jurisdiction` | VARCHAR | Rule country (UK, USA, India, Global) |
| `priority` | VARCHAR | Rule priority (Low/Medium/High/Critical) |
| `version` | VARCHAR | Rule or guideline version |

## AI-answer marts (etl/ai_qa_marts.py) - exported to data/marts

### `mart_ai_by_type` (6 rows)

| Column | Type | Description |
|---|---|---|
| `hallucination_type` | VARCHAR | Hallucination type (NONE = faithful) |
| `answers` | BIGINT | Number of answers |
| `hallucinated` | BIGINT | Hallucinated answers |
| `hallucination_rate_pct` | DOUBLE | Hallucinated answers as % of answers of this type |
| `share_of_answers_pct` | DOUBLE | Share of all benchmark answers (%) |
| `avg_len_diff_chars` | DOUBLE | Mean characters of generated answer minus ground truth |

### `mart_ai_by_question` (5 rows)

| Column | Type | Description |
|---|---|---|
| `question_template` | VARCHAR | Question with customer IDs masked (C#) |
| `answers` | BIGINT | Number of answers |
| `hallucinated` | BIGINT | Hallucinated answers |
| `hallucination_pct` | DOUBLE | Hallucinated answers as % of answers |

### `mart_ai_severity` (20 rows)

| Column | Type | Description |
|---|---|---|
| `hallucination_type` | VARCHAR | Hallucination type (NONE = faithful) |
| `severity` | VARCHAR | Hallucination severity (Low/Medium/High/Critical; n/a for faithful answers) |
| `answers` | BIGINT | Number of answers |
| `pct_of_type` | DOUBLE | Share of the type's hallucinations with this severity (%) |

### `mart_ai_detector_confusion` (6 rows)

| Column | Type | Description |
|---|---|---|
| `true_type` | VARCHAR | Labelled hallucination type |
| `predicted_type` | VARCHAR | Detector prediction |
| `answers` | BIGINT | Number of answers |

### `mart_ai_detector_metrics` (6 rows)

| Column | Type | Description |
|---|---|---|
| `hallucination_type` | VARCHAR | Hallucination type (NONE = faithful) |
| `support` | BIGINT | True answers of this type |
| `predicted` | BIGINT | Answers predicted as this type |
| `true_positive` | BIGINT | Correctly detected answers |
| `precision` | DOUBLE | Precision of the detector for this type |
| `recall` | DOUBLE | Recall of the detector for this type |
| `f1` | DOUBLE | F1 score |

### `ai_examples` (25 rows)

| Column | Type | Description |
|---|---|---|
| `example_id` | BIGINT | Example number |
| `question_template` | VARCHAR | Question with customer IDs masked (C#) |
| `hallucination_type` | VARCHAR | Hallucination type (NONE = faithful) |
| `severity` | VARCHAR | Hallucination severity (Low/Medium/High/Critical; n/a for faithful answers) |
| `ground_truth_masked` | VARCHAR | Ground-truth answer with IDs masked |
| `generated_masked` | VARCHAR | Generated answer with customer IDs masked as C# |
| `detector_prediction` | VARCHAR | Detector prediction for this template |
| `flagged_claim` | VARCHAR | The sentence the detector flagged |
| `answers_with_template` | BIGINT | Benchmark answers sharing this template |

## Data quality (etl/quality_checks.py) and ML (ml/decision_model.py) - exported to data/marts

### `mart_dq_report` (78 rows)

| Column | Type | Description |
|---|---|---|
| `check_name` | VARCHAR | Data-quality check identifier |
| `table_name` | VARCHAR | Table or mart checked |
| `result` | DOUBLE | Check result value |
| `threshold` | VARCHAR | Rule the result is compared against |
| `status` | VARCHAR | pass / warn / fail |
| `detail` | VARCHAR | Explanation of the check |

### `mart_claims_check` (74 rows)

| Column | Type | Description |
|---|---|---|
| `claim_id` | VARCHAR | Claim identifier |
| `claim` | VARCHAR | Fact asserted in the project brief |
| `claimed` | VARCHAR | Value stated in the brief |
| `measured` | DOUBLE | Value recomputed from the data |
| `matches` | BOOLEAN | Measured value within the claimed range |

### `mart_ml_results` (107 rows)

| Column | Type | Description |
|---|---|---|
| `experiment` | VARCHAR | A_all_features or B_without_pep_sanction_risk |
| `kind` | VARCHAR | metric, confusion, permutation_importance or shap_importance |
| `name` | VARCHAR | Metric name, "true -> predicted" pair, or feature |
| `value` | DOUBLE | Metric value, count or importance |
| `std` | DOUBLE | Standard deviation (permutation importance only) |
