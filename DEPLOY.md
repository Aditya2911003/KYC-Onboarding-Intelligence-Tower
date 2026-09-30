# Deploy: GitHub + Streamlit Community Cloud

## 1. GitHub

```bash
cd kyc-onboarding-control-tower
git init
git add .
git commit -m "KYC Onboarding Control Tower: warehouse, marts, dashboard, tests, docs"
git branch -M main
# create the public repo (GitHub CLI) and push
gh repo create GITHUB_USERNAME/kyc-onboarding-control-tower --public --source=. --remote=origin --push
# or, without the CLI: create an empty public repo named kyc-onboarding-control-tower on github.com, then
git remote add origin https://github.com/GITHUB_USERNAME/kyc-onboarding-control-tower.git
git push -u origin main
```

Before pushing, confirm nothing large or raw is staged:

```bash
git ls-files | grep -E '\.csv$' | grep -v '^data/sample/'   # must print nothing
git ls-files | grep -E '\.duckdb|OCRText'                   # must print nothing
git ls-files -z | xargs -0 du -ch | tail -1                 # total well under 100 MB
```

Repository settings:

```bash
gh repo edit GITHUB_USERNAME/kyc-onboarding-control-tower \
  --description "Interactive KYC onboarding and control-assurance dashboard: SQL warehouse (DuckDB), rule-engine reconciliation, simulated SLA analytics, Streamlit UI." \
  --add-topic streamlit --add-topic duckdb --add-topic kyc --add-topic aml --add-topic compliance \
  --add-topic data-analytics --add-topic sql --add-topic python --add-topic portfolio-project --add-topic dashboard \
  --enable-issues
```

Then on github.com: pin the repository on your profile, and (after step 2) put the live app URL in the repo **Website** field:

```bash
gh repo edit GITHUB_USERNAME/kyc-onboarding-control-tower --homepage https://kyc-onboarding-control-tower.streamlit.app
```

The CI workflow runs on the first push; the README badge turns green when lint, the sample ETL, pytest and the AppTest smoke test pass.

## 2. Streamlit Community Cloud

1. Sign in at <https://share.streamlit.io> with GitHub, choose **Create app → Deploy a public app from GitHub**, select `GITHUB_USERNAME/kyc-onboarding-control-tower`, branch `main`.
2. **Main file path:** `app/streamlit_app.py`. Open **Advanced settings**, choose **Python 3.11**. No secrets are required. Set the **App URL** (custom subdomain) to `kyc-onboarding-control-tower` so it matches the README badge; if that subdomain is taken, choose another and update the badge link in `README.md` and the link in `docs/linkedin_post.md`.
3. Deploy. The app installs only `requirements.txt` (streamlit, duckdb, pandas, plotly, pyarrow) and reads only `data/marts/*.parquet` (~2.7 MB), so memory stays far below the 2.7 GB limit — check **Manage app → Resources** after clicking through every page. The app sleeps after 12 hours without traffic; the first visit afterwards shows the "wake up" screen (mentioned in the README) and takes about a minute.
4. Copy the app URL into the README badge (if it differs), the GitHub **Website** field (command above) and the LinkedIn post.

## 3. Refreshing the data

```bash
make raw etl ml         # rebuild marts from archive.zip
make test lint          # must pass
make screenshots        # optional: refresh docs/screenshots
git add data/marts docs/screenshots && git commit -m "Refresh marts" && git push
```

Streamlit Cloud redeploys automatically on push.
