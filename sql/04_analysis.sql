-- =============================================================================
-- 04_analysis.sql : named analysis queries showcasing advanced SQL
-- -----------------------------------------------------------------------------
-- Input : fact_case, dim_customer, dim_rule, stg_guidelines
-- Output: analysis_* tables, exported as data/marts/analysis_*.parquet and shown
--         on the dashboard (Funnel, Controls, Review backlog, Operations,
--         Executive and Rules pages). build_warehouse.py validates the funnel and
--         backlog results against the independently written marts in 03_marts.sql.
-- Why   : each query answers one business question with the idiom best suited
--         to it (FILTER, UNPIVOT, window frames, QUALIFY, GROUPING SETS, ANTI JOIN).
-- =============================================================================

-- (1) Funnel with conditional aggregation (FILTER), reshaped long with UNPIVOT,
--     then FIRST_VALUE gives each stage its share of the opened population.
CREATE OR REPLACE TABLE analysis_funnel AS
WITH stage_counts AS (
    SELECT
        COUNT(*)                                                        AS opened,
        COUNT(*) FILTER (WHERE NOT is_sanctioned)                       AS passed_sanctions,
        COUNT(*) FILTER (WHERE NOT is_sanctioned AND NOT is_pep)        AS passed_pep,
        COUNT(*) FILTER (WHERE NOT is_sanctioned AND NOT is_pep
                           AND risk_category <> 'High')                 AS passed_risk,
        COUNT(*) FILTER (WHERE decision = 'Approve')                    AS approved
    FROM fact_case
),
stages_long AS (
    UNPIVOT stage_counts
    ON opened, passed_sanctions, passed_pep, passed_risk, approved
    INTO NAME stage VALUE cases
),
stages_ordered AS (
    SELECT
        stage,
        cases,
        CASE stage
            WHEN 'opened' THEN 1 WHEN 'passed_sanctions' THEN 2 WHEN 'passed_pep' THEN 3
            WHEN 'passed_risk' THEN 4 ELSE 5
        END AS stage_order
    FROM stages_long
)
SELECT
    stage_order,
    stage,
    cases,
    LAG(cases) OVER w_stage - cases                                        AS dropped,
    ROUND(100.0 * (LAG(cases) OVER w_stage - cases) / LAG(cases) OVER w_stage, 2) AS drop_off_pct,
    ROUND(100.0 * cases / FIRST_VALUE(cases) OVER w_stage, 2)              AS pct_of_opened
FROM stages_ordered
WINDOW w_stage AS (ORDER BY stage_order)
ORDER BY stage_order;

-- (2) Worst analyst per month (SIMULATED). QUALIFY cannot be combined with
--     GROUP BY ALL in DuckDB, so the aggregation happens first in a CTE.
CREATE OR REPLACE TABLE analysis_worst_analyst_month AS
WITH analyst_month AS (
    SELECT
        opened_month,
        assigned_to,
        COUNT(*)                                          AS cases,
        COUNT(*) FILTER (WHERE sla_breached)              AS sla_breaches,
        ROUND(100.0 * COUNT(*) FILTER (WHERE sla_breached) / COUNT(*), 2) AS breach_pct
    FROM fact_case
    GROUP BY opened_month, assigned_to
)
SELECT *
FROM analyst_month
QUALIFY ROW_NUMBER() OVER (
    PARTITION BY opened_month
    ORDER BY breach_pct DESC, cases DESC, assigned_to
) = 1
ORDER BY opened_month;

-- (3) Periodic-review backlog by risk tier, with the oldest review per tier.
CREATE OR REPLACE TABLE analysis_review_backlog AS
SELECT
    risk_category,
    COUNT(*)                                                     AS customers,
    COUNT(*) FILTER (WHERE review_overdue)                       AS overdue,
    ROUND(100.0 * COUNT(*) FILTER (WHERE review_overdue) / COUNT(*), 2) AS overdue_pct,
    MAX(days_since_review)                                       AS max_days_since_review,
    ROUND(AVG(days_since_review) FILTER (WHERE review_overdue), 1) AS avg_days_overdue_customers
FROM dim_customer
GROUP BY risk_category
ORDER BY CASE risk_category WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END;

-- (4) Approvals with a failed verification flag by (SIMULATED) channel and country.
--     GROUPING SETS returns the cross, both margins and the grand total in one pass.
CREATE OR REPLACE TABLE analysis_breach_by_channel_country AS
SELECT
    COALESCE(channel, 'All channels')                           AS channel,
    COALESCE(country, 'All countries')                          AS country,
    COUNT(*) FILTER (WHERE decision = 'Approve')                AS approvals,
    COUNT(*) FILTER (WHERE breach_approved_id_or_address)       AS approved_failed_id_or_address,
    ROUND(100.0 * COUNT(*) FILTER (WHERE breach_approved_id_or_address)
          / NULLIF(COUNT(*) FILTER (WHERE decision = 'Approve'), 0), 2) AS breach_pct,
    GROUPING(channel, country)                                  AS grouping_level
FROM fact_case
GROUP BY GROUPING SETS ((channel, country), (channel), (country), ())
ORDER BY grouping_level, channel, country;

-- (5) Month-over-month change with LAG and a 3-month moving average (SIMULATED dates).
CREATE OR REPLACE TABLE analysis_mom AS
WITH monthly AS (
    SELECT opened_month, COUNT(*) AS cases
    FROM fact_case
    GROUP BY opened_month
)
SELECT
    opened_month,
    cases,
    cases - LAG(cases) OVER w_month                                             AS mom_delta,
    ROUND(100.0 * (cases - LAG(cases) OVER w_month) / LAG(cases) OVER w_month, 2)     AS mom_pct,
    ROUND(AVG(cases) OVER (w_month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 1) AS moving_avg_3m
FROM monthly
WINDOW w_month AS (ORDER BY opened_month)
ORDER BY opened_month;

-- (6) Analyst ranking with p90 turnaround (SIMULATED): RANK, DENSE_RANK, NTILE.
CREATE OR REPLACE TABLE analysis_analyst_rank AS
WITH per_analyst AS (
    SELECT
        assigned_to,
        COUNT(*)                                  AS cases,
        ROUND(quantile_cont(tat_days, 0.5), 2)    AS p50_tat_days,
        ROUND(quantile_cont(tat_days, 0.9), 2)    AS p90_tat_days,
        ROUND(100.0 * COUNT(*) FILTER (WHERE sla_breached) / COUNT(*), 2) AS breach_pct
    FROM fact_case
    GROUP BY assigned_to
)
SELECT
    *,
    RANK()       OVER (ORDER BY breach_pct DESC)   AS breach_rank,
    DENSE_RANK() OVER (ORDER BY p90_tat_days DESC) AS p90_rank,
    NTILE(4)     OVER (ORDER BY breach_pct DESC)   AS breach_quartile
FROM per_analyst
ORDER BY breach_rank;

-- (7) Rule-to-guideline coverage: ANTI JOIN finds rules with no guideline paragraph.
CREATE OR REPLACE TABLE analysis_rule_orphans AS
SELECT
    r.rule_id,
    r.rule_title,
    r.rule_category,
    r.jurisdiction,
    r.priority,
    r.version
FROM dim_rule AS r
ANTI JOIN stg_guidelines AS g ON g.rule_id = r.rule_id
ORDER BY r.priority_rank, r.rule_id;
