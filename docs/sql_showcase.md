# SQL showcase

Where each advanced SQL feature is used and why. All SQL is DuckDB; files run in order `01 → 04`, and every table is created with `CREATE OR REPLACE`.

| Feature | Where | What it answers |
|---|---|---|
| `read_csv(path, dateformat='%d-%m-%Y', types={'EffectiveDate':'DATE'})` | `sql/01_staging.sql` (`stg_guidelines`) | Parses dd-mm-yyyy explicitly instead of trusting auto-detection. |
| Column projection on CSV | `sql/01_staging.sql` (`stg_documents`) | Never reads the ~100 MB `OCRText` column. |
| BOOLEAN predicates (`WHERE is_pep`) | everywhere | Yes/No auto-cast to BOOLEAN, cast explicitly in staging. |
| `range()` table function | `sql/02_model.sql` (`dim_date`) | Generates the 2024-01-01 → 2026-12-31 calendar. |
| `NTILE(5) OVER (ORDER BY income, customer_id)` | `sql/02_model.sql` (`dim_customer`) | Deterministic income quintiles (ties broken by ID). |
| `getvariable('as_of')` / `SET VARIABLE` | `sql/02_model.sql`, `etl/quality_checks.py` | The snapshot date is defined once by the orchestrator. |
| Searched `CASE` rule engine + agreement flag | `sql/02_model.sql` (`fact_case`) | Re-derives every decision and proves 100% agreement. |
| `COUNT(*) FILTER (WHERE decision = 'Approve')` | `02_model`, `03_marts`, `04_analysis`, app queries | Conditional aggregation: verified document recount, breach counts, funnel stages. |
| `LEFT JOIN` + `COALESCE` | `sql/02_model.sql` (`dim_rule`) | Keeps rules without guidelines (`n_guidelines = 0`). |
| `quantile_cont(tat_days, 0.9)` | `03_marts` (`mart_analyst`), `04_analysis` (6), Operations page | p90 turnaround (SIMULATED). |
| `LAG()` + named `WINDOW` | `03_marts` (`mart_mom`), `04_analysis` (5) | Month-over-month change and MoM %. |
| `AVG(cases) OVER (ORDER BY opened_month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW)` | `03_marts`, `04_analysis` (5), Executive page | 3-month moving average. |
| `RANK()`, `DENSE_RANK()`, `NTILE(4)` | `03_marts` (`mart_analyst`), `04_analysis` (6), Operations league table | Analyst ranking by breach rate and p90. |
| `UNPIVOT stage_counts ON opened, passed_sanctions, passed_pep, passed_risk, approved INTO NAME stage VALUE cases` | `04_analysis` (1) `analysis_funnel` | Turns one wide row of stage counts into a funnel. |
| `FIRST_VALUE() OVER w_stage` | `04_analysis` (1) | Each stage as % of opened. |
| CTE then `QUALIFY ROW_NUMBER() OVER (PARTITION BY opened_month ORDER BY breach_pct DESC, cases DESC, assigned_to) = 1` | `04_analysis` (2) `analysis_worst_analyst_month` | Worst analyst per month. DuckDB cannot combine `QUALIFY` with `GROUP BY ALL`, so aggregation happens first in a CTE. |
| `GROUP BY GROUPING SETS ((channel, country), (channel), (country), ())` + `GROUPING()` | `04_analysis` (4) | Breach matrix, both margins and grand total in one pass. |
| `ANTI JOIN` | `04_analysis` (7), `etl/quality_checks.py` | Orphan rules (117); referential-integrity checks. |
| `COUNT(DISTINCT (customer_id, doc_type))` (struct distinct) | `etl/quality_checks.py` | Natural-key uniqueness for documents. |
| `regexp_replace(Question, 'C[0-9]+', 'C#', 'g')` | `etl/ai_qa_marts.py` | Masks customer IDs so answers can be grouped into templates. |
| `SUM(COUNT(*)) OVER (PARTITION BY hallucination_type)` | `etl/ai_qa_marts.py` (`mart_ai_severity`) | Share within type. |
| `COPY mart_case_detail TO 'data/marts/mart_case_detail.parquet' (FORMAT parquet, COMPRESSION zstd)` | `etl/build_warehouse.py` | Small committed marts (~2.7 MB total). |
| `?` placeholders only | `app/data.py::query`, `where_clause` | Every user-controlled value is a bound parameter; keyword search uses `ILIKE '%' || ? || '%'`. |

## Validation of the analysis queries

`etl/build_warehouse.py::validate_analysis` asserts at build time that:

* `analysis_funnel.cases` (FILTER + UNPIVOT) equals `mart_funnel.cases` (plain UNION ALL of WHERE counts);
* `analysis_review_backlog.overdue` equals `mart_review_backlog.overdue`;
* the `GROUPING SETS` grand total equals the sum of `mart_control_breaches.breach_id_or_address`;
* the `ANTI JOIN` orphan count equals the sum of `mart_rule_coverage.rules_without_guideline`.

Results on the full data: funnel 100,000 → 92,123 → 73,648 → 64,425 → 63,001; backlog High 18,101 / Medium 18,611 / Low 13,908; breach grand total 47,157; orphan rules 117.

## Where the results appear on the dashboard

| Query | Page | Tile |
|---|---|---|
| (1) funnel | Funnel and decisions | "Warehouse proof: sql/04_analysis.sql query (1)" |
| (2) worst analyst per month | Operations and SLA | "Warehouse proof: worst analyst per month" |
| (3) review backlog by risk tier | Periodic review backlog | "Warehouse proof: sql/04_analysis.sql query (3)" |
| (4) breaches by channel and country | Controls and compliance | "Warehouse proof: sql/04_analysis.sql query (4)" |
| (5) MoM + moving average | Executive (same window logic, run live on filtered data) | "Monthly volume with 3-month moving average" |
| (6) analyst ranking + p90 | Operations (same logic, live on filtered data) | "Analyst league table" |
| (7) orphan rules | Rules and policy | "Orphan rules (no guideline)" |
