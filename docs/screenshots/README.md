# Screenshots

Captured with `python scripts/capture_screenshots.py` (Playwright + headless Chromium, 1440 px wide, full data marts):

| File | Page |
|---|---|
| `01_executive.png` | Executive overview |
| `02_funnel.png` | Funnel and decisions |
| `03_risk.png` | Risk and screening |
| `04_controls.png` | Controls and compliance |
| `05_documents.png` | Documents and OCR |
| `06_operations.png` | Operations and SLA (SIMULATED) |
| `07_review_backlog.png` | Periodic review backlog |
| `08_rules.png` | Rules and policy |
| `09_customer_360.png` | Customer 360 and what-if |
| `10_ai_copilot.png` | AI Copilot quality |
| `11_model_method.png` | Model and method |
| `12_data_quality.png` | Data quality and definitions |
| `13_about.png` | About |
| `mobile_executive.png` | Executive at phone width (390 px): slicers and tiles stack, no horizontal scroll |
| `demo.gif` | Executive → donut cross-filter → Controls → Customer 360 → AI Copilot |

If you re-deploy and want fresh shots for the README and LinkedIn post, the six that matter most are: **Executive, Funnel, Controls, Operations, Customer 360 what-if, AI Copilot**. Re-run `make screenshots` after any visual change.
