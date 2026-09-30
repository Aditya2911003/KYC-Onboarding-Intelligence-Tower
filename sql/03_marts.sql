-- =============================================================================
-- 03_marts.sql : small, app-ready marts exported to data/marts/*.parquet
-- -----------------------------------------------------------------------------
-- Input : dim_*, fact_* (02_model.sql)
-- Output: every table named mart_* is exported by etl/build_warehouse.py as
--         zstd Parquet. The Streamlit app reads ONLY these files.
-- Why   : the app must stay far below Streamlit Community Cloud limits, so the
--         marts carry only the columns the pages need and no direct identifiers
--         (no names, dates of birth, document numbers or OCR text).
-- Note  : columns derived from sim_case_ops (channel, assigned_to, opened_*,
--         tat_days, sla_*, is_open) are SIMULATED and disclosed in the app.
-- =============================================================================

-- Row-level case mart: one row per case, the grain for every sliceable visual.
CREATE OR REPLACE TABLE mart_case_detail AS
SELECT
    case_id,
    customer_id,
    country,
    occupation,
    account_type,
    risk_category,
    is_pep,
    is_sanctioned,
    aml_flag,
    decision,
    decision_reason,
    engine_decision,
    engine_rule,
    engine_agrees,
    verified_docs,
    income_quintile,
    age_band,
    channel,                                   -- SIMULATED
    assigned_to,                               -- SIMULATED
    opened_date,                               -- SIMULATED
    opened_month,                              -- SIMULATED
    ROUND(tat_days, 2)        AS tat_days,     -- SIMULATED
    sla_days,                                  -- SIMULATED (policy target per decision)
    sla_breached,                              -- SIMULATED
    is_open,                                   -- SIMULATED
    breach_approved_no_identity,
    breach_approved_no_address,
    breach_approved_missing_doc,
    breach_approved_id_or_address,
    any_kyc_breach,
    review_overdue,
    days_since_review,
    last_updated,
    identity_verified,
    address_verified
FROM fact_case;

-- Monthly KPI cube: month x decision x country x risk tier.
CREATE OR REPLACE TABLE mart_monthly_kpi AS
SELECT
    opened_month,
    decision,
    country,
    risk_category,
    COUNT(*)                                   AS cases,
    ROUND(AVG(tat_days), 3)                    AS avg_tat_days,
    COUNT(*) FILTER (WHERE sla_breached)       AS sla_breaches,
    COUNT(*) FILTER (WHERE is_open)            AS still_open
FROM fact_case
GROUP BY opened_month, decision, country, risk_category;

-- Month-over-month series: LAG delta, MoM %, 3-month moving average and rates.
CREATE OR REPLACE TABLE mart_mom AS
WITH monthly AS (
    SELECT
        opened_month,
        COUNT(*)                                                    AS cases,
        COUNT(*) FILTER (WHERE decision = 'Approve')                AS approvals,
        COUNT(*) FILTER (WHERE breach_approved_id_or_address)       AS control_breaches,
        COUNT(*) FILTER (WHERE sla_breached)                        AS sla_breaches
    FROM fact_case
    GROUP BY opened_month
)
SELECT
    opened_month,
    cases,
    LAG(cases) OVER w_month                                          AS prev_cases,
    cases - LAG(cases) OVER w_month                                  AS cases_delta,
    ROUND(100.0 * (cases - LAG(cases) OVER w_month)
          / NULLIF(LAG(cases) OVER w_month, 0), 2)                   AS mom_pct,
    ROUND(AVG(cases) OVER (w_month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 1) AS cases_ma3,
    ROUND(approvals / cases, 4)                                AS approval_rate,
    ROUND(control_breaches / NULLIF(approvals, 0), 4)          AS breach_rate,
    ROUND(sla_breaches / cases, 4)                             AS sla_breach_rate
FROM monthly
WINDOW w_month AS (ORDER BY opened_month);

-- Analyst league table (SIMULATED assignment): workload, turnaround, breach rank.
CREATE OR REPLACE TABLE mart_analyst AS
WITH per_analyst AS (
    SELECT
        assigned_to,
        COUNT(*)                                        AS cases,
        ROUND(AVG(tat_days), 3)                         AS avg_tat_days,
        ROUND(quantile_cont(tat_days, 0.9), 3)          AS p90_tat_days,
        COUNT(*) FILTER (WHERE sla_breached)            AS sla_breaches,
        COUNT(*) FILTER (WHERE risk_category = 'High')  AS high_risk_cases
    FROM fact_case
    GROUP BY assigned_to
)
SELECT
    *,
    ROUND(100.0 * sla_breaches / cases, 2)                          AS breach_pct,
    RANK() OVER (ORDER BY sla_breaches / cases DESC)                AS breach_rank
FROM per_analyst;

-- Onboarding funnel: each stage is the population that passed every prior gate.
CREATE OR REPLACE TABLE mart_funnel AS
SELECT 1 AS stage_order, 'Opened' AS stage, COUNT(*) AS cases FROM fact_case
UNION ALL
SELECT 2, 'Passed sanctions', COUNT(*) FROM fact_case WHERE NOT is_sanctioned
UNION ALL
SELECT 3, 'Passed PEP', COUNT(*) FROM fact_case WHERE NOT is_sanctioned AND NOT is_pep
UNION ALL
SELECT 4, 'Passed risk', COUNT(*) FROM fact_case
    WHERE NOT is_sanctioned AND NOT is_pep AND risk_category <> 'High'
UNION ALL
SELECT 5, 'Approved', COUNT(*) FROM fact_case WHERE decision = 'Approve';

-- Control breaches by country and (SIMULATED) channel.
CREATE OR REPLACE TABLE mart_control_breaches AS
SELECT
    country,
    channel,
    COUNT(*) FILTER (WHERE decision = 'Approve')          AS approvals,
    COUNT(*) FILTER (WHERE breach_approved_no_identity)   AS breach_no_identity,
    COUNT(*) FILTER (WHERE breach_approved_no_address)    AS breach_no_address,
    COUNT(*) FILTER (WHERE breach_approved_missing_doc)   AS breach_missing_doc,
    COUNT(*) FILTER (WHERE breach_approved_id_or_address) AS breach_id_or_address,
    COUNT(*) FILTER (WHERE any_kyc_breach)                AS any_kyc_breach
FROM fact_case
GROUP BY country, channel;

-- Document quality by type and issuing country.
CREATE OR REPLACE TABLE mart_doc_quality AS
SELECT
    doc_type,
    issue_country,
    COUNT(*)                                              AS docs,
    COUNT(*) FILTER (WHERE NOT is_verified)               AS failed_docs,
    ROUND(100.0 * COUNT(*) FILTER (WHERE NOT is_verified) / COUNT(*), 3) AS fail_pct,
    ROUND(AVG(confidence), 4)                             AS avg_conf,
    COUNT(*) FILTER (WHERE low_confidence)                AS low_conf_docs,
    ROUND(100.0 * COUNT(*) FILTER (WHERE low_confidence) / COUNT(*), 3) AS low_conf_pct
FROM fact_document
GROUP BY doc_type, issue_country;

-- OCR confidence histogram in 0.01-wide bins per document type.
CREATE OR REPLACE TABLE mart_doc_conf_hist AS
SELECT
    doc_type,
    ROUND(FLOOR(confidence * 100) / 100, 2) AS conf_bin,
    COUNT(*)                                AS docs,
    COUNT(*) FILTER (WHERE NOT is_verified) AS failed_docs
FROM fact_document
GROUP BY doc_type, conf_bin;

-- Periodic-review backlog by risk tier (overdue = last review > 365 days before AS_OF).
CREATE OR REPLACE TABLE mart_review_backlog AS
SELECT
    risk_category,
    COUNT(*)                                     AS customers,
    COUNT(*) FILTER (WHERE review_overdue)       AS overdue,
    ROUND(100.0 * COUNT(*) FILTER (WHERE review_overdue) / COUNT(*), 2) AS overdue_pct
FROM dim_customer
GROUP BY risk_category;

-- Periodic-review backlog by risk tier and age band.
CREATE OR REPLACE TABLE mart_review_backlog_age AS
SELECT
    risk_category,
    age_band,
    COUNT(*)                                     AS customers,
    COUNT(*) FILTER (WHERE review_overdue)       AS overdue,
    ROUND(100.0 * COUNT(*) FILTER (WHERE review_overdue) / COUNT(*), 2) AS overdue_pct
FROM dim_customer
GROUP BY risk_category, age_band;

-- Rule coverage: rules and orphan rules by category x jurisdiction x priority.
CREATE OR REPLACE TABLE mart_rule_coverage AS
SELECT
    rule_category,
    jurisdiction,
    priority,
    COUNT(*)                              AS rules,
    COUNT(*) FILTER (WHERE is_orphan)     AS rules_without_guideline,
    SUM(n_guidelines)                     AS guidelines
FROM dim_rule
GROUP BY rule_category, jurisdiction, priority;

-- Guideline counts by version and effective year (timeline visual).
CREATE OR REPLACE TABLE mart_guideline_timeline AS
SELECT
    version,
    year(effective_date)  AS effective_year,
    COUNT(*)              AS guidelines
FROM stg_guidelines
GROUP BY version, effective_year;

-- Rule library for keyword search and the orphan list (policy text, no PII).
CREATE OR REPLACE TABLE mart_rules AS
SELECT rule_id, rule_title, rule_category, jurisdiction, priority, version,
       n_guidelines, is_orphan, rule_text
FROM dim_rule;

-- Guideline paragraphs for keyword search (policy text, no PII).
CREATE OR REPLACE TABLE mart_guidelines AS
SELECT guideline_id, rule_id, section, version, effective_date, paragraph
FROM stg_guidelines;

-- Customer 360 documents: the five documents per customer, without OCR text.
CREATE OR REPLACE TABLE mart_customer_docs AS
SELECT
    customer_id,
    doc_type,
    is_verified            AS verified,
    ROUND(confidence, 4)   AS confidence,
    issue_country,
    expiry_date
FROM fact_document;
