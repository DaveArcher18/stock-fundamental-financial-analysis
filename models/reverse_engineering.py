"""
Models — Reverse-Engineering Market-Implied Expectations
==========================================================
Solve for the growth rate, operating margin, or ROIC implied by the
current market price, given assumptions about the other parameters.

This is the "reverse DCF" or "expectations investing" approach
advocated by Damodaran and McKinsey.  Instead of asking "what is the
stock worth?", we ask "what must the market be assuming?"

Usage:
    python -m models.reverse_engineering
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ═══════════════════════════════════════════════════════════════════════════
# Core Solver
# ═══════════════════════════════════════════════════════════════════════════


def _bisect_solve(
    target_value: float,
    func,
    lo: float,
    hi: float,
    max_iter: int = 100,
    tol: float = 0.01,
) -> float:
    """Simple bisection solver — finds x such that func(x) ≈ target.

    Parameters
    ----------
    target_value : float
        The target output value.
    func : callable
        Function of one variable returning a float.
    lo, hi : float
        Bounds for the search.
    max_iter : int
        Maximum iterations.
    tol : float
        Absolute tolerance on the result.

    Returns
    -------
    float
        The value of x such that func(x) ≈ target_value.
    """
    for _ in range(max_iter):
        mid = (lo + hi) / 2.0
        val = func(mid)
        if abs(val - target_value) < tol:
            return mid
        if val < target_value:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


# ═══════════════════════════════════════════════════════════════════════════
# Implied Parameter Solvers
# ═══════════════════════════════════════════════════════════════════════════


def implied_growth_rate(
    target_price_per_share: float,
    financials: pd.DataFrame,
    config: dict,
    wacc_rate: float,
) -> float:
    """Solve for the revenue growth rate implied by the current price.

    Given all other DCF parameters, find the constant annual revenue
    growth rate that produces an intrinsic value equal to the
    current market price.

    Parameters
    ----------
    target_price_per_share : float
        Market price per share (in EUR).
    financials : pd.DataFrame
        Annual financials.
    config : dict
        Parsed assumptions.yaml.
    wacc_rate : float
        WACC to use.

    Returns
    -------
    float
        Implied annual revenue growth rate as a decimal.
    """
    from models.sensitivity import _dcf_value_per_share

    base_params = _build_base_params(financials, config, wacc_rate)

    def f(g):
        params = dict(base_params)
        params["growth_rate"] = g
        return _dcf_value_per_share(**params)

    return _bisect_solve(target_price_per_share, f, lo=0.0, hi=0.40)


def implied_operating_margin(
    target_price_per_share: float,
    financials: pd.DataFrame,
    config: dict,
    wacc_rate: float,
) -> float:
    """Solve for the operating margin implied by the current price.

    Parameters
    ----------
    target_price_per_share : float
        Market price per share (in EUR).
    financials : pd.DataFrame
        Annual financials.
    config : dict
        Parsed assumptions.yaml.
    wacc_rate : float
        WACC to use.

    Returns
    -------
    float
        Implied long-run operating margin as a decimal.
    """
    from models.sensitivity import _dcf_value_per_share

    base_params = _build_base_params(financials, config, wacc_rate)

    def f(m):
        params = dict(base_params)
        params["operating_margin"] = m
        return _dcf_value_per_share(**params)

    return _bisect_solve(target_price_per_share, f, lo=0.10, hi=0.70)


def implied_wacc(
    target_price_per_share: float,
    financials: pd.DataFrame,
    config: dict,
) -> float:
    """Solve for the WACC implied by the current price.

    Parameters
    ----------
    target_price_per_share : float
        Market price per share (in EUR).
    financials : pd.DataFrame
        Annual financials.
    config : dict
        Parsed assumptions.yaml.

    Returns
    -------
    float
        Implied WACC as a decimal.
    """
    from models.sensitivity import _dcf_value_per_share

    base_params = _build_base_params(financials, config, wacc_rate=0.09)

    def f(w):
        params = dict(base_params)
        params["wacc_rate"] = w
        return _dcf_value_per_share(**params)

    # WACC search: lower WACC → higher value, so invert
    # We need f(w) = target, but f is decreasing in w
    # Bisect still works — just swap lo/hi logic
    lo, hi = 0.03, 0.20
    for _ in range(100):
        mid = (lo + hi) / 2.0
        val = f(mid)
        if abs(val - target_price_per_share) < 0.01:
            return mid
        if val > target_price_per_share:
            lo = mid  # value too high → raise WACC
        else:
            hi = mid  # value too low → lower WACC
    return (lo + hi) / 2.0


def implied_terminal_growth(
    target_price_per_share: float,
    financials: pd.DataFrame,
    config: dict,
    wacc_rate: float,
) -> float:
    """Solve for the terminal growth rate implied by the current price.

    Parameters
    ----------
    target_price_per_share : float
        Market price per share (in EUR).
    financials : pd.DataFrame
        Annual financials.
    config : dict
        Parsed assumptions.yaml.
    wacc_rate : float
        WACC to use.

    Returns
    -------
    float
        Implied terminal growth rate as a decimal.
    """
    from models.sensitivity import _dcf_value_per_share

    base_params = _build_base_params(financials, config, wacc_rate)

    def f(tg):
        params = dict(base_params)
        params["terminal_growth"] = tg
        return _dcf_value_per_share(**params)

    return _bisect_solve(target_price_per_share, f, lo=0.005, hi=wacc_rate - 0.005)


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _build_base_params(
    financials: pd.DataFrame,
    config: dict,
    wacc_rate: float,
) -> dict:
    """Build the base parameter dict for the DCF wrapper."""
    return {
        "financials": financials,
        "wacc_rate": wacc_rate,
        "terminal_growth": config["projection"]["terminal_growth_rate"],
        "growth_rate": config["revenue"]["long_term_growth_rate"],
        "operating_margin": config["margins"]["operating_margin"],
        "tax_rate": config["tax"]["effective_rate"],
        "capex_to_revenue": config["capital_intensity"]["capex_to_revenue"],
        "depreciation_to_revenue": config["capital_intensity"]["depreciation_to_revenue"],
        "nwc_to_revenue": config["capital_intensity"]["nwc_to_revenue"],
    }


# ═══════════════════════════════════════════════════════════════════════════
# Pretty Printing
# ═══════════════════════════════════════════════════════════════════════════


def print_reverse_dcf_summary(results: dict) -> None:
    """Print a formatted reverse DCF summary."""
    width = 72
    print(f"\n{'═' * width}")
    print(f"  REVERSE DCF — MARKET-IMPLIED EXPECTATIONS")
    print(f"{'═' * width}")

    mkt = results["market"]
    print(f"\n  Current market price:     ~€{mkt['price_eur']:,.0f}")
    print(f"  Market cap (EUR):         €{mkt['market_cap_eur']/1e9:.0f}B")
    print(f"  Enterprise value (EUR):   €{mkt['ev_eur']/1e9:.0f}B")

    print(f"\n  ── What the Market Must Be Assuming ──\n")

    impl = results["implied"]

    # Growth
    g = impl["growth_rate"]
    print(f"  1. Implied Revenue Growth:     {g*100:.1f}% p.a. for 10 years")
    rev_base = results["base_revenue"]
    rev_implied = rev_base * (1 + g) ** 10
    print(f"     → FY2034E revenue: €{rev_implied/1e9:.0f}B "
          f"(from €{rev_base/1e9:.0f}B today, {rev_implied/rev_base:.1f}x)")

    # Margin
    m = impl["operating_margin"]
    current_m = results["current_op_margin"]
    print(f"\n  2. Implied Operating Margin:   {m*100:.1f}%")
    print(f"     (current: {current_m*100:.1f}%, "
          f"delta: {(m - current_m)*100:+.1f}pp)")

    # WACC
    w = impl["wacc"]
    actual_w = results["actual_wacc"]
    print(f"\n  3. Implied WACC:               {w*100:.2f}%")
    print(f"     (calculated: {actual_w*100:.2f}%, "
          f"delta: {(w - actual_w)*100:+.2f}pp)")

    # Terminal growth
    tg = impl["terminal_growth"]
    print(f"\n  4. Implied Terminal Growth:     {tg*100:.2f}%")
    print(f"     (assumption: {results['config_tg']*100:.2f}%)")

    # ── Plausibility Assessment ───────────────────────────────────────
    print(f"\n  ── Plausibility Assessment ──\n")

    # Growth check
    if g > 0.20:
        print(f"  ⚠ Growth ({g*100:.0f}%) exceeds historical CAGR — aggressive")
    elif g > 0.12:
        print(f"  ◐ Growth ({g*100:.0f}%) is ambitious but defensible if EUV ramp delivers")
    else:
        print(f"  ✓ Growth ({g*100:.0f}%) is within reasonable bounds")

    # Margin check
    if m > 0.45:
        print(f"  ⚠ Margin ({m*100:.0f}%) would exceed any semi peer — very aggressive")
    elif m > 0.38:
        print(f"  ◐ Margin ({m*100:.0f}%) requires significant mix shift to High-NA EUV")
    else:
        print(f"  ✓ Margin ({m*100:.0f}%) is achievable based on management guidance")

    # Terminal growth check
    if tg > 0.04:
        print(f"  ⚠ Terminal growth ({tg*100:.1f}%) exceeds nominal GDP — unsustainable")
    elif tg > 0.03:
        print(f"  ◐ Terminal growth ({tg*100:.1f}%) is at the upper bound of reasonable")
    else:
        print(f"  ✓ Terminal growth ({tg*100:.1f}%) is reasonable")

    # WACC check
    if w < 0.06:
        print(f"  ⚠ Implied WACC ({w*100:.1f}%) seems too low for equity risk")
    elif w < actual_w - 0.02:
        print(f"  ◐ Implied WACC ({w*100:.1f}%) is below calculated — market sees lower risk")
    else:
        print(f"  ✓ Implied WACC ({w*100:.1f}%) is consistent with fundamentals")

    print(f"\n{'═' * width}\n")


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    from models.wacc import compute_wacc_from_data

    # Load data
    config_path = PROJECT_ROOT / "config" / "assumptions.yaml"
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    financials = pd.read_csv(
        PROJECT_ROOT / "data" / "processed" / "financials_annual.csv",
        index_col=0, parse_dates=True,
    )

    company_info = pd.read_csv(
        PROJECT_ROOT / "data" / "raw" / "asml_company_info.csv",
    )
    market_cap_usd = float(
        company_info[company_info["field"] == "market_cap"]["value"].values[0]
    )

    # Compute WACC
    wacc_result = compute_wacc_from_data(
        config=config, financials=financials, market_cap_usd=market_cap_usd,
    )
    base_wacc = wacc_result["wacc"]

    # Market price in EUR
    usd_eur = 0.92
    shares = financials.iloc[-1]["shares_outstanding"]
    market_cap_eur = market_cap_usd * usd_eur
    market_price_eur = market_cap_eur / shares

    latest = financials.iloc[-1]
    net_debt = latest["long_term_debt"] - latest["cash"]
    ev_eur = market_cap_eur + net_debt  # neg net_debt →  net cash reduces EV

    print(f"\n  Solving for market-implied parameters...")
    print(f"  (this runs multiple DCF iterations — may take a few seconds)\n")

    # ── Solve for each implied parameter ──────────────────────────────
    ig = implied_growth_rate(market_price_eur, financials, config, base_wacc)
    print(f"  ✓ Implied growth:          {ig*100:.1f}%")

    im = implied_operating_margin(market_price_eur, financials, config, base_wacc)
    print(f"  ✓ Implied operating margin: {im*100:.1f}%")

    iw = implied_wacc(market_price_eur, financials, config)
    print(f"  ✓ Implied WACC:             {iw*100:.2f}%")

    itg = implied_terminal_growth(market_price_eur, financials, config, base_wacc)
    print(f"  ✓ Implied terminal growth:  {itg*100:.2f}%")

    # ── Assemble results ──────────────────────────────────────────────
    results = {
        "market": {
            "price_eur": market_price_eur,
            "market_cap_eur": market_cap_eur,
            "ev_eur": ev_eur,
        },
        "implied": {
            "growth_rate": ig,
            "operating_margin": im,
            "wacc": iw,
            "terminal_growth": itg,
        },
        "base_revenue": latest["revenue"],
        "current_op_margin": latest["operating_income"] / latest["revenue"],
        "actual_wacc": base_wacc,
        "config_tg": config["projection"]["terminal_growth_rate"],
    }

    print_reverse_dcf_summary(results)

    # Save
    out_dir = PROJECT_ROOT / "data" / "processed"
    summary = pd.DataFrame([{
        "market_price_eur": market_price_eur,
        "implied_growth": ig,
        "implied_operating_margin": im,
        "implied_wacc": iw,
        "implied_terminal_growth": itg,
        "actual_wacc": base_wacc,
    }])
    summary.to_csv(out_dir / "reverse_dcf_implied.csv", index=False)
    print(f"  Saved → {out_dir / 'reverse_dcf_implied.csv'}")
