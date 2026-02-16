"""
Chart 7: FCF Yield Over Time
===============================
Free cash flow yield (FCF / market cap) — declining as price rises.

Usage:
    python -m visualisations.fcf_yield
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


def plot_fcf_yield(output_dir="reports/charts"):
    """Chart 7: FCF yield over time."""
    prices = pd.read_csv(
        PROJECT_ROOT / "data" / "raw" / "asml_price_history.csv",
        index_col=0, parse_dates=True,
    )
    prices.index = pd.to_datetime(prices.index, utc=True).tz_localize(None)
    financials = pd.read_csv(
        PROJECT_ROOT / "data" / "processed" / "financials_annual.csv",
        index_col=0, parse_dates=True,
    )

    years = financials["fiscal_year"].astype(int).values
    ocf = financials["operating_cash_flow"].values
    capex = financials["capex"].values
    fcf = ocf - capex

    # Get year-end prices and compute market cap
    mkt_caps = []
    for idx, row in financials.iterrows():
        fy_end = pd.Timestamp(idx)
        # Find closest price to fiscal year-end
        closest = prices.index[prices.index.get_indexer([fy_end], method="nearest")[0]]
        price_usd = prices.loc[closest, "Close"]
        mkt_cap_usd = price_usd * row["shares_outstanding"]
        mkt_cap_eur = mkt_cap_usd * 0.92
        mkt_caps.append(mkt_cap_eur)

    mkt_caps = np.array(mkt_caps)

    # FCF Yield
    fcf_yield = fcf / mkt_caps * 100

    fig, ax = create_figure(12, 6)

    # Bar chart
    bar_colors = [COLORS["green"] if y > 2 else
                  COLORS["amber"] if y > 1 else
                  COLORS["coral"] for y in fcf_yield]

    bars = ax.bar(years, fcf_yield, width=0.7, color=bar_colors,
                  edgecolor=COLORS["white"], linewidth=0.5, zorder=3)

    # Value labels
    for bar, yld in zip(bars, fcf_yield):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.15,
                f"{yld:.1f}%", ha="center", va="bottom", fontsize=9,
                fontweight="bold", color=COLORS["dark_text"])

    # Reference lines
    ax.axhline(3, color=COLORS["green"], linewidth=1, linestyle=":",
               alpha=0.6, label="Attractive yield (>3%)")
    ax.axhline(1, color=COLORS["coral"], linewidth=1, linestyle=":",
               alpha=0.6, label="Low yield (<1%)")

    # Trend line
    z = np.polyfit(range(len(years)), fcf_yield, 1)
    trend = np.polyval(z, range(len(years)))
    ax.plot(years, trend, color=COLORS["navy"], linewidth=2,
            linestyle="--", alpha=0.5, label="Trend")

    ax.set_title("ASML — Free Cash Flow Yield\n"
                 "(Operating CF − Capex) / Market Cap",
                 color=COLORS["navy"])
    ax.set_ylabel("FCF Yield (%)", color=COLORS["dark_text"])
    ax.set_xticks(years)
    ax.set_xticklabels([str(y) for y in years], rotation=45, ha="right")
    ax.set_ylim(0, max(fcf_yield) * 1.3)

    ax.legend(loc="upper right")
    add_source_footer(fig)
    return save_chart(fig, "07_fcf_yield", output_dir)


if __name__ == "__main__":
    plot_fcf_yield()
