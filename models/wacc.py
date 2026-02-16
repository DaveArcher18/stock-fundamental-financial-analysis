"""
Models — Weighted Average Cost of Capital (WACC)
==================================================
Functions to compute the cost of equity (CAPM), cost of debt,
and blended WACC for use as the discount rate in DCF valuation.

Scaffold — function signatures and docstrings only.
Implementation to follow once assumptions are calibrated.
"""

import pandas as pd
import numpy as np


def cost_of_equity(
    risk_free_rate: float,
    beta: float,
    equity_risk_premium: float,
    country_risk_premium: float = 0.0,
) -> float:
    """Estimate the cost of equity using the Capital Asset Pricing Model (CAPM).

    Formula
    -------
        R_e = R_f + β × ERP + CRP

    where:
        R_f  = risk-free rate (e.g. 10-year government bond yield)
        β    = levered equity beta relative to a broad market index
        ERP  = equity risk premium for the mature market
        CRP  = country risk premium (0 for Netherlands / developed markets)

    Parameters
    ----------
    risk_free_rate : float
        Risk-free rate as a decimal (e.g. 0.035 for 3.5 %).
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
    # TODO: Implement
    raise NotImplementedError("cost_of_equity — implementation pending.")


def cost_of_debt(
    pre_tax_cost: float,
    marginal_tax_rate: float,
) -> float:
    """Compute the after-tax cost of debt.

    Formula
    -------
        R_d(1 - T) = pre-tax cost of debt × (1 − marginal tax rate)

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
    # TODO: Implement
    raise NotImplementedError("cost_of_debt — implementation pending.")


def wacc(
    cost_of_equity: float,
    cost_of_debt: float,
    equity_weight: float,
    debt_weight: float,
) -> float:
    """Compute the Weighted Average Cost of Capital.

    Formula
    -------
        WACC = (E / V) × R_e + (D / V) × R_d(1 - T)

    where V = D + E (total enterprise value), and R_d(1-T) is the
    after-tax cost of debt (already computed by :func:`cost_of_debt`).

    Parameters
    ----------
    cost_of_equity : float
        R_e from CAPM or equivalent model.
    cost_of_debt : float
        After-tax cost of debt.
    equity_weight : float
        E / V — proportion of equity in capital structure at market values.
    debt_weight : float
        D / V — proportion of debt in capital structure at market values.
        Must satisfy ``equity_weight + debt_weight ≈ 1.0``.

    Returns
    -------
    float
        WACC as a decimal.
    """
    # TODO: Implement
    raise NotImplementedError("wacc — implementation pending.")


def compute_wacc_from_config(config: dict) -> float:
    """Convenience wrapper: compute WACC directly from a config dictionary.

    Reads keys from ``config["cost_of_capital"]`` and ``config["tax"]``
    as defined in ``config/assumptions.yaml``.

    Parameters
    ----------
    config : dict
        Parsed assumptions.yaml configuration.

    Returns
    -------
    float
        WACC as a decimal.
    """
    # TODO: Implement — wire up config keys to the three functions above
    raise NotImplementedError("compute_wacc_from_config — implementation pending.")
