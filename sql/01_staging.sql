-- =============================================================================
-- 01_staging.sql : typed, snake_case staging tables over the raw CSVs
-- -----------------------------------------------------------------------------
-- Input : ${RAW_DIR}/*.csv (substituted by etl/build_warehouse.py; the path is
--         an operator CLI argument, validated and quote-escaped, never user input)
-- Output: stg_customers, stg_cases, stg_documents, stg_rules, stg_guidelines
-- Why   : every downstream model reads typed columns with one naming convention.
--         Yes/No columns are auto-cast to BOOLEAN by DuckDB, so predicates can be
--         written as WHERE is_pep instead of string comparisons.
--         OCRText (~100 MB of free text) is deliberately never read.
-- =============================================================================

-- Customers: one row per synthetic customer profile.
CREATE OR REPLACE TABLE stg_customers AS
SELECT
    CustomerID                     AS customer_id,
    FullName                       AS full_name,       -- synthetic; never exported to marts
    CAST(DOB AS DATE)              AS dob,              -- synthetic; never exported to marts
    CAST(Age AS INTEGER)           AS age,
    Gender                         AS gender,
    Nationality                    AS nationality,
    Country                        AS country,
    Occupation                     AS occupation,
    CAST(Income AS BIGINT)         AS income,           -- no currency in the source
    TaxResident                    AS tax_resident,
    CAST(PEPStatus AS BOOLEAN)        AS is_pep,
    CAST(SanctionStatus AS BOOLEAN)   AS is_sanctioned,
    CAST(AddressVerified AS BOOLEAN)  AS address_verified,
    CAST(IdentityVerified AS BOOLEAN) AS identity_verified,
    RiskCategory                   AS risk_category,
    CAST(AMLFlag AS BOOLEAN)       AS aml_flag,
    AccountType                    AS account_type,
    CAST(LastUpdated AS DATE)      AS last_updated
FROM read_csv('${RAW_DIR}/customer_profiles.csv', header = true, auto_detect = true);

-- Cases: one onboarding case per customer with the labelled decision.
CREATE OR REPLACE TABLE stg_cases AS
SELECT
    CaseID                             AS case_id,
    CustomerID                         AS customer_id,
    Country                            AS country,
    Occupation                         AS occupation,
    CAST(Income AS BIGINT)             AS income,
    CAST(PEPStatus AS BOOLEAN)         AS is_pep,
    CAST(SanctionStatus AS BOOLEAN)    AS is_sanctioned,
    RiskCategory                       AS risk_category,
    CAST(AMLFlag AS BOOLEAN)           AS aml_flag,
    CAST(VerifiedDocuments AS INTEGER) AS verified_docs,
    ExpectedDecision                   AS decision,
    DecisionReason                     AS decision_reason
FROM read_csv('${RAW_DIR}/kyc_cases.csv', header = true, auto_detect = true);

-- Documents: five per customer. OCRText is excluded at read time (projection),
-- so it never enters the warehouse, the marts or Git.
CREATE OR REPLACE TABLE stg_documents AS
SELECT
    DocumentID                 AS document_id,
    CustomerID                 AS customer_id,
    DocumentType               AS doc_type,
    DocumentNumber             AS document_number,  -- synthetic; never exported to marts
    IssueCountry               AS issue_country,
    CAST(ExpiryDate AS DATE)   AS expiry_date,
    CAST(Verified AS BOOLEAN)  AS is_verified,
    CAST(Confidence AS DOUBLE) AS confidence,
    Source                     AS source
FROM read_csv('${RAW_DIR}/customer_documents.csv', header = true, auto_detect = true);

-- AML rules: the policy library (3,000 rules in the full data).
CREATE OR REPLACE TABLE stg_rules AS
SELECT
    RuleID       AS rule_id,
    RuleTitle    AS rule_title,
    RuleCategory AS rule_category,
    RuleText     AS rule_text,
    Country      AS jurisdiction,
    Priority     AS priority,
    Version      AS version
FROM read_csv('${RAW_DIR}/aml_rules.csv', header = true, auto_detect = true);

-- Guidelines: EffectiveDate is dd-mm-yyyy in the source, so the format is given
-- explicitly instead of trusting auto-detection (which can silently flip day/month).
CREATE OR REPLACE TABLE stg_guidelines AS
SELECT
    GuidelineID   AS guideline_id,
    RuleID        AS rule_id,
    Section       AS section,
    Paragraph     AS paragraph,
    Version       AS version,
    EffectiveDate AS effective_date
FROM read_csv(
    '${RAW_DIR}/kyc_guidelines.csv',
    header = true,
    dateformat = '%d-%m-%Y',
    types = {'EffectiveDate': 'DATE'}
);
