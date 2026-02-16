"""
Models — Discounted Cash Flow (DCF) Valuation
===============================================
Projects Free Cash Flow to the Firm (FCFF), computes terminal value via
Gordon Growth, and derives intrinsic equity value per share.

Methodology
-----------
This is a two-stage DCF model:

    Stage 1 (Explicit Period):  Project FCFF year-by-year using revenue
        growth assumptions, margin targets, capex intensity, and working
        capital requirements.  Each year's FCFF is discounted back to
        present value at the WACC.

    Stage 2 (Terminal Value):   Beyond the explicit period, the firm is
        assumed to grow at a constant perpetual rate g∞ < WACC, and its
        normalised FCFF is capitalised via the Gordon Growth formula.

    Enterprise Value = PV(Stage 1 FCFF) + PV(Terminal Value)
    Equity Value     = Enterprise Value − Net Debt
    Value per Share  = Equity Value / Shares Outstanding

Supports:
    - Year-by-year growth rate overrides (near-term granularity)
    - Linear margin fade from current → target over a configurable horizon
    - Full EUR-denominated valuation with equity bridge

References:
    • Brealey, Myers & Allen — Principles of Corporate Finance, Ch. 4 & 19
    • Damodaran — Investment Valuation, Ch. 12
    • McKinsey — Valuation: Measuring and Managing the Value of Companies
"""

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from models.wacc import compute_wacc_from_data, compute_wacc_from_config, print_wacc_summary


# ═══════════════════════════════════════════════════════════════════════════
# Growth Rate Construction
# ═══════════════════════════════════════════════════════════════════════════


def build_growth_schedule(
    explicit_years: int,
    near_term_rates: list[float],
    long_term_rate: float,
) -> list[float]:
    """Build a year-by-year revenue growth schedule.

    Near-term overrides are used first, then linearly fades to the
    long-term rate over any remaining years.

    Parameters
    ----------
    explicit_years : int
        Total number of projection years.
    near_term_rates : list[float]
        Year-by-year growth rates for early years (may be shorter
        than *explicit_years*).
    long_term_rate : float
        Steady-state growth rate for the remainder.

    Returns
    -------
    list[float]
        Growth rate for each of the *explicit_years* years.
    """
    schedule = list(near_term_rates[:explicit_years])
    remaining = explicit_years - len(schedule)

    if remaining <= 0:
        return schedule[:explicit_years]

    if len(schedule) == 0:
        # No near-term overrides — use long-term rate throughout
        return [long_term_rate] * explicit_years

    # Fade from last near-term rate to long-term rate
    last_near = schedule[-1]
    for i in range(1, remaining + 1):
        faded = last_near + (long_term_rate - last_near) * (i / remaining)
        schedule.append(faded)

    return schedule


def build_margin_schedule(
    explicit_years: int,
    current_margin: float,
    target_margin: float,
    fade_years: int = 5,
) -> list[float]:
    """Build a margin schedule that linearly fades to a target.

    Parameters
    ----------
    explicit_years : int
        Total projection years.
    current_margin : float
        Starting margin (latest actual).
    target_margin : float
        Long-run equilibrium margin.
    fade_years : int
        Number of years over which to fade. After fade, margin stays
        at target.

    Returns
    -------
    list[float]
        Margin for each projection year.
    """
    schedule = []
    for i in range(1, explicit_years + 1):
        if i <= fade_years:
            m = current_margin + (target_margin - current_margin) * (i / fade_years)
        else:
            m = target_margin
        schedule.append(m)
    return schedule


# ═══════════════════════════════════════════════════════════════════════════
# FCFF Projection
# ═══════════════════════════════════════════════════════════════════════════


