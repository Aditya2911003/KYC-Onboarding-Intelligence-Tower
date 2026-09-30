## What changed and why

## Checklist
- [ ] `ruff check .` and `ruff format --check .` pass
- [ ] `make etl-sample` succeeds and `mart_dq_report` has no `fail`
- [ ] `pytest -q` passes (including the AppTest smoke test)
- [ ] Every new number shown in the app or docs is computed from a mart, not typed in
- [ ] Any new simulated field carries the SIMULATED badge and is documented in `docs/methodology_and_limitations.md`
- [ ] No raw CSV, OCR text or `.duckdb` file is committed
