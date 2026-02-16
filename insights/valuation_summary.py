"""
Insights — Valuation Summary
==============================
Consolidated output module that brings together all valuation results
into a structured summary for review and reporting.

This module will be populated once the DCF, WACC, and sensitivity
models are implemented.
"""

import pandas as pd
from typing import Optional


def compile_valuation_summary(
    company_name: str,
    ticker: str,
    wacc: Optional[float] = None,
    enterprise_value: Optional[float] = None,
    equity_value: Optional[float] = None,
    equity_value_per_share: Optional[float] = None,
    current_price: Optional[float] = None,
    terminal_growth: Optional[float] = None,
    roic_table: Optional[pd.DataFrame] = None,
    ratios: Optional[pd.DataFrame] = None,
) -> dict:
    """Compile a structured valuation summary dictionary.

    Parameters
    ----------
    company_name : str
    ticker : str
    wacc : float | None
    enterprise_value : float | None
    equity_value : float | None
    equity_value_per_share : float | None
    current_price : float | None
    terminal_growth : float | None
    roic_table : pd.DataFrame | None
    ratios : pd.DataFrame | None

    Returns
    -------
    dict
        Structured summary with keys: ``company``, ``valuation``,
        ``implied_upside``, ``key_ratios``, ``roic``.
    """
    summary: dict = {
        "company": {
            "name": company_name,
            "ticker": ticker,
        },
        "valuation": {
            "wacc": wacc,
            "terminal_growth": terminal_growth,
            "enterprise_value": enterprise_value,
            "equity_value": equity_value,
            "equity_value_per_share": equity_value_per_share,
            "current_price": current_price,
        },
    }

    # Implied upside / downside
    if equity_value_per_share is not None and current_price is not None and current_price > 0:
        summary["implied_upside"] = (equity_value_per_share / current_price) - 1.0
    else:
        summary["implied_upside"] = None

    # Latest key ratios snapshot
    if ratios is not None and not ratios.empty:
        summary["key_ratios"] = ratios.iloc[-1].to_dict()
    else:
        summary["key_ratios"] = None

    # Latest ROIC snapshot
    if roic_table is not None and not roic_table.empty:
        summary["roic"] = roic_table.iloc[-1].to_dict()
    else:
        summary["roic"] = None

    return summary


def print_valuation_summary(summary: dict) -> None:
    """Pretty-print the valuation summary to stdout.

    Parameters
    ----------
    summary : dict
        Output from :func:`compile_valuation_summary`.
    """
    print("\n" + "=" * 60)
    print("  VALUATION SUMMARY")
    print("=" * 60)

    company = summary.get("company", {})
    print(f"\n  Company: {company.get('name', 'N/A')} ({company.get('ticker', 'N/A')})")

    val = summary.get("valuation", {})
    for key, value in val.items():
        if value is not None:
            if isinstance(value, float) and abs(value) < 1:
                print(f"  {key:30s}: {value:.2%}")
            elif isinstance(value, float):
                print(f"  {key:30s}: {value:,.0f}")
            else:
                print(f"  {key:30s}: {value}")

    upside = summary.get("implied_upside")
    if upside is not None:
        direction = "UPSIDE" if upside >= 0 else "DOWNSIDE"
        print(f"\n  Implied {direction}: {abs(upside):.1%}")

    print("=" * 60 + "\n")
