"""Streamlit AppTest smoke tests against the committed marts.

Every page must render without exceptions, and setting a slicer must change a KPI.
"""

from __future__ import annotations

import re

import pytest
from streamlit.testing.v1 import AppTest

from tests.conftest import COMMITTED_MARTS, REPO_ROOT

APP = str(REPO_ROOT / "app" / "streamlit_app.py")
PAGES = sorted(p.name for p in (REPO_ROOT / "app" / "views").glob("[0-9][0-9]_*.py"))
pytestmark = pytest.mark.skipif(
    not (COMMITTED_MARTS / "mart_case_detail.parquet").exists(), reason="committed marts not present"
)


@pytest.fixture()
def app(monkeypatch: pytest.MonkeyPatch) -> AppTest:
    monkeypatch.setenv("KYC_MARTS_DIR", str(COMMITTED_MARTS))
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    return at


def kpi_values(at: AppTest) -> dict[str, str]:
    out = {}
    for block in at.markdown:
        match = re.search(r'kpi-label">([^<]+)<.*?kpi-value">([^<]+)<', block.value, re.S)
        if match:
            out[match.group(1).strip()] = match.group(2).strip()
    return out


def test_thirteen_pages_exist() -> None:
    assert len(PAGES) == 13


@pytest.mark.parametrize("page", PAGES)
def test_every_page_renders_without_exceptions(app: AppTest, page: str) -> None:
    app.switch_page(f"views/{page}")
    app.run()
    assert not app.exception, [e.message for e in app.exception]
    assert any("title-band" in m.value for m in app.markdown), "every page has the title band"


def test_setting_a_slicer_changes_the_kpis(app: AppTest) -> None:
    before = kpi_values(app)
    app.multiselect(key="w_risk").set_value(["High"]).run()
    after = kpi_values(app)
    assert not app.exception
    assert before["Cases"] != after["Cases"]
    assert before["Approval rate"] != after["Approval rate"]
    app.button(key="reset_filters").click().run()
    assert kpi_values(app)["Cases"] == before["Cases"]


def test_simulated_badges_are_visible_on_simulated_pages(app: AppTest) -> None:
    for page in ("01_executive.py", "06_operations.py"):
        app.switch_page(f"views/{page}")
        app.run()
        assert any("SIMULATED" in m.value for m in app.markdown)