def project_fcf(
    base_revenue: float,
    growth_rates: list[float],
    operating_margins: list[float] | float,
    tax_rate: float,
    capex_to_revenue: float,
    depreciation_to_revenue: float,
    nwc_to_revenue: float,
) -> pd.DataFrame:
    """Project Free Cash Flow to the Firm (FCFF) over an explicit horizon.

    Formula (per period)
    --------------------
        Revenue_t      = Revenue_{t-1} × (1 + g_t)
        EBIT_t         = Revenue_t × operating_margin_t
        NOPAT_t        = EBIT_t × (1 − tax_rate)
        Net Capex_t    = (capex_to_revenue − depreciation_to_revenue) × Revenue_t
        ΔNWC_t         = nwc_to_revenue × (Revenue_t − Revenue_{t-1})
        FCFF_t         = NOPAT_t − Net Capex_t − ΔNWC_t

    Parameters
    ----------
    base_revenue : float
        Most recent fiscal year revenue (the starting point).
    growth_rates : list[float]
        Revenue growth rate for each projection year.
    operating_margins : list[float] | float
        EBIT margin per year or a constant for all years.
    tax_rate : float
        Effective corporate tax rate.
    capex_to_revenue : float
        Capex / Revenue ratio.
    depreciation_to_revenue : float
        Depreciation / Revenue ratio.
    nwc_to_revenue : float
        Net working capital / Revenue ratio (used to compute ΔNWC).

    Returns
    -------
    pd.DataFrame
        Year-by-year projection with columns: ``year``, ``revenue``,
        ``ebit``, ``nopat``, ``capex``, ``depreciation``, ``net_capex``,
        ``delta_nwc``, ``fcff``.
    """
    n_years = len(growth_rates)

    # Allow margins to be a scalar or per-year list
    if isinstance(operating_margins, (int, float)):
        margins = [operating_margins] * n_years
    else:
        margins = list(operating_margins)
        if len(margins) < n_years:
            margins.extend([margins[-1]] * (n_years - len(margins)))

    rows = []
    prev_revenue = base_revenue

    for i in range(n_years):
        year = i + 1
        revenue = prev_revenue * (1.0 + growth_rates[i])
        ebit = revenue * margins[i]
        nopat = ebit * (1.0 - tax_rate)
        capex = revenue * capex_to_revenue
        depreciation = revenue * depreciation_to_revenue
        net_capex = capex - depreciation
        delta_nwc = nwc_to_revenue * (revenue - prev_revenue)
        fcff = nopat - net_capex - delta_nwc

        rows.append({
            "year": year,
            "growth_rate": growth_rates[i],
            "revenue": revenue,
            "operating_margin": margins[i],
            "ebit": ebit,
            "nopat": nopat,
            "capex": capex,
            "depreciation": depreciation,
            "net_capex": net_capex,
            "delta_nwc": delta_nwc,
            "fcff": fcff,
        })

        prev_revenue = revenue

    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════════════════
# Terminal Value
# ═══════════════════════════════════════════════════════════════════════════


def terminal_value(
    final_year_fcff: float,
    terminal_growth_rate: float,
    wacc: float,
) -> float:
    """Compute terminal value using the Gordon Growth (perpetuity) model.

    Formula
    -------
        TV = FCFF_{T+1} / (WACC − g∞)
           = FCFF_T × (1 + g∞) / (WACC − g∞)

    Parameters
    ----------
    final_year_fcff : float
        FCFF in the last year of the explicit forecast.
    terminal_growth_rate : float
        Long-run nominal growth rate (g∞).
    wacc : float
        Weighted average cost of capital.

    Returns
    -------
    float
        Terminal value as of the end of the explicit forecast period.

    Raises
    ------
    ValueError
        If ``terminal_growth_rate >= wacc``.
    """
    if terminal_growth_rate >= wacc:
        raise ValueError(
            f"Terminal growth rate ({terminal_growth_rate:.4f}) must be "
            f"less than WACC ({wacc:.4f}) for convergence."
        )

    tv = final_year_fcff * (1.0 + terminal_growth_rate) / (wacc - terminal_growth_rate)
    return tv


# ═══════════════════════════════════════════════════════════════════════════
# Enterprise Value
# ═══════════════════════════════════════════════════════════════════════════


