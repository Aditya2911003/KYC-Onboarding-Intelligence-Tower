# LinkedIn launch post (3 variants)

Live app: https://kyc-onboarding-control-tower.streamlit.app · Code: https://github.com/GITHUB_USERNAME/kyc-onboarding-control-tower
Attach: `docs/screenshots/01_executive.png` or `docs/screenshots/demo.gif`.

## Variant 1 — finding first

74.9% of approved customers had a failed identity or address check.

And yet the onboarding decisions were 100% consistent with policy.

I built a KYC Onboarding Control Tower over 100,000 synthetic onboarding cases to join two views that usually live apart: how fast cases move (operations) and whether decisions are right (compliance).

What the data showed:
• A 5-rule engine (sanctions → PEP → high risk → documents → approve) reproduces 100% of 100,000 labelled decisions.
• But identity and address verification are not part of that logic: 47,157 of 63,001 approvals carry at least one failed flag.
• That is a control gap, not a logic error — the fix is a hard verification gate.
• 50.6% of customers are overdue for periodic review, at the same rate for high- and low-risk customers.

Built with a DuckDB SQL warehouse (window functions, UNPIVOT, QUALIFY, GROUPING SETS), a Power BI-style Streamlit app (slicers, cross-filtering, drill-through), 86 tests and CI. Turnaround and SLA fields are simulated (seed 42) and labelled as such on every visual.

Live app and code in the comments. Feedback welcome.

#DataAnalytics #SQL #KYC #AML #Compliance #Streamlit #DuckDB

## Variant 2 — engineering first

Can you prove a compliance decision followed policy for 100% of cases?

In my latest portfolio project I did it with SQL: a recovered rule engine in DuckDB re-derives all 100,000 synthetic KYC decisions and matches every one. Then the same warehouse shows the uncomfortable part — 74.9% of approvals skipped a failed identity or address check.

Under the hood:
• Reproducible pipeline: one command builds the warehouse in ~30 s and exports 2.7 MB of Parquet marts
• 78 data-quality checks (0 fail) and a claimed-vs-measured table for every fact I was given
• Two honest ML experiments: 95.5% with the policy fields, 64.5% vs a 63.0% baseline without them — a model cannot beat the policy
• 13-page Streamlit dashboard with Power BI behaviour, AppTest smoke tests and GitHub Actions

Link in the comments.

#AnalyticsEngineering #SQL #DuckDB #Python #Streamlit #PortfolioProject

## Variant 3 — short

Decisions: 100% policy-compliant. Controls: 74.9% of approvals passed with a failed ID or address check.

That's the headline from my KYC Onboarding Control Tower — a SQL warehouse + Power BI-style Streamlit dashboard over 100,000 synthetic onboarding cases, with every simulated field clearly flagged.

App and repo in the comments.

#KYC #Compliance #DataAnalytics #SQL #Streamlit
