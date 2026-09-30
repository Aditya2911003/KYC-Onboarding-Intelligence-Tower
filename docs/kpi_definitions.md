# KPI definitions

Implemented once in `app/kpis.py` (pure functions plus the `KPI_SQL` snippets the dashboard runs in DuckDB), reused by every page, printed on the Data quality page, and tested in `tests/test_kpis.py` (which also proves each SQL snippet equals its Python function on a hand-built fixture).

* **Cases** = count of case_id. **Approval rate** = Approve / Cases. **EDD rate**, **Reject rate**, **Pending rate** analogous.
* **Avg turnaround (SIMULATED)** = mean tat_days; **p90 turnaround** = 90th percentile.
* **SLA breach %** = share of cases with tat_days greater than sla_days. **Open cases** = count where is_open.
* **Control-breach rate** = approvals with identity_verified = No OR address_verified = No, divided by approvals. Also report each component separately.
* **Rule-engine agreement** = share of cases where engine_agrees; a value below 100% raises a red alert banner.
* **Review overdue %** = share of customers whose last_updated is more than 365 days before 2026-06-30.
* **Document fail rate** = unverified documents / documents; **low-confidence rate** = Confidence below 0.85.
* **Hallucination rate** = hallucinated answers / all answers, by type, severity and question template.
* **Period-over-period delta** = (current minus previous equal-length period) / previous, previous period ending the day before the selected range starts.

## Implementation notes

| KPI | Python (`app/kpis.py`) | SQL snippet (`KPI_SQL`) | Delta polarity |
|---|---|---|---|
| Cases | `cases(df)` | `COUNT(*)` | up = good |
| Approval rate | `approval_rate(df)` | `AVG(CASE WHEN decision = 'Approve' THEN 1.0 ELSE 0.0 END)` | up = good |
| EDD / Reject / Pending rate | `decision_rate(df, d)` | `edd_rate`, `reject_rate`, `pending_rate` | neutral |
| Avg turnaround (SIMULATED) | `avg_turnaround(df)` | `AVG(tat_days)` | down = good |
| p90 turnaround (SIMULATED) | `p90_turnaround(df)` (linear interpolation) | `quantile_cont(tat_days, 0.9)` | down = good |
| SLA breach % (SIMULATED) | `sla_breach_pct(df)` | `AVG(CASE WHEN tat_days > sla_days THEN 1.0 ELSE 0.0 END)` | down = good |
| Open cases (SIMULATED) | `open_cases(df)` | `COUNT(*) FILTER (WHERE is_open)` | down = good |
| Control-breach rate (+ identity, address, missing-document components) | `control_breach_components(df)` | `control_breach_rate`, `breach_no_identity_rate`, `breach_no_address_rate`, `breach_missing_doc_rate` | down = good |
| Rule-engine agreement | `rule_engine_agreement(df)` | `AVG(CASE WHEN engine_agrees THEN 1.0 ELSE 0.0 END)` | up = good |
| Review overdue % | `review_overdue_pct(df)` | `AVG(CASE WHEN review_overdue THEN 1.0 ELSE 0.0 END)` | down = good |
| Document fail rate / low-confidence rate | `document_fail_rate(docs)`, `low_confidence_rate(docs)` | computed in the Documents page query | — |
| Hallucination rate | `hallucination_rate(h, n)` | `SUM(hallucinated) / SUM(answers)` over the AI marts | — |
| Period-over-period delta | `period_delta(cur, prev)`, `previous_period(start, end)` | the same KPI query run with the previous period's dates | per KPI |

When the selected range starts at the first simulated date there is no earlier period, so the cards show "vs prior period: n/a" rather than a misleading +∞%.
