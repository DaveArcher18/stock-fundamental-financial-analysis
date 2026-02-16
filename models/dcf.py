"""
Models — Discounted Cash Flow (DCF) Valuation
===============================================
Functions to project Free Cash Flow to the Firm (FCFF), compute terminal
value, and derive enterprise value via explicit-period DCF.

Scaffold — function signatures and docstrings only.
Implementation to follow once WACC and projection assumptions are calibrated.
"""

import pandas as pd
import numpy as np


def project_fcf(
    base_revenue: float,
    growth_rates: list[float],
    operating_margin: float,
    tax_rate: float,
    capex_to_revenue: float,
    depreciation_to_revenue: float,
    nwc_to_revenue: float,
) -> pd.DataFrame:
    """Project Free Cash Flow to the Firm (FCFF) over an explicit horizon.

    Formula (per period)
    --------------------
        Revenue_t      = Revenue_{t-1} × (1 + g_t)
        EBIT_t         = Revenue_t × operating_margin
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
    operating_margin : float
        Assumed EBIT / Revenue for all projection years (or could be
        extended to accept a list for year-by-year variation).
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
        ``ebit``, ``nopat``, ``net_capex``, ``delta_nwc``, ``fcff``.
    """
    # TODO: Implement
    raise NotImplementedError("project_fcf — implementation pending.")


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

    where g∞ is the perpetual growth rate (must be < WACC).

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
    # TODO: Implement
    raise NotImplementedError("terminal_value — implementation pending.")


def enterprise_value(
    fcff_series: pd.Series,
    wacc: float,
    terminal_value: float,
    terminal_year: int,
) -> float:
    """Compute Enterprise Value by discounting projected FCFF and TV.

    Formula
    -------
        EV = Σ_{t=1}^{T} FCFF_t / (1 + WACC)^t  +  TV / (1 + WACC)^T

    Parameters
    ----------
    fcff_series : pd.Series
        Projected FCFF for each year (1-indexed or labelled by year).
    wacc : float
        Weighted average cost of capital.
    terminal_value : float
        Terminal value computed at the end of year T.
    terminal_year : int
        Number of years in the explicit forecast (T).

    Returns
    -------
    float
        Present value of enterprise = PV(explicit FCFF) + PV(TV).
    """
    # TODO: Implement
    raise NotImplementedError("enterprise_value — implementation pending.")


def equity_value_per_share(
    enterprise_value: float,
    net_debt: float,
    shares_outstanding: float,
) -> float:
    """Derive equity value per share from enterprise value.

    Formula
    -------
        Equity Value = EV − Net Debt
        Value per Share = Equity Value / Shares Outstanding

    Parameters
    ----------
    enterprise_value : float
    net_debt : float
        Total debt minus cash and equivalents.
    shares_outstanding : float
        Diluted shares outstanding.

    Returns
    -------
    float
        Intrinsic value per share.
    """
    # TODO: Implement
    raise NotImplementedError("equity_value_per_share — implementation pending.")
