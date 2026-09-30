-- =============================================================================
-- 02_model.sql : star schema + rule engine + control-breach flags
-- -----------------------------------------------------------------------------
-- Input : stg_* tables (01_staging.sql) and sim_case_ops (etl/build_warehouse.py)
-- Output: dim_date, dim_customer, dim_rule, fact_document, fact_case
-- Why   : the rule engine re-derives every labelled decision from the inputs, so
--         policy compliance is proven row by row rather than asserted. The breach
--         flags then test whether the verification controls were honoured.
-- AS_OF : read from the session variable 'as_of' (set once by the orchestrator)
--         so the snapshot date is defined in exactly one place.
-- =============================================================================

-- Calendar dimension covering the simulated window with headroom.
CREATE OR REPLACE TABLE dim_date AS
WITH calendar AS (
    SELECT CAST(d AS DATE) AS date_key
    FROM range(DATE '2024-01-01', DATE '2027-01-01', INTERVAL 1 DAY) AS t(d)
)
SELECT
    date_key,
    year(date_key)                       AS year,
    quarter(date_key)                    AS quarter,
    month(date_key)                      AS month,
    strftime(date_key, '%Y-%m')          AS year_month,
    CAST(date_trunc('month', date_key) AS DATE) AS month_start,
    dayofweek(date_key)                  AS day_of_week,
    dayofweek(date_key) IN (0, 6)        AS is_weekend
FROM calendar;

-- Customer dimension: descriptive attributes, bands and periodic-review status.
-- NTILE ties are broken by customer_id so quintiles are deterministic.
CREATE OR REPLACE TABLE dim_customer AS
SELECT
    c.customer_id,
    c.full_name,
    c.dob,
    c.age,
    CASE
        WHEN c.age < 25 THEN '18-24'
        WHEN c.age < 35 THEN '25-34'
        WHEN c.age < 50 THEN '35-49'
        WHEN c.age < 65 THEN '50-64'
        ELSE '65+'
    END                                                        AS age_band,
    c.gender,
    c.nationality,
    c.country,
    c.occupation,
    c.income,
    NTILE(5) OVER (ORDER BY c.income, c.customer_id)           AS income_quintile,
    c.tax_resident,
    c.is_pep,
    c.is_sanctioned,
    c.address_verified,
    c.identity_verified,
    c.risk_category,
    c.aml_flag,
    c.account_type,
    c.last_updated,
    date_diff('day', c.last_updated, getvariable('as_of'))     AS days_since_review,
    date_diff('day', c.last_updated, getvariable('as_of')) > 365 AS review_overdue
FROM stg_customers AS c;

-- Rule dimension: each rule with how many guideline paragraphs implement it.
-- LEFT JOIN keeps rules with zero guidelines (the orphan rules).
CREATE OR REPLACE TABLE dim_rule AS
WITH guideline_counts AS (
    SELECT rule_id, COUNT(*) AS n_guidelines
    FROM stg_guidelines
    GROUP BY rule_id
)
SELECT
    r.rule_id,
    r.rule_title,
    r.rule_category,
    r.rule_text,
    r.jurisdiction,
    r.priority,
    CASE r.priority
        WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 WHEN 'Medium' THEN 3 ELSE 4
    END                                   AS priority_rank,
    r.version,
    COALESCE(g.n_guidelines, 0)           AS n_guidelines,
    COALESCE(g.n_guidelines, 0) = 0       AS is_orphan
FROM stg_rules AS r
LEFT JOIN guideline_counts AS g USING (rule_id);

-- Document fact: one row per document. Low confidence threshold is 0.85.
CREATE OR REPLACE TABLE fact_document AS
SELECT
    d.document_id,
    d.customer_id,
    d.doc_type,
    d.issue_country,
    d.expiry_date,
    d.is_verified,
    d.confidence,
    d.confidence < 0.85 AS low_confidence,
    d.source
FROM stg_documents AS d;

