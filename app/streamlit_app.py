"""KYC Onboarding Control Tower: Streamlit entrypoint (page config, theme, navigation).

Run with ``streamlit run app/streamlit_app.py``. The app reads only the Parquet
marts in ``data/marts`` (override with ``KYC_MARTS_DIR``).
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app import theme  # noqa: E402,F401  (registers the Plotly template)

st.set_page_config(
    page_title="KYC Onboarding Control Tower",
    page_icon=":material/verified_user:",
    layout="wide",
    initial_sidebar_state="collapsed",
)

PAGES = [
    st.Page("views/01_executive.py", title="Executive", icon=":material/dashboard:", default=True),
    st.Page("views/02_funnel.py", title="Funnel", icon=":material/filter_list:"),
    st.Page("views/03_risk.py", title="Risk", icon=":material/policy:"),
    st.Page("views/04_controls.py", title="Controls", icon=":material/gpp_bad:"),
    st.Page("views/05_documents.py", title="Documents", icon=":material/description:"),
    st.Page("views/06_operations.py", title="Operations", icon=":material/schedule:"),
    st.Page("views/07_review_backlog.py", title="Review backlog", icon=":material/event_repeat:"),
    st.Page("views/08_rules.py", title="Rules", icon=":material/gavel:"),
    st.Page("views/09_customer_360.py", title="Customer 360", icon=":material/person_search:"),
    st.Page("views/10_ai_copilot.py", title="AI Copilot", icon=":material/smart_toy:"),
    st.Page("views/11_model_method.py", title="Model & method", icon=":material/science:"),
    st.Page("views/12_data_quality.py", title="Data quality", icon=":material/fact_check:"),
    st.Page("views/13_about.py", title="About", icon=":material/info:"),
]

st.navigation(PAGES, position="top").run()
