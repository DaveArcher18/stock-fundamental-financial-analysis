"""
Processing — Compute Financial Ratios
=======================================
Computes key profitability, efficiency, and growth ratios from
cleaned income-statement and cash-flow data.

All formulas are documented inline.  Functions are pure.
"""

import pandas as pd
import numpy as np


# ── Margin Ratios ──────────────────────────────────────────────────────────


def gross_margin(revenue: pd.Series, cost_of_revenue: pd.Series) -> pd.Series:
    """Gross margin = (Revenue − COGS) / Revenue.

    Parameters
    ----------
    revenue : pd.Series
    cost_of_revenue : pd.Series

    Returns
    -------
    pd.Series
    """
    return (revenue - cost_of_revenue) / revenue


def operating_margin(revenue: pd.Series, operating_income: pd.Series) -> pd.Series:
    """Operating (EBIT) margin = Operating Income / Revenue.

    Parameters
    ----------
    revenue : pd.Series
    operating_income : pd.Series

    Returns
    -------
    pd.Series
    """
    return operating_income / revenue


def net_margin(revenue: pd.Series, net_income: pd.Series) -> pd.Series:
    """Net profit margin = Net Income / Revenue.

    Parameters
    ----------
    revenue : pd.Series
    net_income : pd.Series

    Returns
    -------
    pd.Series
    """
    return net_income / revenue


def fcf_margin(revenue: pd.Series, free_cash_flow: pd.Series) -> pd.Series:
    """Free-cash-flow margin = FCF / Revenue.

    Parameters
    ----------
    revenue : pd.Series
    free_cash_flow : pd.Series

    Returns
    -------
    pd.Series
    """
    return free_cash_flow / revenue


# ── Growth Ratios ──────────────────────────────────────────────────────────


def revenue_growth(revenue: pd.Series) -> pd.Series:
    """Year-over-year revenue growth rate.

    Formula
    -------
        g_t = (Revenue_t − Revenue_{t-1}) / Revenue_{t-1}

    Parameters
    ----------
    revenue : pd.Series

    Returns
    -------
    pd.Series
        First element will be NaN (no prior period).
    """
    return revenue.pct_change()


# ── Efficiency Ratios ──────────────────────────────────────────────────────


def capex_to_revenue(revenue: pd.Series, capex: pd.Series) -> pd.Series:
    """Capital expenditure intensity = |Capex| / Revenue.

    Note: Capex is typically reported as a negative number in cash-flow
    statements.  This function takes the absolute value for clarity.

    Parameters
    ----------
    revenue : pd.Series
    capex : pd.Series

    Returns
    -------
    pd.Series
    """
    return capex.abs() / revenue


def rd_to_revenue(revenue: pd.Series, rd_expense: pd.Series) -> pd.Series:
    """R&D intensity = R&D Expense / Revenue.

    Parameters
    ----------
    revenue : pd.Series
    rd_expense : pd.Series

    Returns
    -------
    pd.Series
    """
    return rd_expense.abs() / revenue


# ── Consolidated Ratio Table ──────────────────────────────────────────────


def compute_all_ratios(
    income_stmt: pd.DataFrame,
    cash_flow: pd.DataFrame,
) -> pd.DataFrame:
    """Compute a consolidated table of key financial ratios.

    Parameters
    ----------
    income_stmt : pd.DataFrame
        Cleaned income statement with columns: ``revenue``,
        ``cost_of_revenue``, ``operating_income``, ``net_income``,
        ``rd_expense``.
    cash_flow : pd.DataFrame
        Cleaned cash-flow statement with columns: ``free_cash_flow``,
        ``capex``.  Must share the same index (dates) as *income_stmt*.

    Returns
    -------
    pd.DataFrame
        DataFrame indexed by date with one column per ratio.
    """
    rev = income_stmt["revenue"]

    ratios = pd.DataFrame(index=income_stmt.index)
    ratios["gross_margin"] = gross_margin(rev, income_stmt["cost_of_revenue"])
    ratios["operating_margin"] = operating_margin(rev, income_stmt["operating_income"])
    ratios["net_margin"] = net_margin(rev, income_stmt["net_income"])
    ratios["revenue_growth"] = revenue_growth(rev)
    ratios["rd_to_revenue"] = rd_to_revenue(rev, income_stmt["rd_expense"])

    # Cash-flow ratios — align on the same index
    if "free_cash_flow" in cash_flow.columns:
        fcf = cash_flow["free_cash_flow"].reindex(income_stmt.index)
        ratios["fcf_margin"] = fcf_margin(rev, fcf)
    if "capex" in cash_flow.columns:
        capex = cash_flow["capex"].reindex(income_stmt.index)
        ratios["capex_to_revenue"] = capex_to_revenue(rev, capex)

    return ratios
