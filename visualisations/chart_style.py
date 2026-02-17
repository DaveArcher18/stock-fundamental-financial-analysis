"""
Shared Design System — Chart Style
====================================
Consistent aesthetics across all valuation charts.
Publication-quality, FT/Economist-inspired.
"""

import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
from pathlib import Path
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load_company_config() -> tuple[str, str]:
    """Load company name and ticker from assumptions.yaml.

    Returns
    -------
    tuple[str, str]
        (company_name, ticker)
    """
    config_path = PROJECT_ROOT / "config" / "assumptions.yaml"
    with open(config_path) as f:
        config = yaml.safe_load(f)
    company = config.get("company", {})
    name = company.get("name", company.get("ticker", "Company"))
    ticker = company.get("ticker", "UNKNOWN")
    return name, ticker

# ═══════════════════════════════════════════════════════════════════════════
# Colour Palette
# ═══════════════════════════════════════════════════════════════════════════

COLORS = {
    # Primary
    "asml_blue": "#0066CC",
    "navy": "#1B2838",
    "dark_text": "#2C3E50",
    "light_text": "#7F8C8D",

    # Accents
    "amber": "#F5A623",
    "teal": "#1ABC9C",
    "coral": "#E74C3C",
    "green": "#27AE60",
    "purple": "#8E44AD",
    "steel": "#5D6D7E",

    # Zones (narrative acts — translucent)
    "zone_1": "#D5E8D4",   # Hidden champion — sage green
    "zone_2": "#DAE8FC",   # EUV inflection — light blue
    "zone_3": "#F8CECC",   # Premium monopoly — light coral

    # Chart elements
    "grid": "#E8E8E8",
    "bg": "#FAFAFA",
    "white": "#FFFFFF",
    "bar_positive": "#0066CC",
    "bar_negative": "#E74C3C",
}

# ═══════════════════════════════════════════════════════════════════════════
# Narrative Acts — date boundaries
# ═══════════════════════════════════════════════════════════════════════════

ACTS = {
    "act1": {"start": "2015-01-01", "end": "2017-12-31", "label": "Hidden Champion", "color": COLORS["zone_1"]},
    "act2": {"start": "2018-01-01", "end": "2021-12-31", "label": "EUV Inflection",  "color": COLORS["zone_2"]},
    "act3": {"start": "2022-01-01", "end": "2026-12-31", "label": "Premium Monopoly", "color": COLORS["zone_3"]},
}

# Key events for annotation
KEY_EVENTS = [
    ("2018-10-01", "First EUV\nshipment", 0.85),
    ("2020-03-15", "COVID\ndip",         0.15),
    ("2023-01-15", "ChatGPT /\nAI boom",  0.85),
    ("2024-11-14", "Investor Day\n2030 targets", 0.75),
]


# ═══════════════════════════════════════════════════════════════════════════
# matplotlib RC Defaults
# ═══════════════════════════════════════════════════════════════════════════

def apply_style():
    """Apply the chart style globally."""
    plt.rcParams.update({
        # Figure
        "figure.facecolor": COLORS["white"],
        "figure.figsize": (12, 6),
        "figure.dpi": 200,

        # Axes
        "axes.facecolor": COLORS["bg"],
        "axes.edgecolor": COLORS["grid"],
        "axes.labelcolor": COLORS["dark_text"],
        "axes.labelsize": 11,
        "axes.titlesize": 14,
        "axes.titleweight": "bold",
        "axes.titlepad": 16,
        "axes.grid": True,
        "axes.spines.top": False,
        "axes.spines.right": False,

        # Grid
        "grid.color": COLORS["grid"],
        "grid.linewidth": 0.6,
        "grid.alpha": 0.7,

        # Ticks
        "xtick.color": COLORS["light_text"],
        "ytick.color": COLORS["light_text"],
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,

        # Font
        "font.family": "sans-serif",
        "font.sans-serif": ["Inter", "Segoe UI", "Helvetica Neue", "Arial"],
        "font.size": 10,

        # Legend
        "legend.frameon": False,
        "legend.fontsize": 9,

        # Lines
        "lines.linewidth": 2.0,
        "lines.antialiased": True,
    })


# ═══════════════════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════════════════

def create_figure(width=12, height=6):
    """Create a styled figure and axes."""
    apply_style()
    fig, ax = plt.subplots(figsize=(width, height))
    return fig, ax


def add_narrative_zones(ax, date_index=None):
    """Add translucent shaded zones for the three narrative acts."""
    import pandas as pd

    for key, act in ACTS.items():
        start = pd.Timestamp(act["start"])
        end = pd.Timestamp(act["end"])

        # Clip to data range if provided
        if date_index is not None:
            start = max(start, date_index.min())
            end = min(end, date_index.max())

        if start < end:
            ax.axvspan(start, end, alpha=0.15, color=act["color"],
                       zorder=0, label=None)

            # Label at top
            mid = start + (end - start) / 2
            ax.text(mid, ax.get_ylim()[1] * 0.97, act["label"],
                    ha="center", va="top", fontsize=8, color=COLORS["light_text"],
                    fontstyle="italic", alpha=0.8)


def add_event_annotations(ax, events=None, y_data=None):
    """Add key event annotations with vertical lines."""
    import pandas as pd

    if events is None:
        events = KEY_EVENTS

    for date_str, label, y_pct in events:
        date = pd.Timestamp(date_str)
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()

        # Check if date is within x-axis range
        date_num = mpl.dates.date2num(date)
        if date_num < xlim[0] or date_num > xlim[1]:
            continue

        y_pos = ylim[0] + (ylim[1] - ylim[0]) * y_pct

        ax.axvline(date, color=COLORS["light_text"], linewidth=0.8,
                   linestyle="--", alpha=0.5, zorder=1)
        ax.annotate(label, xy=(date, y_pos),
                    fontsize=7, color=COLORS["dark_text"],
                    ha="center", va="center",
                    bbox=dict(boxstyle="round,pad=0.3", facecolor=COLORS["white"],
                              edgecolor=COLORS["grid"], alpha=0.9))


def add_source_footer(fig, source="SEC EDGAR XBRL + Yahoo Finance"):
    """Add a source attribution footer."""
    fig.text(0.99, 0.01, f"Source: {source}",
             ha="right", va="bottom", fontsize=7,
             color=COLORS["light_text"], fontstyle="italic")


def format_eur(x, pos):
    """Tick formatter for euro amounts."""
    return f"€{x:,.0f}"


def format_pct(x, pos):
    """Tick formatter for percentages."""
    return f"{x:.0f}%"


def format_billions(x, pos):
    """Tick formatter for billions."""
    return f"€{x/1e9:.0f}B"


def save_chart(fig, name: str, output_dir: str = "reports/charts"):
    """Save chart to the output directory."""
    from pathlib import Path
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{name}.png"
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  ✓ Saved → {path}")
    return path
