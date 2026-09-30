# Demo script

## 90-second version

1. **(0:00) Executive page.** "This is a control tower over 100,000 synthetic KYC onboarding cases. The red banner is the headline: the decision logic is 100% policy-compliant, but 74.9% of approvals carry a failed identity or address check — a control gap, not a logic error."
2. **(0:20) KPI cards and the purple pills.** "Approval rate 63.0%. Turnaround, SLA and open cases are marked SIMULATED — the source has no timestamps, so I generated them with a fixed seed and disclosed every parameter."
3. **(0:35) Click the Approve slice of the donut.** "Clicking cross-filters every page, like Power BI. Watch the Controls page keep the filter."
4. **(0:45) Controls page.** "100% rule-engine agreement on the left; 74.9% breach on the right; flat across countries and channels, so it is structural. Click a row — drill-through to Customer 360."
5. **(1:05) Customer 360 what-if.** "Here's why this customer was approved: rule R5 fired. Toggle PEP — the engine switches to Enhanced Due Diligence. Identity unverified never changes the outcome: that's the gap."
6. **(1:20) Close.** "It's backed by a tested DuckDB warehouse, 78 data-quality checks and CI. Code and docs are on GitHub."

## 5-minute version

1. **Problem (0:00–0:30).** Operations measure speed, compliance measures correctness; separate reports mean nobody sees both. Read the problem statement on the About page.
2. **Executive (0:30–1:15).** Headline finding, KPI cards with period deltas (switch Period to "Last 6 months" to show deltas), stacked monthly bars, moving average, insight strip. Point out the SIMULATED pills and that the curve reflects simulation parameters.
3. **Funnel (1:15–1:50).** 100,000 → 63,001; the PEP gate removes the most (18,475). Sankey shows High-risk cases splitting ~50/50 between EDD and Manual Review with no field explaining which. "Warehouse proof" tile: the same funnel computed with FILTER + UNPIVOT + FIRST_VALUE.
4. **Risk (1:50–2:10).** Flat labels: sanction 7.6%–8.2% by country, income quintiles identical. "I don't invent stories from flat data."
5. **Controls (2:10–3:00).** 100% agreement vs 74.9% breach; components; breach by country and channel; monthly trend flat; case table with drill-through and a capped, synthetic-labelled CSV export; GROUPING SETS proof.
6. **Documents & Review backlog (3:00–3:30).** 5.0% fail rate, confidence doesn't separate failures; 50.6% of customers overdue for review including 18,101 High-risk; the gauge.
7. **Customer 360 & what-if (3:30–4:00).** Rule path, risk score (illustrative), simulated timeline, toggles.
8. **AI Copilot (4:00–4:20).** 66.7% hallucinated, flat by question, 25 templates → detector perfect by construction; the caveat is the point.
9. **Model & method (4:20–4:45).** 95.5% vs 64.5%/63.0% baseline: a model cannot beat the policy. Simulation parameter table.
10. **Data quality & repo (4:45–5:00).** 78 checks, 0 fail; claims table 73/74 with the difference explained; lineage diagram. GitHub: SQL files, tests, CI badge.
