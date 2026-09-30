# Data

## Where the raw files go

Put `archive.zip` in the repository root and run `make raw` (or unzip it yourself so the 14 CSVs sit directly in `data/raw/`):

```
data/raw/customer_profiles.csv      data/raw/kyc_cases.csv            data/raw/customer_documents.csv
data/raw/aml_rules.csv              data/raw/kyc_guidelines.csv       data/raw/benchmark_dataset.csv
data/raw/hallucinated_answers.csv   data/raw/ground_truth_answers.csv data/raw/kyc_questions.csv
data/raw/hallucination_labels.csv   data/raw/hallucination_training_dataset.csv
data/raw/hallucination_training_dataset_v2.csv  data/raw/nli_dataset.csv  data/raw/nli_dataset_dedup.csv
```

Then `make etl` builds `data/warehouse.duckdb` (gitignored) and refreshes `data/marts/`.

## What is committed

| Folder | Contents | Size |
|---|---|---|
| `data/marts/` | Parquet marts read by the app (aggregates, the 100k-row case mart, the document mart without OCR text, rule/guideline text, AI examples with masked IDs, DQ and ML results) | ~2.7 MB |
| `data/sample/` | Deterministic 1,000-customer raw sample (`etl/make_sample.py`, seed 42): their profiles, cases and 5,000 documents (no OCRText), 1,000 benchmark rows, 1,000 hallucinated-answer rows (every sampled hallucinated benchmark answer keeps its severity row), and the full rules and guidelines | ~4 MB |

## Licence note

The dataset is **synthetic**: every name, ID, document and answer is generated and no real person is represented. It is **not redistributed** in this repository — the raw CSVs (623 MB), the OCR text and the `.duckdb` warehouse are gitignored. Obtain `archive.zip` from its original source and respect that source's terms. The small sample and marts are derived artefacts included only so CI and the public app can run.
