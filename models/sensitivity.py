"""
Models — Sensitivity Analysis
================================
Two-way sensitivity tables and tornado chart data showing how intrinsic
value per share varies with changes in key DCF parameters.

This module does NOT depend on the specific DCF implementation — it
operates on a generic ``valuation_func(params) → float`` interface,
so it can be reused across different valuation models.

Usage:
    python -m models.sensitivity
"""

import sys
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ═══════════════════════════════════════════════════════════════════════════
# Generic Sensitivity Engines
# ═══════════════════════════════════════════════════════════════════════════


def two_way_sensitivity(
    valuation_func: Callable[..., float],
    base_params: dict,
    param_x: str,
    param_x_range: list[float],
    param_y: str,
    param_y_range: list[float],
) -> pd.DataFrame:
    """Generate a two-way sensitivity table.

    For each combination of (param_x_value, param_y_value), calls
    ``valuation_func(**modified_params)`` and records the result.

    Parameters
    ----------
    valuation_func : Callable[..., float]
        A function that takes keyword arguments and returns a single
        numeric output (e.g. equity value per share).
    base_params : dict
        Baseline parameter dictionary passed to *valuation_func*.
    param_x : str
        Name of the first sensitivity parameter (row axis).
    param_x_range : list[float]
        Values to sweep for param_x.
    param_y : str
        Name of the second sensitivity parameter (column axis).
    param_y_range : list[float]
        Values to sweep for param_y.

    Returns
    -------
    pd.DataFrame
        Sensitivity matrix with shape (len(param_x_range), len(param_y_range)).
        Index = param_x values, Columns = param_y values.
    """
    results = []
    for x_val in param_x_range:
        row = []
        for y_val in param_y_range:
            params = dict(base_params)
            params[param_x] = x_val
            params[param_y] = y_val
            row.append(valuation_func(**params))
        results.append(row)

    return pd.DataFrame(
        results,
        index=pd.Index(param_x_range, name=param_x),
        columns=pd.Index(param_y_range, name=param_y),
    )


def tornado_chart_data(
    valuation_func: Callable[..., float],
    base_params: dict,
    sensitivity_specs: dict[str, tuple[float, float]],
) -> pd.DataFrame:
    """Generate data for a tornado (single-parameter) sensitivity chart.

    Each parameter is varied independently (low, high) while all others
    stay at their base values.

    Parameters
    ----------
    valuation_func : Callable[..., float]
        Function that returns a valuation output.
    base_params : dict
        Baseline parameter dictionary.
    sensitivity_specs : dict[str, tuple[float, float]]
        Mapping of ``{parameter_name: (low_value, high_value)}``.

    Returns
    -------
    pd.DataFrame
        Columns: ``parameter``, ``low_value``, ``high_value``,
        ``low_result``, ``high_result``, ``base_result``, ``swing``.
        Sorted by absolute swing descending (most sensitive first).
    """
    base_result = valuation_func(**base_params)

    rows = []
    for param_name, (low_val, high_val) in sensitivity_specs.items():
        # Low scenario
        params_low = dict(base_params)
        params_low[param_name] = low_val
        low_result = valuation_func(**params_low)

        # High scenario
        params_high = dict(base_params)
        params_high[param_name] = high_val
        high_result = valuation_func(**params_high)

        swing = abs(high_result - low_result)

        rows.append({
            "parameter": param_name,
            "base_value": base_params[param_name],
            "low_value": low_val,
            "high_value": high_val,
            "low_result": low_result,
            "high_result": high_result,
            "base_result": base_result,
            "swing": swing,
        })

    df = pd.DataFrame(rows)
    df = df.sort_values("swing", ascending=False).reset_index(drop=True)
    return df


# ═══════════════════════════════════════════════════════════════════════════
# ASML-Specific DCF Wrapper
# ═══════════════════════════════════════════════════════════════════════════