-- Case fact: labelled decision, rule-engine decision, agreement and breach flags,
-- joined to the simulated operations layer (kept in its own table, sim_case_ops).
CREATE OR REPLACE TABLE fact_case AS
WITH doc_counts AS (
    -- Recount verified documents from the document table to prove the
    -- VerifiedDocuments column is consistent (checked in quality_checks.py).
    SELECT customer_id,
           COUNT(*)                            AS doc_rows,
           COUNT(*) FILTER (WHERE is_verified) AS verified_doc_rows
    FROM fact_document
    GROUP BY customer_id
),
engine AS (
    SELECT
        k.*,
        -- Recovered decision policy, in precedence order.
        CASE WHEN k.is_sanctioned            THEN 'Reject'
             WHEN k.is_pep                   THEN 'Enhanced Due Diligence'
             WHEN k.risk_category = 'High'   THEN 'Escalate (EDD/Manual)'
             WHEN k.verified_docs < 4        THEN 'Pending Documents'
             ELSE 'Approve' END              AS engine_decision,
        -- Which rule fired, for explainability in Customer 360.
        CASE WHEN k.is_sanctioned            THEN 'R1 Sanctions screening'
             WHEN k.is_pep                   THEN 'R2 PEP enhanced due diligence'
             WHEN k.risk_category = 'High'   THEN 'R3 High-risk escalation'
             WHEN k.verified_docs < 4        THEN 'R4 Document sufficiency'
             ELSE 'R5 Standard approval' END AS engine_rule
    FROM stg_cases AS k
)
SELECT
    e.case_id,
    e.customer_id,
    e.country,
    e.occupation,
    e.income,
    e.is_pep,
    e.is_sanctioned,
    e.risk_category,
    e.aml_flag,
    e.verified_docs,
    dc.doc_rows,
    dc.verified_doc_rows,
    e.decision,
    e.decision_reason,
    e.engine_decision,
    e.engine_rule,
    -- engine_agrees: TRUE when the engine outcome equals the labelled decision,
    -- where 'Escalate (EDD/Manual)' matches either EDD or Manual Review.
    -- It must be TRUE for 100% of rows.
    CASE WHEN e.engine_decision = 'Escalate (EDD/Manual)'
         THEN e.decision IN ('Enhanced Due Diligence', 'Manual Review')
         ELSE e.decision = e.engine_decision END             AS engine_agrees,
    cu.identity_verified,
    cu.address_verified,
    cu.account_type,
    cu.age_band,
    cu.income_quintile,
    cu.review_overdue,
    cu.days_since_review,
    cu.last_updated,
    -- Control-breach flags: approved although a verification control failed.
    (e.decision = 'Approve' AND NOT cu.identity_verified)    AS breach_approved_no_identity,
    (e.decision = 'Approve' AND NOT cu.address_verified)     AS breach_approved_no_address,
    (e.decision = 'Approve' AND e.verified_docs < 5)         AS breach_approved_missing_doc,
    (e.decision = 'Approve'
        AND (NOT cu.identity_verified OR NOT cu.address_verified)) AS breach_approved_id_or_address,
    (e.decision = 'Approve'
        AND (NOT cu.identity_verified OR NOT cu.address_verified
             OR e.verified_docs < 5))                        AS any_kyc_breach,
    -- Simulated operations fields (SIMULATED: see sim_case_ops and docs).
    s.opened_at,
    s.closed_at,
    CAST(s.opened_at AS DATE)                                AS opened_date,
    CAST(date_trunc('month', s.opened_at) AS DATE)           AS opened_month,
    s.assigned_to,
    s.channel,
    s.handling_days,
    s.tat_days,
    s.sla_days,
    s.sla_breached,
    s.is_open
FROM engine AS e
JOIN dim_customer AS cu USING (customer_id)
LEFT JOIN doc_counts AS dc USING (customer_id)
LEFT JOIN sim_case_ops AS s USING (case_id);
