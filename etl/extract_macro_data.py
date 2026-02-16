"""
ETL — Extract Macro Data
=========================
Scaffold for retrieving macroeconomic data (risk-free rates, inflation,
GDP growth) from public sources such as FRED (Federal Reserve Economic Data).

This module provides the *interface* and placeholder implementations.
Full FRED integration requires a free API key from https://fred.stlouisfed.org/docs/api/api_key.html
"""

from typing import Optional

import pandas as pd


# ---------------------------------------------------------------------------
# FRED series IDs for reference
# ---------------------------------------------------------------------------
FRED_SERIES = {
    "us_10y_treasury": "DGS10",        # 10-Year Treasury Constant Maturity Rate
    "us_3m_tbill": "DTB3",             # 3-Month Treasury Bill Rate
    "us_cpi": "CPIAUCSL",              # Consumer Price Index for All Urban Consumers
    "eur_10y_bund": "IRLTLT01DEM156N", # Long-term interest rate, Germany
    "us_gdp_growth": "A191RL1Q225SBEA",# Real GDP growth (quarterly, annualised)
}


def fetch_fred_series(
    series_id: str,
    api_key: Optional[str] = None,
    start_date: str = "2000-01-01",
    end_date: Optional[str] = None,
) -> pd.Series:
    """Fetch a single time-series from the FRED API.

    Parameters
    ----------
    series_id : str
        FRED series identifier (e.g. ``"DGS10"``).
    api_key : str | None
        FRED API key.  When ``None``, raises ``NotImplementedError``
        as a scaffold reminder.
    start_date : str
        ISO-format start date.
    end_date : str | None
        ISO-format end date.  Defaults to today.

    Returns
    -------
    pd.Series
        Time-series indexed by date.

    Raises
    ------
    NotImplementedError
        If no API key is provided (scaffold mode).
    """
    if api_key is None:
        raise NotImplementedError(
            "FRED integration requires an API key. "
            "Obtain one free at https://fred.stlouisfed.org/docs/api/api_key.html "
            "and pass it via the `api_key` parameter or store it in "
            "config/assumptions.yaml under `macro.fred_api_key`."
        )

    # ------------------------------------------------------------------
    # TODO: Implement actual FRED API call
    #
    #   import requests
    #   url = (
    #       f"https://api.stlouisfed.org/fred/series/observations"
    #       f"?series_id={series_id}"
    #       f"&api_key={api_key}"
    #       f"&file_type=json"
    #       f"&observation_start={start_date}"
    #   )
    #   if end_date:
    #       url += f"&observation_end={end_date}"
    #   response = requests.get(url)
    #   response.raise_for_status()
    #   data = response.json()["observations"]
    #   series = pd.Series(
    #       {obs["date"]: float(obs["value"]) for obs in data if obs["value"] != "."},
    #       name=series_id,
    #   )
    #   series.index = pd.to_datetime(series.index)
    #   return series
    # ------------------------------------------------------------------
    raise NotImplementedError("FRED fetch not yet implemented.")


def get_risk_free_rate(
    api_key: Optional[str] = None,
    series_id: str = "DGS10",
    as_of: Optional[str] = None,
) -> float:
    """Return the most recent risk-free rate observation.

    Parameters
    ----------
    api_key : str | None
        FRED API key.
    series_id : str
        FRED series for the risk-free proxy.
    as_of : str | None
        If provided, return the rate as of this date rather than the latest.

    Returns
    -------
    float
        Risk-free rate as a decimal (e.g. 0.035 for 3.5 %).

    Raises
    ------
    NotImplementedError
        When running in scaffold mode (no API key).
    """
    series = fetch_fred_series(series_id=series_id, api_key=api_key)

    if as_of is not None:
        series = series.loc[:as_of]

    latest_value = series.iloc[-1]

    # FRED reports rates in percentage points; convert to decimal
    return float(latest_value) / 100.0


def get_inflation_rate(
    api_key: Optional[str] = None,
    series_id: str = "CPIAUCSL",
    lookback_months: int = 12,
) -> float:
    """Compute trailing year-over-year CPI inflation.

    Parameters
    ----------
    api_key : str | None
        FRED API key.
    series_id : str
        FRED CPI series identifier.
    lookback_months : int
        Number of months for the trailing calculation.

    Returns
    -------
    float
        YoY inflation rate as a decimal.

    Raises
    ------
    NotImplementedError
        When running in scaffold mode.
    """
    series = fetch_fred_series(series_id=series_id, api_key=api_key)
    latest = series.iloc[-1]
    lagged = series.iloc[-1 - lookback_months]
    return float((latest - lagged) / lagged)


if __name__ == "__main__":
    print("[extract_macro_data] Running in scaffold mode — no API key provided.")
    print(f"  Available FRED series references: {list(FRED_SERIES.keys())}")
    print("  Set a FRED API key to enable live data retrieval.")
