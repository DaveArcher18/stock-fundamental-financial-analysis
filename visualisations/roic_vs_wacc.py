"""
Chart 6: ROIC vs. WACC
========================
Dual-bar chart showing ROIC and WACC spread — economic moat widening.

Usage:
    python -m visualisations.roic_vs_wacc
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from visualisations.chart_style import (
    COLORS, create_figure, add_source_footer, save_chart, load_company_config,
)


def plot_roic_vs_wacc(output_dir="reports/charts"):
    """Chart 6: ROIC vs WACC bar chart with economic spread."""
    roic_df = pd.read_csv(
        PROJECT_ROOT / "data" / "processed" / "roic_analysis.csv", index_col=0,
    )

    years = roic_df["fiscal_year"].astype(int).values
    roic = roic_df["roic"].values * 100

    # Skip first year if NaN
    valid = ~np.isnan(roic)
    years = years[valid]
    roic = roic[valid]

    # WACC = 8.46% (from our data-driven calculation)
    wacc = 8.46

    fig, ax = create_figure(12, 6)

    x = np.arange(len(years))
    bar_width = 0.5

    # ROIC bars — color by whether spread is positive
    bar_colors = [COLORS["asml_blue"] if r > wacc else COLORS["coral"] for r in roic]
    bars = ax.bar(x, roic, bar_width, color=bar_colors, edgecolor=COLORS["white"],
                  linewidth=0.5, zorder=3, label="ROIC")

    # WACC line
    ax.axhline(wacc, color=COLORS["amber"], linewidth=2.5, linestyle="--",
               zorder=4, label=f"WACC ({wacc:.1f}%)")

    # Shade the spread
    for i, (yr, r) in enumerate(zip(x, roic)):
        if r > wacc:
            ax.fill_between([yr - bar_width/2, yr + bar_width/2], wacc, r,
                           alpha=0.15, color=COLORS["green"], zorder=2)

    # Value labels
    for i, (xi, r) in enumerate(zip(x, roic)):
        ax.text(xi, r + 0.8, f"{r:.0f}%", ha="center", va="bottom",
                fontsize=9, fontweight="bold", color=bar_colors[i])

    # Spread annotation for latest year
    spread = roic[-1] - wacc
    mid = wacc + spread / 2
    ax.annotate(f"Spread:\n{spread:+.0f}pp",
                xy=(x[-1] + 0.4, mid), fontsize=9, fontweight="bold",
                color=COLORS["green"], ha="left", va="center",
                bbox=dict(boxstyle="round,pad=0.3", facecolor=COLORS["white"],
                          edgecolor=COLORS["green"], alpha=0.9))

    company_name, _ = load_company_config()
    ax.set_title(f"{company_name} — ROIC vs. Cost of Capital", color=COLORS["navy"])
    ax.set_ylabel("Return / Cost (%)", color=COLORS["dark_text"])
    ax.set_xticks(x)
    ax.set_xticklabels([str(y) for y in years], rotation=45, ha="right")
    ax.set_ylim(0, max(roic) * 1.2)

    ax.legend(loc="upper left")
    add_source_footer(fig)
    return save_chart(fig, "06_roic_vs_wacc", output_dir)


if __name__ == "__main__":
    plot_roic_vs_wacc()
