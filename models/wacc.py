"""
Models — Weighted Average Cost of Capital (WACC)
==================================================
Functions to compute the cost of equity (CAPM), cost of debt,
and blended WACC for use as the discount rate in DCF valuation.

Supports two modes:
    1. Config-driven — uses hardcoded assumptions from assumptions.yaml
    2. Data-driven   — derives inputs from actual financial data

Theory
------
WACC represents the minimum return a company must earn on its existing
asset base to satisfy its creditors, shareholders, and other capital
providers.  It is the appropriate discount rate for valuing the firm's
unlevered free cash flows (FCFF).

    WACC = (E/V) × Rₑ  +  (D/V) × Rd × (1 − T)

Where:
    E/V  = equity weight at market values
    D/V  = debt weight at market values
    Rₑ   = cost of equity from CAPM
    Rd   = pre-tax cost of debt
    T    = marginal tax rate

References:
    • Brealey, Myers & Allen — Principles of Corporate Finance
    • Damodaran — Investment Valuation, Ch. 8
"""

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Ensure project root is on path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ═══════════════════════════════════════════════════════════════════════════
# Core WACC Components
# ═══════════════════════════════════════════════════════════════════════════


def cost_of_equity(
    risk_free_rate: float,
    beta: float,
    equity_risk_premium: float,
    country_risk_premium: float = 0.0,
) -> float:
    """Estimate the cost of equity using the Capital Asset Pricing Model (CAPM).

    Formula
    -------
        Rₑ = Rf + β × ERP + CRP

    where:
        Rf   = risk-free rate (e.g. 10-year government bond yield)
        β    = levered equity beta relative to a broad market index
        ERP  = equity risk premium for the mature market
        CRP  = country risk premium (0 for Netherlands / developed markets)

    Parameters
    ----------
    risk_free_rate : float
        Risk-free rate as a decimal (e.g. 0.035 for 3.5%).
    beta : float
        Levered equity beta.
    equity_risk_premium : float
        Equity risk premium as a decimal.
    country_risk_premium : float
        Additional country-specific risk premium (default 0).

    Returns
    -------
    float
        Cost of equity as a decimal.
    """
    ke = risk_free_rate + beta * equity_risk_premium + country_risk_premium
    return ke


def cost_of_debt(
    pre_tax_cost: float,
    marginal_tax_rate: float,
) -> float:
    """Compute the after-tax cost of debt.

    Formula
    -------
        Rd(1−T) = pre-tax cost of debt × (1 − marginal tax rate)

    The tax shield on interest makes debt cheaper on an after-tax basis.

    Parameters
    ----------
    pre_tax_cost : float
        Pre-tax yield on outstanding debt / credit spread.
    marginal_tax_rate : float
        Marginal corporate tax rate as a decimal.

    Returns
    -------
    float
        After-tax cost of debt.
    """
    return pre_tax_cost * (1.0 - marginal_tax_rate)


def wacc(
    cost_of_equity: float,
    cost_of_debt: float,
    equity_weight: float,
    debt_weight: float,
) -> float:
    """Compute the Weighted Average Cost of Capital.

    Formula
    -------
        WACC = (E/V) × Rₑ  +  (D/V) × Rd(1−T)

    where V = D + E (total enterprise value), and Rd(1−T) is the
    after-tax cost of debt (already computed by :func:`cost_of_debt`).

    Parameters
    ----------
    cost_of_equity : float
        Rₑ from CAPM or equivalent model.
    cost_of_debt : float
        After-tax cost of debt.
    equity_weight : float
        E/V — proportion of equity in capital structure at market values.
    debt_weight : float
        D/V — proportion of debt in capital structure at market values.
        Must satisfy ``equity_weight + debt_weight ≈ 1.0``.

    Returns
    -------
    float
        WACC as a decimal.

    Raises
    ------
    ValueError
        If weights do not sum to approximately 1.0.
    """
    total = equity_weight + debt_weight
    if abs(total - 1.0) > 0.01:
        raise ValueError(
            f"Capital structure weights must sum to ~1.0, got {total:.4f} "
            f"(equity={equity_weight:.4f}, debt={debt_weight:.4f})."
        )

    return equity_weight * cost_of_equity + debt_weight * cost_of_debt


# ═══════════════════════════════════════════════════════════════════════════
# Data-Driven Helpers
# ═══════════════════════════════════════════════════════════════════════════