def _dcf_value_per_share(
    financials: pd.DataFrame,
    wacc_rate: float,
    terminal_growth: float,
    growth_rate: float,
    operating_margin: float,
    tax_rate: float,
    capex_to_revenue: float,
    depreciation_to_revenue: float,
    nwc_to_revenue: float,
    explicit_years: int = 10,
) -> float:
    """Thin wrapper around the DCF model returning value per share.

    All parameters that the sensitivity analysis might vary are made
    explicit keyword arguments so they can be overridden by the
    generic sensitivity engine.
    """
    from models.dcf import (
        build_growth_schedule,
        build_margin_schedule,
        project_fcf,
        terminal_value,
        enterprise_value,
        equity_value_per_share,
    )

    latest = financials.iloc[-1]
    base_revenue = latest["revenue"]

    # Safe column access for cross-company XBRL variation
    def _get(key, fallbacks=None, default=0.0):
        if key in latest.index and pd.notna(latest[key]):
            return latest[key]
        for fb in (fallbacks or []):
            if fb in latest.index and pd.notna(latest[fb]):
                return latest[fb]
        return default

    cash = _get("cash", ["cash_and_equivalents"])
    total_debt = _get("long_term_debt", ["total_debt", "debt_current"])
    net_debt = total_debt - cash
    shares = _get("shares_outstanding", ["shares_outstanding_basic", "common_shares_outstanding"])

    op_inc = _get("operating_income", ["income_from_operations"], default=None)
    if op_inc is None or base_revenue == 0:
        current_op_margin = operating_margin  # use the passed-in parameter
    else:
        current_op_margin = op_inc / base_revenue

    growth_schedule = [growth_rate] * explicit_years

    margin_schedule = build_margin_schedule(
        explicit_years=explicit_years,
        current_margin=current_op_margin,
        target_margin=operating_margin,
        fade_years=5,
    )

    projections = project_fcf(
        base_revenue=base_revenue,
        growth_rates=growth_schedule,
        operating_margins=margin_schedule,
        tax_rate=tax_rate,
        capex_to_revenue=capex_to_revenue,
        depreciation_to_revenue=depreciation_to_revenue,
        nwc_to_revenue=nwc_to_revenue,
    )

    final_fcff = projections.iloc[-1]["fcff"]
    tv = terminal_value(final_fcff, terminal_growth, wacc_rate)

    ev_result = enterprise_value(
        fcff_series=projections["fcff"],
        wacc=wacc_rate,
        tv=tv,
        terminal_year=explicit_years,
    )

    eq = equity_value_per_share(
        ev=ev_result["enterprise_value"],
        net_debt=net_debt,
        shares_outstanding=shares,
    )

    return eq["value_per_share"]


# ═══════════════════════════════════════════════════════════════════════════
# Pretty Printing
# ═══════════════════════════════════════════════════════════════════════════


def print_sensitivity_table(
    table: pd.DataFrame,
    param_x_label: str,
    param_y_label: str,
    title: str,
    format_fn=None,
    base_x: float = None,
    base_y: float = None,
) -> None:
    """Print a formatted two-way sensitivity table."""
    width = max(72, 12 * len(table.columns) + 20)
    print(f"\n{'═' * width}")
    print(f"  {title}")
    print(f"  Row: {param_x_label}  |  Column: {param_y_label}")
    print(f"{'═' * width}\n")

    if format_fn is None:
        format_fn = lambda x: f"€{x:,.0f}"

    # Build formatted table
    formatted = table.copy()
    for col in formatted.columns:
        formatted[col] = formatted[col].apply(format_fn)

    # Label columns
    col_labels = []
    for c in table.columns:
        marker = " ◄" if base_y is not None and abs(c - base_y) < 1e-6 else ""
        if abs(c) < 1 and c != 0:
            col_labels.append(f"{c*100:.1f}%{marker}")
        else:
            col_labels.append(f"{c}{marker}")
    formatted.columns = col_labels

    # Label rows
    row_labels = []
    for r in table.index:
        marker = " ◄" if base_x is not None and abs(r - base_x) < 1e-6 else ""
        if abs(r) < 1 and r != 0:
            row_labels.append(f"{r*100:.1f}%{marker}")
        else:
            row_labels.append(f"{r}{marker}")
    formatted.index = row_labels

    print(formatted.to_string())
    print()


