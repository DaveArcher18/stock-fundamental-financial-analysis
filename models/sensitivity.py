"""
Models — Sensitivity Analysis
================================
Utilities for two-way sensitivity tables that show how enterprise value
(or equity value per share) varies with changes in two key parameters.

Scaffold — function signatures and docstrings only.
"""

import pandas as pd
import numpy as np
from typing import Callable


def two_way_sensitivity(
    valuation_func: Callable[..., float],
    base_params: dict,
    param_x: str,
    param_x_range: list[float],
    param_y: str,
    param_y_range: list[float],
) -> pd.DataFrame:
    """Generate a two-way sensitivity table.

    Methodology
    -----------
    For each combination of (param_x_value, param_y_value), call
    ``valuation_func(**modified_params)`` and record the result.
    The output is a DataFrame with param_x values as the index and
    param_y values as columns.

    Parameters
    ----------
    valuation_func : Callable[..., float]
        A function that takes keyword arguments and returns a single
        numeric output (e.g. enterprise value or equity value per share).
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
        Sensitivity matrix with shape ``(len(param_x_range), len(param_y_range))``.
        Index = param_x values, Columns = param_y values.

    Example
    -------
    >>> table = two_way_sensitivity(
    ...     valuation_func=compute_ev,
    ...     base_params={"wacc": 0.09, "terminal_growth": 0.025, ...},
    ...     param_x="wacc",
    ...     param_x_range=[0.07, 0.08, 0.09, 0.10, 0.11],
    ...     param_y="terminal_growth",
    ...     param_y_range=[0.015, 0.02, 0.025, 0.03, 0.035],
    ... )
    """
    # TODO: Implement
    raise NotImplementedError("two_way_sensitivity — implementation pending.")


def tornado_chart_data(
    valuation_func: Callable[..., float],
    base_params: dict,
    sensitivity_specs: dict[str, tuple[float, float]],
) -> pd.DataFrame:
    """Generate data for a tornado (single-parameter) sensitivity chart.

    Parameters
    ----------
    valuation_func : Callable[..., float]
        Function that returns a valuation output.
    base_params : dict
        Baseline parameter dictionary.
    sensitivity_specs : dict[str, tuple[float, float]]
        Mapping of ``{parameter_name: (low_value, high_value)}``.
        One parameter is varied at a time; all others stay at base.

    Returns
    -------
    pd.DataFrame
        Columns: ``parameter``, ``low_value``, ``high_value``,
        ``low_result``, ``high_result``, ``base_result``, ``swing``.
        Sorted by absolute swing descending (most sensitive first).
    """
    # TODO: Implement
    raise NotImplementedError("tornado_chart_data — implementation pending.")