def derive_cost_of_debt_from_data(
    financials: pd.DataFrame,
    lookback_years: int = 3,
) -> float:
    """Estimate pre-tax cost of debt from interest expense and debt levels.

    Uses the ratio of interest expense to average outstanding debt over
    the most recent *lookback_years*.  This gives a blended rate that
    reflects the mix of outstanding bonds/facilities.

    Formula
    -------
        Implied Rd = Interest Expense / Average(Total Debt)

    Parameters
    ----------
    financials : pd.DataFrame
        Annual financials with ``interest_expense`` and ``long_term_debt``.
    lookback_years : int
        Number of recent years to average over.

    Returns
    -------
    float
        Implied pre-tax cost of debt as a decimal.
    """
    recent = financials.tail(lookback_years)

    # Safe access — some companies report debt under different XBRL tags
    if "interest_expense" not in recent.columns:
        return 0.03  # fallback
    interest = recent["interest_expense"].mean()

    debt_col = None
    for col in ["long_term_debt", "total_debt", "debt_current"]:
        if col in recent.columns:
            debt_col = col
            break
    if debt_col is None:
        return 0.03  # fallback
    debt = recent[debt_col].mean()

    if debt <= 0 or pd.isna(interest):
        return 0.03  # fallback to config default

    return interest / debt


def derive_effective_tax_rate(
    financials: pd.DataFrame,
    lookback_years: int = 3,
) -> float:
    """Derive the effective tax rate from reported income tax and EBT.

    Formula
    -------
        Effective Tax Rate = Income Tax Expense / (Net Income + Tax Expense)

    Parameters
    ----------
    financials : pd.DataFrame
        Annual financials with ``income_tax_expense`` and ``net_income``.
    lookback_years : int
        Number of recent years to average over.

    Returns
    -------
    float
        Effective tax rate as a decimal.
    """
    recent = financials.tail(lookback_years)

    tax = recent["income_tax_expense"]
    ni = recent["net_income"]
    ebt = ni + tax

    # Weighted average (by EBT magnitude) to avoid distortion
    total_tax = tax.sum()
    total_ebt = ebt.sum()

    if total_ebt <= 0:
        return 0.15  # fallback

    return total_tax / total_ebt


