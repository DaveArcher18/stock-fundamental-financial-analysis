"""
Processing — Return on Invested Capital (ROIC)
================================================
Computes invested capital, NOPAT, ROIC, and incremental ROIC from
cleaned balance-sheet and income-statement data.

All formulas follow McKinsey / Damodaran conventions and are documented
inline.  Functions are pure.
"""

import pandas as pd
import numpy as np


def compute_nopat(
    operating_income: pd.Series,
    tax_rate: pd.Series | float,
) -> pd.Series:
    """Net Operating Profit After Taxes.

    Formula
    -------
        NOPAT = EBIT × (1 − Tax Rate)

    Parameters
    ----------
    operating_income : pd.Series
        EBIT (Earnings Before Interest and Taxes).
    tax_rate : pd.Series | float
        Effective tax rate (decimal, e.g. 0.15 for 15 %).

    Returns
    -------
    pd.Series
    """
    return operating_income * (1.0 - tax_rate)


def compute_invested_capital(
    total_assets: pd.Series,
    cash: pd.Series,
    accounts_payable: pd.Series,
    total_current_liabilities: pd.Series,
    short_term_debt: pd.Series,
) -> pd.Series:
    """Invested Capital (operating definition).

    Formula
    -------
        Invested Capital = Total Assets
                         − Excess Cash
                         − Non-debt Current Liabilities

    Where non-debt current liabilities ≈ Total Current Liabilities − Short-Term Debt.

    This approximation captures the operating asset base that earns returns,
    net of operating liabilities that are effectively interest-free financing.

    Parameters
    ----------
    total_assets : pd.Series
    cash : pd.Series
        Cash and cash equivalents.
    accounts_payable : pd.Series
        (Currently unused — included for extensibility with more granular splits.)
    total_current_liabilities : pd.Series
    short_term_debt : pd.Series

    Returns
    -------
    pd.Series
    """
    # Non-debt current liabilities = total current liabilities − short-term debt
    non_debt_current_liab = total_current_liabilities - short_term_debt

    invested_capital = total_assets - cash - non_debt_current_liab
    return invested_capital


def compute_roic(
    nopat: pd.Series,
    invested_capital: pd.Series,
) -> pd.Series:
    """Return on Invested Capital.

    Formula
    -------
        ROIC_t = NOPAT_t / Invested Capital_{t-1}

    Uses beginning-of-period invested capital (i.e. prior year's closing balance)
    to match the income earned during the period.

    Parameters
    ----------
    nopat : pd.Series
    invested_capital : pd.Series

    Returns
    -------
    pd.Series
        First element will be NaN (no prior-period capital).
    """
    # Beginning-of-period IC = prior year's closing IC
    beginning_ic = invested_capital.shift(1)
    return nopat / beginning_ic


def compute_incremental_roic(
    nopat: pd.Series,
    invested_capital: pd.Series,
) -> pd.Series:
    """Incremental (marginal) ROIC — return on *new* invested capital.

    Formula
    -------
        ROIIC_t = ΔNOPAT_t / ΔInvested Capital_{t-1}

    This measures the return earned on the *change* in invested capital,
    which is the relevant metric when assessing whether new investments
    create or destroy value.

    Parameters
    ----------
    nopat : pd.Series
    invested_capital : pd.Series

    Returns
    -------
    pd.Series
        First two elements will be NaN.
    """
    delta_nopat = nopat.diff()
    delta_ic = invested_capital.diff().shift(1)

    # Avoid division by zero / near-zero
    incremental = delta_nopat / delta_ic
    incremental = incremental.where(delta_ic.abs() > 1e-6, np.nan)

    return incremental


def compute_roic_table(
    income_stmt: pd.DataFrame,
    balance_sheet: pd.DataFrame,
    tax_rate: float = 0.15,
) -> pd.DataFrame:
    """Build a consolidated ROIC analysis table.

    Parameters
    ----------
    income_stmt : pd.DataFrame
        Cleaned income statement with column ``operating_income``.
    balance_sheet : pd.DataFrame
        Cleaned balance sheet with columns: ``total_assets``, ``cash``,
        ``accounts_payable``, ``total_current_liabilities``,
        ``short_term_debt``.
    tax_rate : float
        Effective tax rate for NOPAT computation.

    Returns
    -------
    pd.DataFrame
        Columns: ``nopat``, ``invested_capital``, ``roic``,
        ``incremental_roic``.
    """
    nopat = compute_nopat(income_stmt["operating_income"], tax_rate)

    ic = compute_invested_capital(
        total_assets=balance_sheet["total_assets"],
        cash=balance_sheet["cash"],
        accounts_payable=balance_sheet["accounts_payable"],
        total_current_liabilities=balance_sheet["total_current_liabilities"],
        short_term_debt=balance_sheet["short_term_debt"],
    )

    roic = compute_roic(nopat, ic)
    inc_roic = compute_incremental_roic(nopat, ic)

    result = pd.DataFrame(
        {
            "nopat": nopat,
            "invested_capital": ic,
            "roic": roic,
            "incremental_roic": inc_roic,
        },
        index=income_stmt.index,
    )

    return result
