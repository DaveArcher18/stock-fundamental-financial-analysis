"""
Chart 5: Margin Evolution
===========================
Gross, operating, and net margin as layered area chart.

Usage:
    python -m visualisations.margin_evolution
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from visualisations.chart_style import (
    COLORS, create_figure, add_source_footer, save_chart,
)


def plot_margin_evolution(output_dir="reports/charts"):
    """Chart 5: Margin progression — gross, operating, net."""
    ratios = pd.read_csv(
        PROJECT_ROOT / "data" / "processed" / "financial_ratios.csv", index_col=0,
    )

    years = ratios["fiscal_year"].astype(int).values
    gm = ratios["gross_margin"].values * 100
    om = ratios["operating_margin"].values * 100
    nm = ratios["net_margin"].values * 100

    fig, ax = create_figure(12, 6)

    # Stacked area (layered — gross on top, then operating, then net)
    ax.fill_between(years, 0, gm, alpha=0.2, color=COLORS["asml_blue"], label="Gross margin")
    ax.fill_between(years, 0, om, alpha=0.3, color=COLORS["teal"], label="Operating margin")
    ax.fill_between(years, 0, nm, alpha=0.4, color=COLORS["green"], label="Net margin")

    # Lines on top
    ax.plot(years, gm, color=COLORS["asml_blue"], linewidth=2.5, marker="o",
            markersize=6, markeredgecolor=COLORS["white"], markeredgewidth=1.5)
    ax.plot(years, om, color=COLORS["teal"], linewidth=2.5, marker="s",
            markersize=5, markeredgecolor=COLORS["white"], markeredgewidth=1.5)
    ax.plot(years, nm, color=COLORS["green"], linewidth=2.5, marker="D",
            markersize=5, markeredgecolor=COLORS["white"], markeredgewidth=1.5)

    # Value labels
    for i, yr in enumerate(years):
        if i % 2 == 0 or i == len(years) - 1:  # Every other year + latest
            ax.text(yr, gm[i] + 1.5, f"{gm[i]:.0f}%", ha="center", fontsize=7,
                    color=COLORS["asml_blue"], fontweight="bold")
            ax.text(yr, om[i] + 1.5, f"{om[i]:.0f}%", ha="center", fontsize=7,
                    color=COLORS["teal"], fontweight="bold")

    # 2030 target zone
    ax.axhspan(56, 60, alpha=0.08, color=COLORS["amber"], zorder=0)
    ax.text(years[-1] + 0.5, 58, "2030 GM\ntarget\n56–60%", fontsize=7,
            color=COLORS["amber"], va="center", fontweight="bold")

    ax.set_title("ASML — Margin Evolution", color=COLORS["navy"])
    ax.set_ylabel("Margin (%)", color=COLORS["dark_text"])
    ax.set_ylim(0, 65)
    ax.set_xticks(years)
    ax.set_xticklabels([str(y) for y in years], rotation=45, ha="right")

    ax.legend(loc="lower right")
    add_source_footer(fig)
    return save_chart(fig, "05_margin_evolution", output_dir)


if __name__ == "__main__":
    plot_margin_evolution()
