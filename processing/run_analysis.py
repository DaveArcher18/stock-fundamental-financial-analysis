"""
Processing — Run Full Analysis on SEC XBRL Data
=================================================
Bridges the single-table XBRL output from ``etl/extract_sec_xbrl.py``
into the existing processing modules (ratios, ROIC, working capital),
then prints a comprehensive analytical summary and saves all results.

Usage:
    python -m processing.run_analysis

Or from the project root:
    python processing/run_analysis.py
"""

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from processing.compute_ratios import (
    gross_margin,
    operating_margin,
    net_margin,
    revenue_growth,
    capex_to_revenue,
    rd_to_revenue,
)
from processing.working_capital import compute_working_capital_table
from processing.roic import compute_nopat, compute_roic, compute_incremental_roic


# ═══════════════════════════════════════════════════════════════════════════
# Load Data
# ═══════════════════════════════════════════════════════════════════════════


def load_xbrl_financials(
    filepath: str = "data/processed/financials_annual.csv",
) -> pd.DataFrame:
    """Load the processed XBRL financials CSV.

    Parameters
    ----------
    filepath : str
        Path to ``financials_annual.csv`` produced by the XBRL extractor.

    Returns
    -------
    pd.DataFrame
        DataFrame indexed by fiscal year end date.
    """
    full_path = PROJECT_ROOT / filepath
    df = pd.read_csv(full_path, index_col=0, parse_dates=True)
    print(f"[run_analysis] Loaded {len(df)} years of data from {full_path}")
    return df


# ═══════════════════════════════════════════════════════════════════════════
# Compute All Metrics
# ═══════════════════════════════════════════════════════════════════════════


def compute_margin_ratios(df: pd.DataFrame) -> pd.DataFrame:
    """Compute profitability, growth, and efficiency ratios.

    Parameters
    ----------
    df : pd.DataFrame
        XBRL financials with standardised column names.

    Returns
    -------
    pd.DataFrame
        Ratio table indexed by fiscal year end date.
    """
    ratios = pd.DataFrame(index=df.index)
    ratios["fiscal_year"] = df["fiscal_year"]

    rev = df["revenue"]

    # ── Margins ───────────────────────────────────────────────────────
    if "cost_of_revenue" in df.columns:
        ratios["gross_margin"] = gross_margin(rev, df["cost_of_revenue"])
    else:
        ratios["gross_margin"] = np.nan

    if "operating_income" in df.columns:
        ratios["operating_margin"] = operating_margin(rev, df["operating_income"])
    elif "net_income" in df.columns and "income_tax_expense" in df.columns:
        # Approximate: operating_income ≈ net_income + tax
        approx_oi = df["net_income"] + df["income_tax_expense"].abs()
        ratios["operating_margin"] = operating_margin(rev, approx_oi)
    else:
        ratios["operating_margin"] = np.nan
    ratios["net_margin"] = net_margin(rev, df["net_income"])

    # ── Growth ────────────────────────────────────────────────────────
    ratios["revenue_growth"] = revenue_growth(rev)

    # Free Cash Flow
    ocf = df.get("operating_cash_flow", pd.Series(0, index=df.index))
    capex = df.get("capex", pd.Series(0, index=df.index))
    fcf = ocf - capex

    # ── Ratios & Metrics ──────────────────────────────────────────────────
    ratios["fcf_conversion"] = fcf / df["net_income"]
    ratios["capex_to_revenue"] = capex / rev

    if "rd_expense" in df.columns:
        ratios["rd_to_revenue"] = rd_to_revenue(rev, df["rd_expense"])

    if "sga_expense" in df.columns:
        ratios["sga_to_revenue"] = df["sga_expense"].abs() / rev

    # ── Depreciation coverage ─────────────────────────────────────────
    if "depreciation" in df.columns:
        ratios["depreciation_to_revenue"] = df["depreciation"].abs() / rev

    return ratios


