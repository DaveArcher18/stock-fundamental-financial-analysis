"""
Processing — Clean Financial Data
===================================
Standardise column names, coerce string values to numeric, and handle
missing values safely for downstream ratio computation and modelling.

All functions are pure (no side effects) and company-agnostic.
"""

from typing import Optional

import numpy as np
import pandas as pd


def standardise_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise column names to snake_case.

    Parameters
    ----------
    df : pd.DataFrame
        Raw or partially cleaned DataFrame.

    Returns
    -------
    pd.DataFrame
        DataFrame with lowercased, underscore-separated column names.
    """
    df = df.copy()
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(r"[\s\-]+", "_", regex=True)
        .str.replace(r"[^\w]", "", regex=True)
    )
    return df


def coerce_to_numeric(
    df: pd.DataFrame,
    exclude_columns: Optional[list[str]] = None,
) -> pd.DataFrame:
    """Convert all non-excluded columns to numeric, coercing errors to NaN.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame with potentially string-typed numeric columns.
    exclude_columns : list[str] | None
        Columns to skip (e.g. ``["date"]``).

    Returns
    -------
    pd.DataFrame
        DataFrame with numeric columns where possible.
    """
    df = df.copy()
    if exclude_columns is None:
        exclude_columns = []

    for col in df.columns:
        if col in exclude_columns:
            continue
        # Strip currency symbols, commas, whitespace before conversion
        if df[col].dtype == object:
            df[col] = (
                df[col]
                .astype(str)
                .str.replace(r"[€$£,\s]", "", regex=True)
                .str.replace(r"^\-$", "", regex=True)  # bare hyphens → empty
            )
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def handle_missing_values(
    df: pd.DataFrame,
    strategy: str = "preserve",
    fill_value: float = 0.0,
) -> pd.DataFrame:
    """Handle NaN / missing values according to a chosen strategy.

    Parameters
    ----------
    df : pd.DataFrame
        DataFrame potentially containing NaN values.
    strategy : str
        One of:
        - ``"preserve"`` — leave NaN as-is (default; safest for financial data).
        - ``"zero"`` — fill NaN with 0.
        - ``"forward"`` — forward-fill.
        - ``"interpolate"`` — linear interpolation.
        - ``"fill"`` — fill with *fill_value*.
    fill_value : float
        Value used when ``strategy="fill"``.

    Returns
    -------
    pd.DataFrame

    Raises
    ------
    ValueError
        If *strategy* is not recognised.
    """
    df = df.copy()

    if strategy == "preserve":
        return df
    elif strategy == "zero":
        return df.fillna(0.0)
    elif strategy == "forward":
        return df.ffill()
    elif strategy == "interpolate":
        return df.interpolate(method="linear", limit_direction="forward")
    elif strategy == "fill":
        return df.fillna(fill_value)
    else:
        raise ValueError(
            f"Unknown missing-value strategy '{strategy}'. "
            f"Choose from: preserve, zero, forward, interpolate, fill."
        )


def ensure_date_index(
    df: pd.DataFrame,
    date_column: str = "date",
) -> pd.DataFrame:
    """Parse date column and set as index, sorted ascending.

    Parameters
    ----------
    df : pd.DataFrame
    date_column : str
        Name of the column containing dates.

    Returns
    -------
    pd.DataFrame
        Date-indexed DataFrame sorted chronologically.
    """
    df = df.copy()
    if date_column in df.columns:
        df[date_column] = pd.to_datetime(df[date_column], errors="coerce")
        df = df.set_index(date_column).sort_index()
    return df


def clean_financial_data(
    df: pd.DataFrame,
    date_column: str = "date",
    missing_strategy: str = "preserve",
) -> pd.DataFrame:
    """Full cleaning pipeline: standardise → coerce → handle missing → index.

    Parameters
    ----------
    df : pd.DataFrame
        Raw financial statement DataFrame.
    date_column : str
        Name of the date column.
    missing_strategy : str
        Strategy for missing values (see :func:`handle_missing_values`).

    Returns
    -------
    pd.DataFrame
        Fully cleaned, date-indexed DataFrame.
    """
    df = standardise_column_names(df)
    df = coerce_to_numeric(df, exclude_columns=[date_column])
    df = handle_missing_values(df, strategy=missing_strategy)
    df = ensure_date_index(df, date_column=date_column)
    return df
