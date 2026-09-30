# KYC Onboarding Control Tower: one command per stage.
# `make all` works from a clean clone using only the committed sample.

PYTHON ?= python3
RAW_DIR ?= data/raw
MARTS_DIR ?= data/marts
SAMPLE_OUT ?= build/sample_marts
SAMPLE_DB ?= build/warehouse.duckdb

.PHONY: help setup raw sample etl ml etl-sample ml-sample test lint format app screenshots notebook all clean

help:  ## List targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  %-12s %s\n", $$1, $$2}'

setup:  ## Install pinned dev dependencies (includes the app runtime)
	$(PYTHON) -m pip install -r requirements-dev.txt

raw:  ## Unzip archive.zip (placed in the repo root) into data/raw
	mkdir -p $(RAW_DIR)
	unzip -o -j archive.zip 'data/*.csv' -d $(RAW_DIR)

sample:  ## Rebuild the deterministic 1,000-customer sample from data/raw
	$(PYTHON) etl/make_sample.py --raw-dir $(RAW_DIR) --out-dir data/sample

etl:  ## Build the warehouse and marts from the full raw data
	$(PYTHON) etl/build_warehouse.py --raw-dir $(RAW_DIR) --out-dir $(MARTS_DIR)

ml:  ## Run the two ML experiments on the full warehouse
	$(PYTHON) ml/decision_model.py --db data/warehouse.duckdb --out-dir $(MARTS_DIR)

etl-sample:  ## Build the warehouse from the committed sample (never touches data/marts)
	$(PYTHON) etl/build_warehouse.py --raw-dir data/sample --out-dir $(SAMPLE_OUT) --db $(SAMPLE_DB)

ml-sample:  ## Run the ML experiments on the sample warehouse
	$(PYTHON) ml/decision_model.py --db $(SAMPLE_DB) --out-dir $(SAMPLE_OUT)

test:  ## Run pytest against the sample-built warehouse (+ AppTest on committed marts)
	KYC_TEST_MARTS_DIR=$(SAMPLE_OUT) KYC_TEST_DB=$(SAMPLE_DB) $(PYTHON) -m pytest -q

lint:  ## ruff lint + format check
	ruff check .
	ruff format --check .

format:  ## Apply ruff formatting
	ruff format .

app:  ## Run the dashboard locally
	streamlit run app/streamlit_app.py

screenshots:  ## Capture docs/screenshots/*.png and demo.gif with Playwright (starts the app itself)
	$(PYTHON) scripts/capture_screenshots.py

notebook:  ## Execute the EDA notebook in place (needs data/raw)
	$(PYTHON) -m jupyter nbconvert --to notebook --execute --inplace notebooks/01_eda_and_findings.ipynb

all: setup lint etl-sample ml-sample test  ## Clean-clone check using only the sample

clean:  ## Remove build outputs and caches (keeps committed marts)
	rm -rf build .pytest_cache .ruff_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
