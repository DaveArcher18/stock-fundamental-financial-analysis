"""
Charts 1 & 2: Valuation Multiples Over Time
=============================================
P/E ratio and EV/EBITDA plotted over time with narrative zone shading.

Usage:
    python -m visualisations.valuation_multiples
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
    COLORS, ACTS, KEY_EVENTS,
    create_figure, add_narrative_zones, add_event_annotations,
    add_source_footer, save_chart, apply_style, load_company_config,
    get_output_dirs,
)


def _load_data():
    """Load price history and annual financials, normalising timezones."""
    _, ticker = load_company_config()
    raw_dir, processed_dir = get_output_dirs()
    prices = pd.read_csv(
        raw_dir / f"{ticker.lower()}_price_history.csv",
        index_col=0, parse_dates=True,
    )
    # Normalise tz-aware index from yfinance to tz-naive
    prices.index = pd.to_datetime(prices.index, utc=True).tz_localize(None)

    financials = pd.read_csv(
        processed_dir / "financials_annual.csv",
        index_col=0, parse_dates=True,
    )
    return prices, financials


def _compute_trailing_pe(prices: pd.DataFrame, financials: pd.DataFrame) -> pd.Series:
    """Compute trailing P/E using the most recent annual EPS at each point in time."""
    close = prices["Close"].copy()

    # Build EPS time series from annual data
    eps_points = {}
    for idx, row in financials.iterrows():
        date = pd.Timestamp(idx)
        # Robust shares access
        shares = row.get("shares_outstanding")
        if pd.isna(shares) or shares == 0:
            shares = row.get("shares_outstanding_basic")
        if pd.isna(shares) or shares == 0:
            shares = row.get("common_shares_outstanding")
        
        # Fallback to config if available (not easily accessible here without plumbing)
        # For now, if shares are still missing, skip this point or use 1 to avoid ZeroDivision
        if pd.isna(shares) or shares == 0:
            continue

        eps = row["net_income"] / shares
        eps_points[date] = eps

    if not eps_points:
        return pd.Series(dtype=float)

    eps_series = pd.Series(eps_points).sort_index()

    # Forward-fill EPS to daily frequency
    eps_daily = eps_series.reindex(close.index, method="ffill")

    # P/E ratio
    pe = close / eps_daily
    pe = pe.replace([np.inf, -np.inf], np.nan)

    return pe


def _compute_trailing_ev_ebitda(prices: pd.DataFrame, financials: pd.DataFrame) -> pd.Series:
    """Compute trailing EV/EBITDA using daily market cap and most recent annual EBITDA."""
    close = prices["Close"].copy()

    # Build EBITDA and shares time series
    ebitda_points = {}
    shares_points = {}
    net_debt_points = {}

    for idx, row in financials.iterrows():
        date = pd.Timestamp(idx)
        ebitda = row.get("operating_income", 0) + row.get("depreciation", 0)
        ebitda_points[date] = ebitda
        
        # Robust shares access
        shares = row.get("shares_outstanding")
        if pd.isna(shares) or shares == 0:
            shares = row.get("shares_outstanding_basic")
        if pd.isna(shares) or shares == 0:
            shares = row.get("common_shares_outstanding")
        
        shares_points[date] = shares if pd.notna(shares) else np.nan
        
        net_debt = row.get("long_term_debt", 0) - row.get("cash", 0)
        net_debt_points[date] = net_debt

    ebitda_daily = pd.Series(ebitda_points).sort_index().reindex(close.index, method="ffill")
    shares_daily = pd.Series(shares_points).sort_index().reindex(close.index, method="ffill")
    net_debt_daily = pd.Series(net_debt_points).sort_index().reindex(close.index, method="ffill")

    # EV = market_cap + net_debt  (price is USD, financials in EUR — use as proxy)
    market_cap = close * shares_daily
    ev = market_cap + net_debt_daily

    ev_ebitda = ev / ebitda_daily
    ev_ebitda = ev_ebitda.replace([np.inf, -np.inf], np.nan)

    return ev_ebitda


def plot_pe_ratio(prices, financials, output_dir="reports/charts"):
    """Chart 1: P/E ratio over time."""
    pe = _compute_trailing_pe(prices, financials)
    pe = pe.dropna()

    # Trim to financials range
    pe = pe[pe.index >= "2015-01-01"]

    fig, ax = create_figure(12, 6)

    # Plot
    ax.plot(pe.index, pe.values, color=COLORS["asml_blue"], linewidth=1.5, alpha=0.8)

    # Add rolling average
    pe_smooth = pe.rolling(60, min_periods=30).median()
    ax.plot(pe_smooth.index, pe_smooth.values, color=COLORS["navy"],
            linewidth=2.5, label="60-day median")

    # Zone shading
    add_narrative_zones(ax, pe.index)

    # Horizontal reference lines
    median_pe = pe.median()
    ax.axhline(median_pe, color=COLORS["amber"], linewidth=1.5,
               linestyle="--", alpha=0.7, label=f"Median P/E: {median_pe:.0f}x")

    # Labels
    company_name, _ = load_company_config()
    start_yr = pe.index.min().year
    end_yr = pe.index.max().year
    ax.set_title(f"{company_name} — Trailing P/E Ratio ({start_yr}–{end_yr})", color=COLORS["navy"])
    ax.set_ylabel("P/E Ratio (×)", color=COLORS["dark_text"])
    ax.set_xlabel("")

    # Set reasonable y limits
    ax.set_ylim(0, min(pe.quantile(0.98) * 1.1, 120))

    # Legend
    ax.legend(loc="upper left")

    # Event annotations (call after setting ylim)
    add_event_annotations(ax)

    # Latest value callout
    latest_pe = pe.iloc[-1]
    ax.annotate(f"Current: {latest_pe:.0f}×",
                xy=(pe.index[-1], latest_pe),
                xytext=(-60, 20), textcoords="offset points",
                fontsize=9, fontweight="bold", color=COLORS["coral"],
                arrowprops=dict(arrowstyle="->", color=COLORS["coral"], lw=1.5))

    add_source_footer(fig)
    return save_chart(fig, "01_pe_ratio", output_dir)


def plot_ev_ebitda(prices, financials, output_dir="reports/charts"):
    """Chart 2: EV/EBITDA over time."""
    ev_ebitda = _compute_trailing_ev_ebitda(prices, financials)
    ev_ebitda = ev_ebitda.dropna()
    ev_ebitda = ev_ebitda[ev_ebitda.index >= "2015-01-01"]

    fig, ax = create_figure(12, 6)

    # Plot
    ax.plot(ev_ebitda.index, ev_ebitda.values, color=COLORS["teal"], linewidth=1.5, alpha=0.8)

    # Rolling median
    smooth = ev_ebitda.rolling(60, min_periods=30).median()
    ax.plot(smooth.index, smooth.values, color=COLORS["navy"],
            linewidth=2.5, label="60-day median")

    # Zone shading
    add_narrative_zones(ax, ev_ebitda.index)

    # Reference lines
    median_val = ev_ebitda.median()
    ax.axhline(median_val, color=COLORS["amber"], linewidth=1.5,
               linestyle="--", alpha=0.7, label=f"Median: {median_val:.0f}×")

    # Labels
    company_name, _ = load_company_config()
    start_yr = ev_ebitda.index.min().year
    end_yr = ev_ebitda.index.max().year
    ax.set_title(f"{company_name} — Trailing EV/EBITDA ({start_yr}–{end_yr})", color=COLORS["navy"])
    ax.set_ylabel("EV/EBITDA (×)", color=COLORS["dark_text"])
    ax.set_xlabel("")
    ax.set_ylim(0, min(ev_ebitda.quantile(0.98) * 1.1, 100))

    ax.legend(loc="upper left")
    add_event_annotations(ax)

    # Latest callout
    latest = ev_ebitda.iloc[-1]
    ax.annotate(f"Current: {latest:.0f}×",
                xy=(ev_ebitda.index[-1], latest),
                xytext=(-60, 20), textcoords="offset points",
                fontsize=9, fontweight="bold", color=COLORS["coral"],
                arrowprops=dict(arrowstyle="->", color=COLORS["coral"], lw=1.5))

    add_source_footer(fig)
    return save_chart(fig, "02_ev_ebitda", output_dir)


if __name__ == "__main__":
    prices, financials = _load_data()
    plot_pe_ratio(prices, financials)
    plot_ev_ebitda(prices, financials)