def compute_roic_analysis(
    df: pd.DataFrame,
    tax_rate: float = 0.15,
) -> pd.DataFrame:
    """Compute ROIC using a simplified invested capital formula.

    Since the XBRL data lacks ``total_current_liabilities`` and
    ``short_term_debt``, we use a simplified approach:

        Invested Capital = Total Assets − Cash − Accounts Payable

    This is a reasonable approximation that captures the operating asset
    base net of the largest non-interest-bearing liability.

    Parameters
    ----------
    df : pd.DataFrame
        XBRL financials.
    tax_rate : float
        Effective tax rate for NOPAT.

    Returns
    -------
    pd.DataFrame
        ROIC analysis table.
    """
    roic_df = pd.DataFrame(index=df.index)
    roic_df["fiscal_year"] = df["fiscal_year"]

    # NOPAT = EBIT × (1 − t)
    if "operating_income" in df.columns:
        ebit = df["operating_income"]
    elif "net_income" in df.columns and "income_tax_expense" in df.columns:
        ebit = df["net_income"] + df["income_tax_expense"].abs()
    else:
        ebit = df["net_income"]
    nopat = compute_nopat(ebit, tax_rate)
    roic_df["nopat"] = nopat

    # Invested Capital = Total Assets − Cash − AP
    cash = df["cash"] if "cash" in df.columns else 0
    ap = df["accounts_payable"] if "accounts_payable" in df.columns else 0
    invested_capital = df["total_assets"] - cash - ap
    roic_df["invested_capital"] = invested_capital

    # ROIC = NOPAT_t / IC_{t-1}
    roic_df["roic"] = compute_roic(nopat, invested_capital)

    # Incremental ROIC = ΔNOPAT / ΔIC_{t-1}
    roic_df["incremental_roic"] = compute_incremental_roic(nopat, invested_capital)

    # Book equity check
    roic_df["equity"] = df["total_equity"]
    roic_df["roe"] = df["net_income"] / df["total_equity"].shift(1)

    return roic_df


