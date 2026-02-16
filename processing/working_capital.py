"""
Processing — Working Capital Analysis
=======================================
Computes net working capital, working-capital days (DSO, DIO, DPO),
and change in NWC (ΔNWC) from cleaned financial statements.

Working capital swings are material for capital-equipment companies with
long build cycles and cyclical order patterns.  All formulas are documented
inline.
"""

import pandas as pd
import numpy as np


def compute_net_working_capital(
    accounts_receivable: pd.Series,
    inventory: pd.Series,
    accounts_payable: pd.Series,
) -> pd.Series:
    """Net Working Capital (operating definition).

    Formula
    -------
        NWC = Accounts Receivable + Inventory − Accounts Payable

    This is the *operating* NWC — excludes cash, short-term debt, and
    other non-operating current items.

    Parameters
    ----------
    accounts_receivable : pd.Series
    inventory : pd.Series
    accounts_payable : pd.Series

    Returns
    -------
    pd.Series
    """
    return accounts_receivable + inventory - accounts_payable


def compute_change_in_nwc(nwc: pd.Series) -> pd.Series:
    """Change in net working capital (ΔNWC).

    Formula
    -------
        ΔNWC_t = NWC_t − NWC_{t-1}

    A positive ΔNWC represents a *use* of cash (working capital build);
    a negative ΔNWC represents a *source* of cash (working capital release).

    Parameters
    ----------
    nwc : pd.Series

    Returns
    -------
    pd.Series
        First element will be NaN.
    """
    return nwc.diff()


def days_sales_outstanding(
    accounts_receivable: pd.Series,
    revenue: pd.Series,
    days_in_year: int = 365,
) -> pd.Series:
    """Days Sales Outstanding (DSO).

    Formula
    -------
        DSO = (Accounts Receivable / Revenue) × Days in Year

    Parameters
    ----------
    accounts_receivable : pd.Series
    revenue : pd.Series
    days_in_year : int

    Returns
    -------
    pd.Series
    """
    return (accounts_receivable / revenue) * days_in_year


def days_inventory_outstanding(
    inventory: pd.Series,
    cost_of_revenue: pd.Series,
    days_in_year: int = 365,
) -> pd.Series:
    """Days Inventory Outstanding (DIO).

    Formula
    -------
        DIO = (Inventory / COGS) × Days in Year

    Parameters
    ----------
    inventory : pd.Series
    cost_of_revenue : pd.Series
    days_in_year : int

    Returns
    -------
    pd.Series
    """
    return (inventory / cost_of_revenue) * days_in_year


def days_payable_outstanding(
    accounts_payable: pd.Series,
    cost_of_revenue: pd.Series,
    days_in_year: int = 365,
) -> pd.Series:
    """Days Payable Outstanding (DPO).

    Formula
    -------
        DPO = (Accounts Payable / COGS) × Days in Year

    Parameters
    ----------
    accounts_payable : pd.Series
    cost_of_revenue : pd.Series
    days_in_year : int

    Returns
    -------
    pd.Series
    """
    return (accounts_payable / cost_of_revenue) * days_in_year


def cash_conversion_cycle(
    dso: pd.Series,
    dio: pd.Series,
    dpo: pd.Series,
) -> pd.Series:
    """Cash Conversion Cycle (CCC).

    Formula
    -------
        CCC = DSO + DIO − DPO

    A shorter CCC indicates more efficient working-capital management.

    Parameters
    ----------
    dso : pd.Series
    dio : pd.Series
    dpo : pd.Series

    Returns
    -------
    pd.Series
    """
    return dso + dio - dpo


def compute_working_capital_table(
    balance_sheet: pd.DataFrame,
    income_stmt: pd.DataFrame,
) -> pd.DataFrame:
    """Build a consolidated working-capital analysis table.

    Parameters
    ----------
    balance_sheet : pd.DataFrame
        Cleaned balance sheet with columns: ``accounts_receivable``,
        ``inventory``, ``accounts_payable``.
    income_stmt : pd.DataFrame
        Cleaned income statement with columns: ``revenue``,
        ``cost_of_revenue``.

    Returns
    -------
    pd.DataFrame
        Columns: ``nwc``, ``delta_nwc``, ``dso``, ``dio``, ``dpo``, ``ccc``.
    """
    ar = balance_sheet["accounts_receivable"]
    inv = balance_sheet["inventory"]
    ap = balance_sheet["accounts_payable"]
    rev = income_stmt["revenue"]
    cogs = income_stmt["cost_of_revenue"]

    nwc = compute_net_working_capital(ar, inv, ap)
    delta = compute_change_in_nwc(nwc)
    dso = days_sales_outstanding(ar, rev)
    dio = days_inventory_outstanding(inv, cogs)
    dpo = days_payable_outstanding(ap, cogs)
    ccc = cash_conversion_cycle(dso, dio, dpo)

    result = pd.DataFrame(
        {
            "nwc": nwc,
            "delta_nwc": delta,
            "dso": dso,
            "dio": dio,
            "dpo": dpo,
            "ccc": ccc,
        },
        index=balance_sheet.index,
    )

    return result
