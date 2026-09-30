"""Design system: Power BI classic palette, CSS, Plotly template and number formats."""

from __future__ import annotations

import math

import plotly.graph_objects as go
import plotly.io as pio

# Canvas and tiles.
CANVAS = "#EAEAEA"
TILE = "#FFFFFF"
TILE_BORDER = "#D9D9D9"
TITLE_BAND = "#374649"
TEXT = "#252423"
MUTED = "#605E5C"

# Power BI classic palette.
TEAL = "#01B8AA"
CHARCOAL = "#374649"
RED = "#FD625E"
YELLOW = "#F2C80F"
GREY = "#5F6B6D"
SKY = "#8AD4EB"
ORANGE = "#FE9666"
PURPLE = "#A66999"
PALETTE = [TEAL, CHARCOAL, RED, YELLOW, GREY, SKY, ORANGE, PURPLE]
GOOD = "#107C10"
BAD = "#D13438"

DECISION_ORDER = ["Approve", "Enhanced Due Diligence", "Manual Review", "Pending Documents", "Reject"]
DECISION_COLORS = {
    "Approve": TEAL,
    "Enhanced Due Diligence": YELLOW,
    "Manual Review": ORANGE,
    "Pending Documents": SKY,
    "Reject": RED,
}
# Patterns so decision colours are never the only encoding in stacked bars.
DECISION_PATTERNS = {
    "Approve": "",
    "Enhanced Due Diligence": "/",
    "Manual Review": "x",
    "Pending Documents": ".",
    "Reject": "\\",
}
RISK_ORDER = ["Low", "Medium", "High"]
RISK_COLORS = {"Low": TEAL, "Medium": YELLOW, "High": RED}
FONT_FAMILY = "Segoe UI, 'Source Sans Pro', Helvetica, Arial, sans-serif"

CSS = f"""
<style>
.stApp {{ background-color: {CANVAS}; }}
.block-container {{ padding-top: 3.2rem; padding-bottom: 2rem; max-width: 100%; }}
html, body, .stApp {{ overflow-x: hidden; font-family: {FONT_FAMILY}; }}
div[data-testid="stVerticalBlockBorderWrapper"]:has(> div > div > div.tile-marker),
div[data-testid="stVerticalBlock"]:has(> div.stElementContainer > div > div.tile-marker) {{
    background: {TILE}; border: 1px solid {TILE_BORDER} !important; border-radius: 4px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}}
.st-key-slicer_bar, [class*="st-key-tile_"], [class*="st-key-kpi_"] {{
    background: {TILE}; border: 1px solid {TILE_BORDER}; border-radius: 4px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08); padding: 10px 12px 6px 12px;
}}
[class*="st-key-kpi_"] {{ min-height: 128px; }}
.title-band {{
    background: {TITLE_BAND}; color: #FFFFFF; border-radius: 4px; padding: 12px 18px;
    display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px;
}}
.title-band h1 {{ color: #FFFFFF; font-size: 1.45rem; margin: 0; padding: 0; font-weight: 600; }}
.title-band .question {{ color: #D9E1E2; font-size: 0.85rem; margin-top: 2px; }}
.sim-pill {{
    display: inline-block; background: {PURPLE}; color: #FFFFFF; font-size: 10px; font-weight: 700;
    letter-spacing: 0.06em; padding: 2px 8px; border-radius: 10px; text-transform: uppercase;
    vertical-align: middle; margin-left: 6px;
}}
.real-pill {{
    display: inline-block; background: {TEAL}; color: #FFFFFF; font-size: 10px; font-weight: 700;
    letter-spacing: 0.06em; padding: 2px 8px; border-radius: 10px; text-transform: uppercase;
    vertical-align: middle; margin-left: 6px;
}}
.tile-title {{ font-size: 13px; font-weight: 600; color: {TEXT}; margin-bottom: 2px; }}
.tile-sub {{ font-size: 11px; color: {MUTED}; margin-bottom: 4px; }}
.kpi-label {{ font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em; color: {MUTED}; }}
.kpi-value {{ font-size: 32px; font-weight: 600; color: {TEXT}; line-height: 1.15; }}
.kpi-delta {{ font-size: 12px; font-weight: 600; }}
.kpi-foot {{ font-size: 11px; color: {MUTED}; }}
.insight-strip {{
    background: #FFFFFF; border-left: 4px solid {TEAL}; border-radius: 4px; padding: 8px 14px;
    font-size: 14px; color: {TEXT}; border-top: 1px solid {TILE_BORDER};
    border-right: 1px solid {TILE_BORDER}; border-bottom: 1px solid {TILE_BORDER};
}}
.insight-strip ul {{ margin: 0; padding-left: 18px; }}
.headline {{
    background: #FFFFFF; border-left: 6px solid {BAD}; border-radius: 4px; padding: 12px 16px;
    font-size: 15px; color: {TEXT}; border-top: 1px solid {TILE_BORDER};
    border-right: 1px solid {TILE_BORDER}; border-bottom: 1px solid {TILE_BORDER};
}}
.alert-banner {{ background: {BAD}; color: #FFFFFF; padding: 10px 14px; border-radius: 4px; font-weight: 600; }}
.footnote {{ font-size: 11px; color: {MUTED}; margin-top: 4px; }}
.big-card {{ text-align: center; padding: 6px 0; }}
.big-card .v {{ font-size: 44px; font-weight: 700; line-height: 1.1; }}
.big-card .l {{ font-size: 13px; color: {MUTED}; }}
.author-card {{ background: #FFFFFF; border: 1px solid {TILE_BORDER}; border-radius: 4px; padding: 14px; }}
@media (max-width: 640px) {{
    .kpi-value {{ font-size: 26px; }}
    .title-band h1 {{ font-size: 1.15rem; }}
    .big-card .v {{ font-size: 34px; }}
}}
</style>
"""


def plotly_template() -> go.layout.Template:
    """Return the shared Plotly template (white tiles, light grid, PBI palette)."""
    template = go.layout.Template()
    template.layout = go.Layout(
        font=dict(family=FONT_FAMILY, size=12, color=TEXT),
        paper_bgcolor=TILE,
        plot_bgcolor=TILE,
        colorway=PALETTE,
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(gridcolor=CANVAS, zerolinecolor=TILE_BORDER, linecolor=TILE_BORDER, automargin=True),
        yaxis=dict(gridcolor=CANVAS, zerolinecolor=TILE_BORDER, linecolor=TILE_BORDER, automargin=True),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, font=dict(size=11)),
        hoverlabel=dict(bgcolor="#FFFFFF", bordercolor=TILE_BORDER, font=dict(family=FONT_FAMILY, size=12)),
        separators=".,",
    )
    return template


pio.templates["kyc_pbi"] = plotly_template()
pio.templates.default = "kyc_pbi"


def fmt_int(value: float | int | None) -> str:
    """Format a count with thousands separators ('—' when missing)."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "—"
    return f"{round(float(value)):,}"


def fmt_pct(value: float | None, digits: int = 1) -> str:
    """Format a 0-1 ratio as a percentage with one decimal ('—' when missing)."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "—"
    return f"{100 * value:,.{digits}f}%"


def fmt_days(value: float | None) -> str:
    """Format a duration in days as '4.6 d' ('—' when missing)."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "—"
    return f"{value:,.1f} d"