def compute_working_capital_analysis(df: pd.DataFrame) -> pd.DataFrame:
    """Compute working capital metrics from the XBRL data.

    Parameters
    ----------
    df : pd.DataFrame
        XBRL financials.

    Returns
    -------
    pd.DataFrame
        Working capital table with NWC, ΔNWC, DSO, DIO, DPO, CCC.
    """
    # The working capital module expects separate balance_sheet and
    # income_stmt DataFrames with the same index. We just pass the
    # unified DataFrame for both — it has all the required columns.
    # Check required columns — skip working capital if missing key fields
    required = ["accounts_receivable", "accounts_payable", "cost_of_revenue"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        print(f"  ⚠ Working capital analysis skipped (missing: {', '.join(missing)})")
        # Return empty DataFrame with expected columns
        wc = pd.DataFrame(
            {"nwc": np.nan, "delta_nwc": np.nan, "dso": np.nan,
             "dio": np.nan, "dpo": np.nan, "ccc": np.nan},
            index=df.index,
        )
        wc.insert(0, "fiscal_year", df["fiscal_year"].values)
        return wc

    # If inventory is missing, zero it out (META, service companies)
    if "inventory" not in df.columns:
        df = df.copy()
        df["inventory"] = 0

    wc = compute_working_capital_table(
        balance_sheet=df,
        income_stmt=df,
    )
    wc.insert(0, "fiscal_year", df["fiscal_year"].values)
    return wc


# ═══════════════════════════════════════════════════════════════════════════
# Pretty Printing
# ═══════════════════════════════════════════════════════════════════════════


def print_section(title: str) -> None:
    """Print a formatted section header."""
    width = 72
    print(f"\n{'─' * width}")
    print(f"  {title}")
    print(f"{'─' * width}\n")


def print_ratios(ratios: pd.DataFrame) -> None:
    """Print the margin and efficiency ratio table."""
    print_section("PROFITABILITY & EFFICIENCY RATIOS")

    display = ratios.copy()
    pct_cols = [c for c in display.columns if c != "fiscal_year"]
    for c in pct_cols:
        display[c] = display[c].apply(
            lambda x: f"{x*100:.1f}%" if pd.notna(x) else "—"
        )
    print(display.to_string(index=False))

    # Trend commentary
    if len(ratios) >= 3:
        latest = ratios.iloc[-1]
        avg_3y = ratios.iloc[-3:].mean(numeric_only=True)
        avg_full = ratios.mean(numeric_only=True)
        print(f"\n  Latest year ({int(latest['fiscal_year'])}):")
        print(f"    Gross margin:     {latest['gross_margin']*100:.1f}%  "
              f"(3y avg: {avg_3y['gross_margin']*100:.1f}%, "
              f"10y avg: {avg_full['gross_margin']*100:.1f}%)")
        print(f"    Operating margin: {latest['operating_margin']*100:.1f}%  "
              f"(3y avg: {avg_3y['operating_margin']*100:.1f}%, "
              f"10y avg: {avg_full['operating_margin']*100:.1f}%)")
        if "rd_to_revenue" in ratios.columns:
            print(f"    R&D intensity:    {latest['rd_to_revenue']*100:.1f}%  "
                  f"(3y avg: {avg_3y['rd_to_revenue']*100:.1f}%)")


def print_roic(roic_df: pd.DataFrame) -> None:
    """Print the ROIC analysis table."""
    print_section("RETURN ON INVESTED CAPITAL (ROIC)")

    display = roic_df.copy()
    for c in ["nopat", "invested_capital", "equity"]:
        if c in display.columns:
            display[c] = display[c].apply(
                lambda x: f"€{x/1e9:.1f}B" if pd.notna(x) else "—"
            )
    for c in ["roic", "incremental_roic", "roe"]:
        if c in display.columns:
            display[c] = display[c].apply(
                lambda x: f"{x*100:.1f}%" if pd.notna(x) else "—"
            )
    print(display.to_string(index=False))

    # Summary stats
    if len(roic_df) >= 3:
        valid_roic = roic_df["roic"].dropna()
        if len(valid_roic) >= 2:
            print(f"\n  ROIC summary:")
            print(f"    Latest:  {valid_roic.iloc[-1]*100:.1f}%")
            print(f"    Median:  {valid_roic.median()*100:.1f}%")
            print(f"    Min:     {valid_roic.min()*100:.1f}%  "
                  f"({int(roic_df.loc[valid_roic.idxmin(), 'fiscal_year'])})")
            print(f"    Max:     {valid_roic.max()*100:.1f}%  "
                  f"({int(roic_df.loc[valid_roic.idxmax(), 'fiscal_year'])})")


def print_working_capital(wc: pd.DataFrame) -> None:
    """Print the working capital analysis table."""
    print_section("WORKING CAPITAL ANALYSIS")

    display = wc.copy()
    for c in ["nwc", "delta_nwc"]:
        if c in display.columns:
            display[c] = display[c].apply(
                lambda x: f"€{x/1e9:.1f}B" if pd.notna(x) else "—"
            )
    for c in ["dso", "dio", "dpo", "ccc"]:
        if c in display.columns:
            display[c] = display[c].apply(
                lambda x: f"{x:.0f}d" if pd.notna(x) else "—"
            )
    print(display.to_string(index=False))

    # Trend
    if len(wc) >= 3:
        latest = wc.iloc[-1]
        avg_3y = wc.iloc[-3:].mean(numeric_only=True)
        print(f"\n  Cash Conversion Cycle:")
        print(f"    Latest ({int(latest['fiscal_year'])}):  {latest['ccc']:.0f} days")
        print(f"    3-year average:  {avg_3y['ccc']:.0f} days")
        print(f"    Breakdown: DSO {latest['dso']:.0f}d + "
              f"DIO {latest['dio']:.0f}d − DPO {latest['dpo']:.0f}d")


def print_key_insights(
    df: pd.DataFrame,
    ratios: pd.DataFrame,
    roic_df: pd.DataFrame,
    wc: pd.DataFrame,
) -> None:
    """Print a concise summary of key analytical insights."""
    print_section("KEY ANALYTICAL INSIGHTS")

    latest = df.iloc[-1]
    fy = int(latest["fiscal_year"])

    # Revenue scale and trajectory
    rev = latest["revenue"] / 1e9
    cagr_5y = (df.iloc[-1]["revenue"] / df.iloc[-5]["revenue"]) ** (1/4) - 1 if len(df) >= 5 else np.nan
    cagr_full = (df.iloc[-1]["revenue"] / df.iloc[0]["revenue"]) ** (1/(len(df)-1)) - 1 if len(df) > 1 else np.nan

    print(f"  1. Revenue Scale & Growth")
    print(f"     FY{fy} revenue: €{rev:.1f}B")
    if not np.isnan(cagr_5y):
        print(f"     5-year CAGR:   {cagr_5y*100:.1f}%")
    print(f"     {len(df)-1}-year CAGR:   {cagr_full*100:.1f}%")

    # Margin trajectory
    print(f"\n  2. Margin Expansion")
    gm_first = ratios.iloc[0]["gross_margin"] * 100
    gm_last = ratios.iloc[-1]["gross_margin"] * 100
    om_first = ratios.iloc[0]["operating_margin"] * 100
    om_last = ratios.iloc[-1]["operating_margin"] * 100
    print(f"     Gross margin:     {gm_first:.1f}% → {gm_last:.1f}%  ({gm_last - gm_first:+.1f}pp)")
    print(f"     Operating margin: {om_first:.1f}% → {om_last:.1f}%  ({om_last - om_first:+.1f}pp)")

    # ROIC
    valid_roic = roic_df["roic"].dropna()
    if len(valid_roic) >= 2:
        print(f"\n  3. Capital Efficiency")
        print(f"     ROIC (latest):     {valid_roic.iloc[-1]*100:.1f}%")
        print(f"     ROIC (median):     {valid_roic.median()*100:.1f}%")
        wacc_est = 0.09  # rough estimate
        spread = valid_roic.iloc[-1] - wacc_est
        print(f"     ROIC − WACC spread: ~{spread*100:.1f}pp  "
              f"(assuming ~{wacc_est*100:.0f}% WACC)")
        if spread > 0:
            print(f"     → Positive spread = economic value creation ✓")

    # Capital intensity trend
    capex_latest = ratios.iloc[-1]["capex_to_revenue"] * 100
    capex_avg = ratios["capex_to_revenue"].mean() * 100
    print(f"\n  4. Capital Intensity")
    print(f"     Capex/Revenue (latest): {capex_latest:.1f}%")
    print(f"     Capex/Revenue (avg):    {capex_avg:.1f}%")
    if capex_latest > capex_avg * 1.3:
        print(f"     → Elevated capex phase (capacity build)")
    else:
        print(f"     → Within historical norms")

    # Working capital
    print(f"\n  5. Working Capital")
    ccc_latest = wc.iloc[-1]["ccc"]
    if not np.isnan(ccc_latest):
        print(f"     Cash Conversion Cycle: {ccc_latest:.0f} days")
    if "inventory" in latest.index and pd.notna(latest.get("inventory")):
        inv_to_rev = latest["inventory"] / latest["revenue"] * 100
        print(f"     Inventory/Revenue:     {inv_to_rev:.1f}%")
        if inv_to_rev > 30:
            print(f"     → High inventory levels — typical for capital equipment with "
                  f"long build cycles")
    else:
        print(f"     (No inventory — services/platform company)")

    # Share count
    shares_col = "shares_outstanding" if "shares_outstanding" in df.columns else "shares_outstanding_basic"
    if shares_col in df.columns:
        shares_first = df.iloc[0][shares_col] / 1e6
        shares_last = df.iloc[-1][shares_col] / 1e6
        if shares_first > 0:
            shares_reduction = (1 - shares_last / shares_first) * 100
            print(f"\n  6. Shareholder Returns")
            print(f"     Shares outstanding: {shares_first:.0f}M → {shares_last:.0f}M "
                  f"({shares_reduction:.1f}% buyback)")


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════


def run_analysis(
    data_path: str = "data/processed/financials_annual.csv",
    output_dir: str = "data/processed",
    config_path: str = "config/assumptions.yaml",
) -> dict[str, pd.DataFrame]:
    """Run the full processing pipeline on XBRL data.

    Parameters
    ----------
    data_path : str
        Path to the XBRL financials CSV.
    output_dir : str
        Directory for output CSVs.
    config_path : str
        Path to assumptions YAML for tax rate.

    Returns
    -------
    dict[str, pd.DataFrame]
        Dictionary containing ``ratios``, ``roic``, and ``working_capital``
        DataFrames.
    """
    # Load config
    cfg_path = PROJECT_ROOT / config_path
    config = {}
    if cfg_path.exists():
        with open(cfg_path, "r") as f:
            config = yaml.safe_load(f)
    tax_rate = config.get("tax", {}).get("effective_rate", 0.15)

    company_name = config.get("company", {}).get("name", "COMPANY").upper()
    print("\n" + "═" * 72)
    print(f"  {company_name} FINANCIAL ANALYSIS — SEC XBRL DATA")
    print("═" * 72)

    # Load data
    df = load_xbrl_financials(data_path)

    # Compute
    ratios = compute_margin_ratios(df)
    roic_df = compute_roic_analysis(df, tax_rate=tax_rate)
    wc = compute_working_capital_analysis(df)

    # Print
    print_ratios(ratios)
    print_roic(roic_df)
    print_working_capital(wc)
    print_key_insights(df, ratios, roic_df, wc)

    # Save
    out = Path(PROJECT_ROOT) / output_dir
    out.mkdir(parents=True, exist_ok=True)

    ratios.to_csv(out / "financial_ratios.csv", index=True)
    roic_df.to_csv(out / "roic_analysis.csv", index=True)
    wc.to_csv(out / "working_capital.csv", index=True)

    print(f"\n{'─' * 72}")
    print(f"  Saved to {out}/:")
    print(f"    • financial_ratios.csv")
    print(f"    • roic_analysis.csv")
    print(f"    • working_capital.csv")
    print(f"{'─' * 72}\n")

    return {"ratios": ratios, "roic": roic_df, "working_capital": wc}


if __name__ == "__main__":
    run_analysis()