def enterprise_value(
    fcff_series: pd.Series,
    wacc: float,
    tv: float,
    terminal_year: int,
) -> dict:
    """Compute Enterprise Value by discounting projected FCFF and TV.

    Formula
    -------
        EV = Σ_{t=1}^{T} FCFF_t / (1 + WACC)^t  +  TV / (1 + WACC)^T

    Parameters
    ----------
    fcff_series : pd.Series
        Projected FCFF for each year (1-indexed).
    wacc : float
        Weighted average cost of capital.
    tv : float
        Terminal value at end of year T.
    terminal_year : int
        Number of years in the explicit forecast (T).

    Returns
    -------
    dict
        ``pv_explicit``, ``pv_terminal``, ``enterprise_value``,
        ``terminal_pct`` (percentage of EV from terminal value).
    """
    # Discount each year's FCFF
    discount_factors = [(1.0 + wacc) ** t for t in range(1, terminal_year + 1)]
    pv_fcffs = [fcff / df for fcff, df in zip(fcff_series, discount_factors)]
    pv_explicit = sum(pv_fcffs)

    # Discount terminal value
    pv_tv = tv / (1.0 + wacc) ** terminal_year

    ev = pv_explicit + pv_tv
    terminal_pct = pv_tv / ev * 100 if ev > 0 else 0

    return {
        "pv_explicit": pv_explicit,
        "pv_terminal": pv_tv,
        "enterprise_value": ev,
        "terminal_pct": terminal_pct,
        "pv_fcffs": pv_fcffs,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Equity Bridge
# ═══════════════════════════════════════════════════════════════════════════


def equity_value_per_share(
    ev: float,
    net_debt: float,
    shares_outstanding: float,
) -> dict:
    """Derive equity value per share from enterprise value.

    Formula
    -------
        Equity Value = EV − Net Debt
        Value per Share = Equity Value / Shares Outstanding

    Net debt = Total Debt − Cash.  A negative net debt (net cash)
    *increases* equity value relative to EV.

    Parameters
    ----------
    ev : float
        Enterprise value.
    net_debt : float
        Total debt minus cash and equivalents.
    shares_outstanding : float
        Diluted shares outstanding.

    Returns
    -------
    dict
        ``equity_value``, ``net_debt``, ``value_per_share``,
        ``shares_outstanding``.
    """
    equity_value = ev - net_debt
    vps = equity_value / shares_outstanding

    return {
        "equity_value": equity_value,
        "net_debt": net_debt,
        "value_per_share": vps,
        "shares_outstanding": shares_outstanding,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Full DCF Orchestrator
# ═══════════════════════════════════════════════════════════════════════════


def run_dcf(
    config: dict,
    financials: pd.DataFrame,
    wacc_rate: float,
    market_cap_usd: float = None,
    usd_eur_rate: float = 0.92,
) -> dict:
    """Run the full DCF valuation pipeline.

    Parameters
    ----------
    config : dict
        Parsed assumptions.yaml.
    financials : pd.DataFrame
        Annual XBRL financials.
    wacc_rate : float
        WACC to use for discounting.
    market_cap_usd : float | None
        Current market cap (for upside/downside comparison).
    usd_eur_rate : float
        USD→EUR conversion rate.

    Returns
    -------
    dict
        Full valuation result including projections, EV, equity value,
        and value per share.
    """
    latest = financials.iloc[-1]

    # ── Extract base-year data ────────────────────────────────────────
    base_revenue = latest["revenue"]
    cash = latest["cash"]
    total_debt = latest["long_term_debt"]
    net_debt = total_debt - cash
    shares = latest["shares_outstanding"]

    # Current margins (for fade starting point)
    current_op_margin = latest["operating_income"] / latest["revenue"]

    # ── Config parameters ─────────────────────────────────────────────
    proj = config["projection"]
    rev_cfg = config["revenue"]
    margin_cfg = config["margins"]
    capint = config["capital_intensity"]
    tax_rate = config["tax"]["effective_rate"]

    explicit_years = proj["explicit_years"]
    terminal_growth = proj["terminal_growth_rate"]

    # ── Build schedules ───────────────────────────────────────────────
    near_term = rev_cfg.get("near_term_growth_rates") or []
    long_term_growth = rev_cfg["long_term_growth_rate"]

    growth_schedule = build_growth_schedule(
        explicit_years=explicit_years,
        near_term_rates=near_term,
        long_term_rate=long_term_growth,
    )

    margin_schedule = build_margin_schedule(
        explicit_years=explicit_years,
        current_margin=current_op_margin,
        target_margin=margin_cfg["operating_margin"],
        fade_years=5,
    )

    # ── Project FCFF ──────────────────────────────────────────────────
    projections = project_fcf(
        base_revenue=base_revenue,
        growth_rates=growth_schedule,
        operating_margins=margin_schedule,
        tax_rate=tax_rate,
        capex_to_revenue=capint["capex_to_revenue"],
        depreciation_to_revenue=capint["depreciation_to_revenue"],
        nwc_to_revenue=capint["nwc_to_revenue"],
    )

    # ── Terminal Value ────────────────────────────────────────────────
    final_fcff = projections.iloc[-1]["fcff"]
    tv = terminal_value(final_fcff, terminal_growth, wacc_rate)

    # ── Enterprise Value ──────────────────────────────────────────────
    ev_result = enterprise_value(
        fcff_series=projections["fcff"],
        wacc=wacc_rate,
        tv=tv,
        terminal_year=explicit_years,
    )

    # ── Equity Bridge ─────────────────────────────────────────────────
    equity_result = equity_value_per_share(
        ev=ev_result["enterprise_value"],
        net_debt=net_debt,
        shares_outstanding=shares,
    )

    # ── Market comparison ─────────────────────────────────────────────
    market_data = {}
    if market_cap_usd:
        market_cap_eur = market_cap_usd * usd_eur_rate
        market_price_eur = market_cap_eur / shares
        upside = (equity_result["value_per_share"] / market_price_eur - 1.0) * 100

        market_data = {
            "market_cap_eur": market_cap_eur,
            "market_price_per_share_eur": market_price_eur,
            "upside_pct": upside,
        }

    return {
        "projections": projections,
        "terminal_value": tv,
        "ev": ev_result,
        "equity": equity_result,
        "market": market_data,
        "inputs": {
            "base_revenue": base_revenue,
            "wacc": wacc_rate,
            "terminal_growth": terminal_growth,
            "tax_rate": tax_rate,
            "current_op_margin": current_op_margin,
            "target_op_margin": margin_cfg["operating_margin"],
            "capex_to_revenue": capint["capex_to_revenue"],
            "depreciation_to_revenue": capint["depreciation_to_revenue"],
            "nwc_to_revenue": capint["nwc_to_revenue"],
            "net_debt": net_debt,
            "shares_outstanding": shares,
        },
    }


# ═══════════════════════════════════════════════════════════════════════════
# Pretty Printing
# ═══════════════════════════════════════════════════════════════════════════


def print_dcf_summary(result: dict) -> None:
    """Print a formatted DCF valuation summary."""
    width = 72
    inputs = result["inputs"]
    ev = result["ev"]
    eq = result["equity"]
    proj = result["projections"]

    print(f"\n{'═' * width}")
    print(f"  DISCOUNTED CASH FLOW — VALUATION SUMMARY")
    print(f"{'═' * width}")

    # ── Key Assumptions ───────────────────────────────────────────────
    print(f"\n  ── Key Assumptions ──")
    print(f"  Base year revenue:        €{inputs['base_revenue']/1e9:.1f}B")
    print(f"  WACC:                     {inputs['wacc']*100:.2f}%")
    print(f"  Terminal growth (g∞):     {inputs['terminal_growth']*100:.2f}%")
    print(f"  Tax rate:                 {inputs['tax_rate']*100:.1f}%")
    print(f"  Op. margin (current→tgt): {inputs['current_op_margin']*100:.1f}% → "
          f"{inputs['target_op_margin']*100:.1f}%")
    print(f"  Net capex/revenue:        {(inputs['capex_to_revenue'] - inputs['depreciation_to_revenue'])*100:.1f}%")
    print(f"  ΔNWC/revenue:             {inputs['nwc_to_revenue']*100:.1f}%")

    # ── Projection Table ──────────────────────────────────────────────
    print(f"\n  ── FCFF Projections (EUR billions) ──\n")
    header = f"  {'Yr':>3s}  {'Growth':>7s}  {'Revenue':>9s}  {'Margin':>7s}  {'NOPAT':>8s}  {'NetCapx':>8s}  {'ΔNWC':>8s}  {'FCFF':>8s}"
    print(header)
    print(f"  {'─'*3}  {'─'*7}  {'─'*9}  {'─'*7}  {'─'*8}  {'─'*8}  {'─'*8}  {'─'*8}")

    for _, row in proj.iterrows():
        print(f"  {int(row['year']):>3d}  "
              f"{row['growth_rate']*100:>6.1f}%  "
              f"€{row['revenue']/1e9:>7.1f}B  "
              f"{row['operating_margin']*100:>6.1f}%  "
              f"€{row['nopat']/1e9:>6.1f}B  "
              f"€{row['net_capex']/1e9:>6.1f}B  "
              f"€{row['delta_nwc']/1e9:>6.1f}B  "
              f"€{row['fcff']/1e9:>6.1f}B")

    # ── Valuation ─────────────────────────────────────────────────────
    print(f"\n  ── Valuation ──")
    print(f"  PV of explicit FCFF:      €{ev['pv_explicit']/1e9:.1f}B")
    print(f"  PV of terminal value:     €{ev['pv_terminal']/1e9:.1f}B  "
          f"({ev['terminal_pct']:.0f}% of EV)")
    print(f"  Terminal value (undiscounted): €{result['terminal_value']/1e9:.1f}B")

    print(f"\n  ══════════════════════════════════════════════════")
    print(f"  ▸ Enterprise Value:       €{ev['enterprise_value']/1e9:.1f}B")
    print(f"  ══════════════════════════════════════════════════")

    # ── Equity Bridge ─────────────────────────────────────────────────
    print(f"\n  ── Equity Bridge ──")
    print(f"  Enterprise value:         €{ev['enterprise_value']/1e9:.1f}B")
    nd = eq["net_debt"]
    sign = "−" if nd >= 0 else "+"
    print(f"  {sign} Net debt (cash):       €{abs(nd)/1e9:.1f}B  "
          f"({'net debt' if nd >= 0 else 'net cash'})")
    print(f"  = Equity value:           €{eq['equity_value']/1e9:.1f}B")
    print(f"  ÷ Shares outstanding:     {eq['shares_outstanding']/1e6:.0f}M")

    print(f"\n  ══════════════════════════════════════════════════")
    print(f"  ▸ Intrinsic Value/Share:  €{eq['value_per_share']:.2f}")
    print(f"  ══════════════════════════════════════════════════")

    # ── Market Comparison ─────────────────────────────────────────────
    if result.get("market"):
        mkt = result["market"]
        print(f"\n  ── Market Comparison ──")
        print(f"  Current market price:     ~€{mkt['market_price_per_share_eur']:.2f}  (est. EUR)")
        upside = mkt["upside_pct"]
        arrow = "▲" if upside > 0 else "▼"
        verdict = "UNDERVALUED" if upside > 10 else "OVERVALUED" if upside < -10 else "FAIRLY VALUED"
        print(f"  Implied upside/downside:  {arrow} {upside:+.1f}%")
        print(f"  Verdict:                  {verdict}")

    print(f"\n{'═' * width}\n")


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":

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
    company_info = pd.read_csv(
        PROJECT_ROOT / "data" / "raw" / "asml_company_info.csv",
    )
    market_cap_usd = float(
        company_info[company_info["field"] == "market_cap"]["value"].values[0]
    )

    # ── Compute WACC ──────────────────────────────────────────────────
    wacc_result = compute_wacc_from_data(
        config=config,
        financials=financials,
        market_cap_usd=market_cap_usd,
    )
    print_wacc_summary(wacc_result, title="WACC (Data-Driven)")

    # ── Run DCF ───────────────────────────────────────────────────────
    dcf_result = run_dcf(
        config=config,
        financials=financials,
        wacc_rate=wacc_result["wacc"],
        market_cap_usd=market_cap_usd,
    )
    print_dcf_summary(dcf_result)

    # ── Save projections ──────────────────────────────────────────────
    out_dir = PROJECT_ROOT / "data" / "processed"
    dcf_result["projections"].to_csv(out_dir / "dcf_projections.csv", index=False)
    print(f"[dcf] Saved projections → {out_dir / 'dcf_projections.csv'}")