def derive_capital_structure(
    financials: pd.DataFrame,
    market_cap_usd: float,
    usd_eur_rate: float = 0.92,
) -> dict:
    """Derive market-value capital structure weights.

    Uses the most recent market cap (converted to EUR) and the latest
    book value of debt to approximate the capital structure at market values.

    Parameters
    ----------
    financials : pd.DataFrame
        Annual financials with ``long_term_debt``.
    market_cap_usd : float
        Current market capitalisation in USD.
    usd_eur_rate : float
        USD-to-EUR conversion rate.

    Returns
    -------
    dict
        Keys: ``market_cap_eur``, ``total_debt_eur``, ``equity_weight``,
        ``debt_weight``.
    """
    latest = financials.iloc[-1]

    # Safe access — BRK-B and others may not report long_term_debt
    total_debt = 0.0
    for col in ["long_term_debt", "total_debt", "debt_current"]:
        if col in latest.index and pd.notna(latest[col]):
            total_debt = latest[col]
            break

    market_cap_eur = market_cap_usd * usd_eur_rate
    enterprise_value = market_cap_eur + total_debt

    return {
        "market_cap_eur": market_cap_eur,
        "total_debt_eur": total_debt,
        "enterprise_value_eur": enterprise_value,
        "equity_weight": market_cap_eur / enterprise_value,
        "debt_weight": total_debt / enterprise_value,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Config-Driven WACC
# ═══════════════════════════════════════════════════════════════════════════


def compute_wacc_from_config(config: dict) -> dict:
    """Compute WACC directly from a config dictionary (assumptions.yaml).

    Reads keys from ``config["cost_of_capital"]`` and ``config["tax"]``.

    Parameters
    ----------
    config : dict
        Parsed assumptions.yaml configuration.

    Returns
    -------
    dict
        Dictionary with ``ke``, ``kd_after_tax``, ``wacc``, and all inputs.
    """
    coc = config["cost_of_capital"]
    tax = config["tax"]

    ke = cost_of_equity(
        risk_free_rate=coc["risk_free_rate"],
        beta=coc["beta"],
        equity_risk_premium=coc["equity_risk_premium"],
        country_risk_premium=coc.get("country_risk_premium", 0.0),
    )

    kd = cost_of_debt(
        pre_tax_cost=coc["pre_tax_cost_of_debt"],
        marginal_tax_rate=tax["marginal_rate"],
    )

    d_to_v = coc["target_debt_to_capital"]
    e_to_v = 1.0 - d_to_v

    w = wacc(
        cost_of_equity=ke,
        cost_of_debt=kd,
        equity_weight=e_to_v,
        debt_weight=d_to_v,
    )

    return {
        "cost_of_equity": ke,
        "cost_of_debt_pre_tax": coc["pre_tax_cost_of_debt"],
        "cost_of_debt_after_tax": kd,
        "equity_weight": e_to_v,
        "debt_weight": d_to_v,
        "marginal_tax_rate": tax["marginal_rate"],
        "wacc": w,
        "inputs": {
            "risk_free_rate": coc["risk_free_rate"],
            "beta": coc["beta"],
            "equity_risk_premium": coc["equity_risk_premium"],
            "country_risk_premium": coc.get("country_risk_premium", 0.0),
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
# Data-Driven WACC
# ═══════════════════════════════════════════════════════════════════════════


def compute_wacc_from_data(
    config: dict,
    financials: pd.DataFrame,
    market_cap_usd: float,
    usd_eur_rate: float = 0.92,
) -> dict:
    """Compute WACC using a blend of config assumptions and actual data.

    Uses:
        - Config: risk-free rate, ERP, beta (market parameters)
        - Data:   cost of debt, tax rate, capital structure (company data)

    This gives the most accurate estimate by grounding company-specific
    inputs in actual filings while using market-level parameters from
    the analyst's judgement.

    Parameters
    ----------
    config : dict
        Parsed assumptions.yaml configuration.
    financials : pd.DataFrame
        Annual financials from SEC XBRL.
    market_cap_usd : float
        Current market capitalisation in USD.
    usd_eur_rate : float
        USD-to-EUR conversion rate.

    Returns
    -------
    dict
        Dictionary with ``ke``, ``kd_after_tax``, ``wacc``, and all inputs,
        including data-derived values.
    """
    coc = config["cost_of_capital"]
    tax_config = config["tax"]

    # ── Cost of Equity (from config — market parameters) ──────────────
    ke = cost_of_equity(
        risk_free_rate=coc["risk_free_rate"],
        beta=coc["beta"],
        equity_risk_premium=coc["equity_risk_premium"],
        country_risk_premium=coc.get("country_risk_premium", 0.0),
    )

    # ── Cost of Debt (from data) ──────────────────────────────────────
    implied_kd = derive_cost_of_debt_from_data(financials)
    marginal_tax = tax_config["marginal_rate"]
    effective_tax = derive_effective_tax_rate(financials)
    kd = cost_of_debt(pre_tax_cost=implied_kd, marginal_tax_rate=marginal_tax)

    # ── Capital Structure (from data) ─────────────────────────────────
    cap_structure = derive_capital_structure(
        financials, market_cap_usd, usd_eur_rate
    )

    w = wacc(
        cost_of_equity=ke,
        cost_of_debt=kd,
        equity_weight=cap_structure["equity_weight"],
        debt_weight=cap_structure["debt_weight"],
    )

    return {
        "cost_of_equity": ke,
        "cost_of_debt_pre_tax": implied_kd,
        "cost_of_debt_after_tax": kd,
        "equity_weight": cap_structure["equity_weight"],
        "debt_weight": cap_structure["debt_weight"],
        "marginal_tax_rate": marginal_tax,
        "effective_tax_rate": effective_tax,
        "wacc": w,
        "capital_structure": cap_structure,
        "inputs": {
            "risk_free_rate": coc["risk_free_rate"],
            "beta": coc["beta"],
            "equity_risk_premium": coc["equity_risk_premium"],
            "country_risk_premium": coc.get("country_risk_premium", 0.0),
            "implied_cost_of_debt": implied_kd,
            "market_cap_usd": market_cap_usd,
            "usd_eur_rate": usd_eur_rate,
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
# Pretty Printing
# ═══════════════════════════════════════════════════════════════════════════


def print_wacc_summary(result: dict, title: str = "WACC ESTIMATE") -> None:
    """Print a formatted WACC breakdown.

    Parameters
    ----------
    result : dict
        Output from :func:`compute_wacc_from_config` or
        :func:`compute_wacc_from_data`.
    title : str
        Section title.
    """
    width = 60
    print(f"\n{'═' * width}")
    print(f"  {title}")
    print(f"{'═' * width}")

    inputs = result.get("inputs", {})
    print(f"\n  ── CAPM Inputs ──")
    print(f"  Risk-free rate (Rf):     {inputs.get('risk_free_rate', 0)*100:.2f}%")
    print(f"  Equity beta (β):         {inputs.get('beta', 0):.3f}")
    print(f"  Equity risk premium:     {inputs.get('equity_risk_premium', 0)*100:.2f}%")
    crp = inputs.get('country_risk_premium', 0)
    if crp > 0:
        print(f"  Country risk premium:    {crp*100:.2f}%")

    print(f"\n  ── Component Costs ──")
    print(f"  Cost of equity (Rₑ):     {result['cost_of_equity']*100:.2f}%")
    print(f"  Cost of debt pre-tax:    {result['cost_of_debt_pre_tax']*100:.2f}%")
    print(f"  Cost of debt after-tax:  {result['cost_of_debt_after_tax']*100:.2f}%")
    print(f"  Marginal tax rate:       {result['marginal_tax_rate']*100:.1f}%")

    if "effective_tax_rate" in result:
        print(f"  Effective tax rate:      {result['effective_tax_rate']*100:.1f}%  (from data)")

    print(f"\n  ── Capital Structure ──")
    print(f"  Equity weight (E/V):     {result['equity_weight']*100:.1f}%")
    print(f"  Debt weight (D/V):       {result['debt_weight']*100:.1f}%")

    if "capital_structure" in result:
        cs = result["capital_structure"]
        print(f"  Market cap (EUR):        €{cs['market_cap_eur']/1e9:.1f}B")
        print(f"  Total debt (EUR):        €{cs['total_debt_eur']/1e9:.1f}B")

    print(f"\n  ══════════════════════════════════════════════════")
    print(f"  ▸ WACC = {result['wacc']*100:.2f}%")
    print(f"  ══════════════════════════════════════════════════")
    print(f"{'═' * width}\n")


# ═══════════════════════════════════════════════════════════════════════════
# CLI entry point
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import yaml

    # Load config
    config_path = PROJECT_ROOT / "config" / "assumptions.yaml"
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    # Load financial data
    financials = pd.read_csv(
        PROJECT_ROOT / "data" / "processed" / "financials_annual.csv",
        index_col=0, parse_dates=True,
    )

    # Load market cap
    ticker = config.get("company", {}).get("ticker", "ASML").lower()
    company_info = pd.read_csv(
        PROJECT_ROOT / "data" / "raw" / f"{ticker}_company_info.csv",
    )
    market_cap_usd = float(
        company_info[company_info["field"] == "market_cap"]["value"].values[0]
    )

    # ── Method 1: Config-driven (analyst assumptions) ─────────────────
    result_config = compute_wacc_from_config(config)
    print_wacc_summary(result_config, title="WACC — CONFIG-DRIVEN (Analyst Assumptions)")

    # ── Method 2: Data-driven (actual financial data) ─────────────────
    result_data = compute_wacc_from_data(
        config=config,
        financials=financials,
        market_cap_usd=market_cap_usd,
    )
    print_wacc_summary(result_data, title="WACC — DATA-DRIVEN (SEC Filings + Market)")

    # ── Comparison ────────────────────────────────────────────────────
    print("── Comparison ──")
    print(f"  Config WACC:     {result_config['wacc']*100:.2f}%")
    print(f"  Data WACC:       {result_data['wacc']*100:.2f}%")
    diff = (result_data['wacc'] - result_config['wacc']) * 100
    print(f"  Difference:      {diff:+.2f}pp")
    print()

    if abs(diff) > 1.0:
        print("  ⚠ Significant divergence — review assumptions vs data.")
        print("    Key drivers:")
        if result_config['inputs']['beta'] != result_data['inputs']['beta']:
            print(f"    • Beta: {result_config['inputs']['beta']:.2f} (config) "
                  f"vs {result_data['inputs']['beta']:.2f} (data)")
        print(f"    • Cost of debt: {result_config['cost_of_debt_pre_tax']*100:.2f}% (config) "
              f"vs {result_data['cost_of_debt_pre_tax']*100:.2f}% (data)")
        print(f"    • D/(D+E): {result_config['debt_weight']*100:.1f}% (config) "
              f"vs {result_data['debt_weight']*100:.1f}% (data)")
    else:
        print("  ✓ Config and data-derived WACC are consistent.")
