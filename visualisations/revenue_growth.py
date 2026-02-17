"""
Chart 3: Revenue Over Time
============================
Annual revenue bar chart with YoY growth rate overlay.

Usage:
    python -m visualisations.revenue_growth
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from visualisations.chart_style import (
    COLORS, create_figure, add_source_footer, save_chart,
    format_billions, apply_style, load_company_config,
    get_output_dirs,
)


def plot_revenue_growth(output_dir="reports/charts"):
    """Chart 3: Revenue bars with growth overlay."""
    _, processed_dir = get_output_dirs()
    financials = pd.read_csv(
        processed_dir / "financials_annual.csv",
        index_col=0, parse_dates=True,
    )

    years = financials["fiscal_year"].astype(int).values
    revenue = financials["revenue"].values

    # Compute growth
    growth = [np.nan] + [
        (revenue[i] / revenue[i - 1] - 1) * 100
        for i in range(1, len(revenue))
    ]
    growth = np.array(growth)

    # CAGR
    n = len(revenue) - 1
    cagr = (revenue[-1] / revenue[0]) ** (1 / n) - 1

    fig, ax1 = create_figure(12, 6)

    # Revenue bars — color by growth rate
    bar_colors = []
    for g in growth:
        if np.isnan(g):
            bar_colors.append(COLORS["asml_blue"])
        elif g >= 20:
            bar_colors.append(COLORS["asml_blue"])
        elif g >= 10:
            bar_colors.append("#4A90D9")
        elif g >= 0:
            bar_colors.append("#7FB3E0")
        else:
            bar_colors.append(COLORS["coral"])

    bars = ax1.bar(years, revenue, color=bar_colors, width=0.7,
                   edgecolor=COLORS["white"], linewidth=0.5, zorder=3)

    # Value labels on bars
    for bar, rev in zip(bars, revenue):
        ax1.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + revenue.max() * 0.01,
                 f"€{rev/1e9:.1f}B", ha="center", va="bottom", fontsize=8,
                 color=COLORS["dark_text"], fontweight="bold")

    ax1.set_ylabel("Revenue (€B)", color=COLORS["dark_text"])
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(format_billions))
    ax1.set_ylim(0, revenue.max() * 1.15)

    # Growth rate line on secondary axis
    ax2 = ax1.twinx()
    valid_mask = ~np.isnan(growth)
    ax2.plot(years[valid_mask], growth[valid_mask], color=COLORS["amber"],
             linewidth=2.5, marker="o", markersize=6, zorder=5,
             markeredgecolor=COLORS["white"], markeredgewidth=1.5)

    # Growth rate labels
    for yr, g in zip(years[valid_mask], growth[valid_mask]):
        ax2.text(yr, g + 2, f"{g:+.0f}%", ha="center", va="bottom",
                 fontsize=8, color=COLORS["amber"], fontweight="bold")

    ax2.set_ylabel("YoY Growth (%)", color=COLORS["amber"])
    ax2.tick_params(axis="y", colors=COLORS["amber"])
    ax2.spines["right"].set_visible(True)
    ax2.spines["right"].set_color(COLORS["amber"])
    ax2.axhline(0, color=COLORS["light_text"], linewidth=0.8, linestyle=":", alpha=0.5)

    # Set growth axis range
    g_min = np.nanmin(growth) - 5
    g_max = np.nanmax(growth) + 10
    ax2.set_ylim(g_min, g_max)

    # Title with CAGR
    company_name, _ = load_company_config()
    ax1.set_title(f"{company_name} — Revenue & Growth (FY{years[0]}–{years[-1]})\n"
                  f"{n}-year CAGR: {cagr*100:.1f}%",
                  color=COLORS["navy"])
    ax1.set_xlabel("")

    # X-axis cleanup
    ax1.set_xticks(years)
    ax1.set_xticklabels([str(y) for y in years], rotation=45, ha="right")

    add_source_footer(fig)
    return save_chart(fig, "03_revenue_growth", output_dir)


if __name__ == "__main__":
    plot_revenue_growth()
