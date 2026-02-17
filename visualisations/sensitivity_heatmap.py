"""
Chart 8: Sensitivity Heatmap
===============================
DCF sensitivity table (Growth × WACC) as a diverging color heatmap.

Usage:
    python -m visualisations.sensitivity_heatmap
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from visualisations.chart_style import (
    COLORS, add_source_footer, save_chart, apply_style, get_output_dirs,
)


def plot_sensitivity_heatmap(output_dir="reports/charts"):
    """Chart 8: Growth × WACC sensitivity heatmap."""
    _, processed_dir = get_output_dirs()
    sensitivity = pd.read_csv(
        processed_dir / "sensitivity_growth_wacc.csv",
        index_col=0,
    )

    # Convert index and columns to percentages for display
    row_labels = [f"{float(r)*100:.0f}%" for r in sensitivity.index]
    col_labels = [f"{float(c)*100:.1f}%" for c in sensitivity.columns]
    values = sensitivity.values

    apply_style()
    fig, ax = plt.subplots(figsize=(14, 8))

    # Current market price for diverging colormap center
    market_price = 1277

    # Create diverging colormap: red (overvalued) → white (fair) → green (undervalued)
    cmap = mcolors.LinearSegmentedColormap.from_list(
        "valuation",
        [(0.0, "#E74C3C"),     # red — way below market
         (0.35, "#F5A623"),    # amber
         (0.5, "#FFFFFF"),     # white — at market
         (0.7, "#1ABC9C"),     # teal
         (1.0, "#27AE60")],   # green — above market
    )

    # Normalize around market price
    vmin = values.min()
    vmax = values.max()

    # Center on market price
    norm = mcolors.TwoSlopeNorm(vcenter=market_price, vmin=vmin, vmax=vmax)

    im = ax.imshow(values, cmap=cmap, norm=norm, aspect="auto")

    # Cell text
    for i in range(len(row_labels)):
        for j in range(len(col_labels)):
            val = values[i, j]
            text_color = COLORS["white"] if abs(val - market_price) > 400 else COLORS["dark_text"]
            weight = "bold" if abs(val - market_price) < 100 else "normal"
            ax.text(j, i, f"€{val:,.0f}", ha="center", va="center",
                    fontsize=9, color=text_color, fontweight=weight)

    # Labels
    ax.set_xticks(range(len(col_labels)))
    ax.set_xticklabels(col_labels, fontsize=9)
    ax.set_yticks(range(len(row_labels)))
    ax.set_yticklabels(row_labels, fontsize=10)
    ax.set_xlabel("WACC", fontsize=11, color=COLORS["dark_text"])
    ax.set_ylabel("Revenue Growth (Long-term)", fontsize=11, color=COLORS["dark_text"])

    ax.set_title(f"DCF Value/Share — Growth × WACC Sensitivity\n"
                 f"Market price: ~€{market_price:,} (white = at market)",
                 color=COLORS["navy"], fontsize=13, fontweight="bold")

    # Colorbar
    cbar = fig.colorbar(im, ax=ax, shrink=0.8, pad=0.02)
    cbar.set_label("Intrinsic Value/Share (EUR)", fontsize=9, color=COLORS["dark_text"])

    # Add market price line on colorbar
    cbar.ax.axhline(market_price, color=COLORS["navy"], linewidth=2, linestyle="-")
    cbar.ax.text(1.5, market_price, f"  ← Market €{market_price:,}", fontsize=8,
                 va="center", color=COLORS["navy"], fontweight="bold")

    add_source_footer(fig)
    return save_chart(fig, "08_sensitivity_heatmap", output_dir)


if __name__ == "__main__":
    plot_sensitivity_heatmap()
