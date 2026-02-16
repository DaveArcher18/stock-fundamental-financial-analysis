"""
Insights — Historical Analysis
================================
Functions to summarise and visualise historical financial trends,
ratio evolution, and cycle positioning.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from typing import Optional
from pathlib import Path


def print_summary_statistics(
    prices: pd.DataFrame,
    company_info: Optional[dict] = None,
) -> None:
    """Print basic summary statistics for market data.

    Parameters
    ----------
    prices : pd.DataFrame
        Historical price DataFrame from yfinance.
    company_info : dict | None
        Company-level metadata dictionary.
    """
    print("\n" + "=" * 60)
    print("  MARKET DATA — SUMMARY STATISTICS")
    print("=" * 60)

    if company_info:
        print(f"\n  Company:    {company_info.get('shortName', 'N/A')}")
        print(f"  Sector:     {company_info.get('sector', 'N/A')}")
        print(f"  Industry:   {company_info.get('industry', 'N/A')}")
        print(f"  Currency:   {company_info.get('currency', 'N/A')}")

        mkt_cap = company_info.get("market_cap")
        if mkt_cap:
            print(f"  Market Cap: ${mkt_cap / 1e9:,.1f}B")

        shares = company_info.get("shares_outstanding")
        if shares:
            print(f"  Shares Out: {shares / 1e6:,.1f}M")

        beta = company_info.get("beta")
        if beta:
            print(f"  Beta:       {beta:.2f}")

    print(f"\n  Price History")
    print(f"  ─────────────")
    print(f"  Period:     {prices.index[0].strftime('%Y-%m-%d')} → "
          f"{prices.index[-1].strftime('%Y-%m-%d')}")
    print(f"  Datapoints: {len(prices):,}")

    close_col = "Adj Close" if "Adj Close" in prices.columns else "Close"
    if close_col in prices.columns:
        close = prices[close_col]
        print(f"\n  Latest:     {close.iloc[-1]:,.2f}")
        print(f"  52w High:   {close.iloc[-252:].max():,.2f}" if len(close) >= 252 else "")
        print(f"  52w Low:    {close.iloc[-252:].min():,.2f}" if len(close) >= 252 else "")
        print(f"  All-Time H: {close.max():,.2f}")
        print(f"  All-Time L: {close.min():,.2f}")

        # Annualised return
        if len(close) > 252:
            years = (prices.index[-1] - prices.index[0]).days / 365.25
            cagr = (close.iloc[-1] / close.iloc[0]) ** (1 / years) - 1
            print(f"  CAGR:       {cagr:.1%}")

    print("=" * 60 + "\n")


def print_ratio_summary(ratios: pd.DataFrame) -> None:
    """Print a summary of computed financial ratios.

    Parameters
    ----------
    ratios : pd.DataFrame
        Output from ``compute_ratios.compute_all_ratios``.
    """
    print("\n" + "=" * 60)
    print("  FINANCIAL RATIOS — SUMMARY")
    print("=" * 60)

    for col in ratios.columns:
        series = ratios[col].dropna()
        if series.empty:
            continue
        print(f"\n  {col}")
        print(f"    Latest:  {series.iloc[-1]:.3f}")
        print(f"    Mean:    {series.mean():.3f}")
        print(f"    Median:  {series.median():.3f}")
        print(f"    Min:     {series.min():.3f}")
        print(f"    Max:     {series.max():.3f}")

    print("=" * 60 + "\n")


def plot_price_history(
    prices: pd.DataFrame,
    ticker: str = "ASML",
    output_dir: str = "data/processed",
) -> None:
    """Save a line chart of adjusted close prices.

    Parameters
    ----------
    prices : pd.DataFrame
    ticker : str
    output_dir : str
    """
    close_col = "Adj Close" if "Adj Close" in prices.columns else "Close"
    if close_col not in prices.columns:
        print("[historical_analysis] No close price column found — skipping plot.")
        return

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(prices.index, prices[close_col], linewidth=1.0, color="#1a73e8")
    ax.set_title(f"{ticker} — Adjusted Close Price", fontsize=14, fontweight="bold")
    ax.set_xlabel("Date")
    ax.set_ylabel("Price")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    filepath = f"{output_dir}/{ticker.lower()}_price_history.png"
    fig.savefig(filepath, dpi=150)
    plt.close(fig)
    print(f"[historical_analysis] Saved price chart → {filepath}")