def print_tornado(tornado_df: pd.DataFrame, title: str = "TORNADO ANALYSIS") -> None:
    """Print a formatted tornado chart as text."""
    width = 72
    print(f"\n{'═' * width}")
    print(f"  {title}")
    print(f"{'═' * width}\n")

    base = tornado_df.iloc[0]["base_result"]
    print(f"  Base case value: €{base:,.0f}\n")

    # Find max swing for bar scaling
    max_swing = tornado_df["swing"].max()

    for _, row in tornado_df.iterrows():
        param = row["parameter"]
        low_r = row["low_result"]
        high_r = row["high_result"]
        swing = row["swing"]

        # Format parameter range
        bv = row["base_value"]
        lv = row["low_value"]
        hv = row["high_value"]

        if abs(bv) < 1 and bv != 0:
            range_str = f"{lv*100:.1f}% → {hv*100:.1f}%"
        else:
            range_str = f"{lv} → {hv}"

        # ASCII bar — skip NaN swings
        bar_width = 30
        if pd.isna(swing) or pd.isna(max_swing) or max_swing <= 0:
            bar_len = 0
        else:
            bar_len = int(swing / max_swing * bar_width)
        bar = "█" * bar_len

        low_str = f"€{low_r:,.0f}"
        high_str = f"€{high_r:,.0f}"

        print(f"  {param:<28s}  {bar}  €{swing:,.0f}")
        print(f"    ({range_str}): {low_str} — {high_str}")
        print()


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

    ticker = config.get("company", {}).get("ticker", "ASML").lower()
    company_info = pd.read_csv(
        PROJECT_ROOT / "data" / "raw" / f"{ticker}_company_info.csv",
    )
    market_cap_usd = float(
        company_info[company_info["field"] == "market_cap"]["value"].values[0]
    )

    # Compute baseline WACC
    wacc_result = compute_wacc_from_data(
        config=config, financials=financials, market_cap_usd=market_cap_usd,
    )
    base_wacc = wacc_result["wacc"]

    # ── Base parameters ───────────────────────────────────────────────
    base_params = {
        "financials": financials,
        "wacc_rate": base_wacc,
        "terminal_growth": config["projection"]["terminal_growth_rate"],
        "growth_rate": config["revenue"]["long_term_growth_rate"],
        "operating_margin": config["margins"]["operating_margin"],
        "tax_rate": config["tax"]["effective_rate"],
        "capex_to_revenue": config["capital_intensity"]["capex_to_revenue"],
        "depreciation_to_revenue": config["capital_intensity"]["depreciation_to_revenue"],
        "nwc_to_revenue": config["capital_intensity"]["nwc_to_revenue"],
    }

    # Safe shares lookup
    latest = financials.iloc[-1]
    shares = latest.get("shares_outstanding",
             latest.get("shares_outstanding_basic",
             latest.get("common_shares_outstanding", 1)))
    market_price_eur = (market_cap_usd * 0.92) / shares

    company_name = config.get("company", {}).get("name", "COMPANY")
    print(f"\n{'═' * 72}")
    print(f"  SENSITIVITY ANALYSIS — {company_name} DCF")
    print(f"{'═' * 72}")
    print(f"\n  Base case value/share: €{base_vps:,.0f}")
    print(f"  Current market price:  ~€{market_price_eur:,.0f}  (est. EUR)")

    # ══════════════════════════════════════════════════════════════════
    # TABLE 1: WACC × Terminal Growth
    # ══════════════════════════════════════════════════════════════════
    wacc_range = [0.070, 0.075, 0.080, 0.085, base_wacc, 0.095, 0.100, 0.105, 0.110]
    wacc_range = sorted(set(round(w, 4) for w in wacc_range))
    tg_range = [0.015, 0.020, 0.025, 0.030, 0.035]

    table1 = two_way_sensitivity(
        valuation_func=_dcf_value_per_share,
        base_params=base_params,
        param_x="wacc_rate",
        param_x_range=wacc_range,
        param_y="terminal_growth",
        param_y_range=tg_range,
    )

    print_sensitivity_table(
        table1,
        param_x_label="WACC",
        param_y_label="Terminal Growth (g∞)",
        title="TABLE 1: Value/Share — WACC × Terminal Growth",
        base_x=base_wacc,
        base_y=config["projection"]["terminal_growth_rate"],
    )

    # ══════════════════════════════════════════════════════════════════
    # TABLE 2: Revenue Growth × Operating Margin
    # ══════════════════════════════════════════════════════════════════
    growth_range = [0.04, 0.06, 0.08, 0.10, 0.12, 0.14, 0.16, 0.18]
    margin_range = [0.30, 0.32, 0.35, 0.38, 0.40]

    table2 = two_way_sensitivity(
        valuation_func=_dcf_value_per_share,
        base_params=base_params,
        param_x="growth_rate",
        param_x_range=growth_range,
        param_y="operating_margin",
        param_y_range=margin_range,
    )

    print_sensitivity_table(
        table2,
        param_x_label="Revenue Growth",
        param_y_label="Operating Margin",
        title="TABLE 2: Value/Share — Revenue Growth × Operating Margin",
        base_x=config["revenue"]["long_term_growth_rate"],
        base_y=config["margins"]["operating_margin"],
    )

    # ══════════════════════════════════════════════════════════════════
    # TABLE 3: Revenue Growth × WACC  (the money table)
    # ══════════════════════════════════════════════════════════════════
    table3 = two_way_sensitivity(
        valuation_func=_dcf_value_per_share,
        base_params=base_params,
        param_x="growth_rate",
        param_x_range=growth_range,
        param_y="wacc_rate",
        param_y_range=wacc_range,
    )

    print_sensitivity_table(
        table3,
        param_x_label="Revenue Growth",
        param_y_label="WACC",
        title="TABLE 3: Value/Share — Revenue Growth × WACC",
        base_x=config["revenue"]["long_term_growth_rate"],
        base_y=base_wacc,
    )

    # ══════════════════════════════════════════════════════════════════
    # TORNADO: Which parameter moves the needle most?
    # ══════════════════════════════════════════════════════════════════
    tornado_specs = {
        "growth_rate":             (0.03,  0.18),
        "operating_margin":        (0.28,  0.42),
        "wacc_rate":               (0.07,  0.11),
        "terminal_growth":         (0.015, 0.035),
        "tax_rate":                (0.10,  0.20),
        "capex_to_revenue":        (0.04,  0.10),
        "nwc_to_revenue":          (0.10,  0.20),
    }

    tornado = tornado_chart_data(
        valuation_func=_dcf_value_per_share,
        base_params=base_params,
        sensitivity_specs=tornado_specs,
    )

    print_tornado(tornado, title="TORNADO: Impact on Value/Share")

    # ══════════════════════════════════════════════════════════════════
    # KEY INSIGHT: What growth justifies the market price?
    # ══════════════════════════════════════════════════════════════════
    print(f"{'═' * 72}")
    print(f"  KEY INSIGHT: What growth rate justifies ~€{market_price_eur:,.0f}?")
    print(f"{'═' * 72}\n")

    # Binary search for implied growth
    lo, hi = 0.01, 0.30
    for _ in range(50):
        mid = (lo + hi) / 2
        params = dict(base_params)
        params["growth_rate"] = mid
        val = _dcf_value_per_share(**params)
        if val < market_price_eur:
            lo = mid
        else:
            hi = mid

    implied_growth = (lo + hi) / 2
    print(f"  To justify the current market price of ~€{market_price_eur:,.0f},")
    print(f"  ASML needs to grow revenue at {implied_growth*100:.1f}% p.a. for 10 years")
    print(f"  (assuming {base_wacc*100:.1f}% WACC, "
          f"{config['margins']['operating_margin']*100:.0f}% terminal op. margin).")
    print()

    latest_rev = financials.iloc[-1]["revenue"]
    implied_rev_10y = latest_rev * (1 + implied_growth) ** 10
    print(f"  That implies FY2034 revenue of €{implied_rev_10y/1e9:.0f}B")
    print(f"  (up from €{latest_rev/1e9:.0f}B today — a {implied_rev_10y/latest_rev:.1f}x increase).")
    print()

    # Save tables
    out_dir = PROJECT_ROOT / "data" / "processed"
    table1.to_csv(out_dir / "sensitivity_wacc_tg.csv")
    table2.to_csv(out_dir / "sensitivity_growth_margin.csv")
    table3.to_csv(out_dir / "sensitivity_growth_wacc.csv")
    tornado.to_csv(out_dir / "tornado_analysis.csv", index=False)

    print(f"  Saved to {out_dir}/:")
    print(f"    • sensitivity_wacc_tg.csv")
    print(f"    • sensitivity_growth_margin.csv")
    print(f"    • sensitivity_growth_wacc.csv")
    print(f"    • tornado_analysis.csv")
    print(f"{'═' * 72}\n")
