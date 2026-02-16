"""
ETL — Extract Market Data
==========================
Pulls full historical price data for a given ticker using yfinance.
Saves raw CSV to data/raw/ with adjusted close, volume, shares outstanding,
and market capitalisation where available.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
import yfinance as yf


def extract_price_history(
    ticker: str,
    start_date: str = "2000-01-01",
    end_date: Optional[str] = None,
    output_dir: str = "data/raw",
) -> pd.DataFrame:
    """Download full historical OHLCV data for *ticker* via yfinance.

    Parameters
    ----------
    ticker : str
        Yahoo Finance ticker symbol (e.g. ``"ASML"``).
    start_date : str
        ISO-format start date for the history window.
    end_date : str | None
        ISO-format end date.  Defaults to today.
    output_dir : str
        Directory where the raw CSV will be saved.

    Returns
    -------
    pd.DataFrame
        DataFrame indexed by date with columns:
        Open, High, Low, Close, Adj Close, Volume.
    """
    if end_date is None:
        end_date = datetime.today().strftime("%Y-%m-%d")

    print(f"[extract_market_data] Downloading {ticker} price history "
          f"({start_date} → {end_date}) …")

    stock = yf.Ticker(ticker)
    hist: pd.DataFrame = stock.history(start=start_date, end=end_date, auto_adjust=False)

    if hist.empty:
        raise ValueError(f"No price data returned for ticker '{ticker}'.")

    # Ensure output directory exists
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    filename = f"{ticker.lower()}_price_history.csv"
    filepath = os.path.join(output_dir, filename)
    hist.to_csv(filepath)
    print(f"[extract_market_data] Saved {len(hist)} rows → {filepath}")

    return hist


def extract_company_info(
    ticker: str,
    output_dir: str = "data/raw",
) -> dict:
    """Retrieve supplementary company-level data from yfinance.

    Extracts shares outstanding and market capitalisation when the
    upstream API makes them available.  Results are saved as a small
    JSON-like CSV for auditability.

    Parameters
    ----------
    ticker : str
        Yahoo Finance ticker symbol.
    output_dir : str
        Directory where the summary CSV will be saved.

    Returns
    -------
    dict
        Dictionary with keys such as ``shares_outstanding``,
        ``market_cap``, ``currency``, ``sector``.
    """
    print(f"[extract_market_data] Fetching company info for {ticker} …")

    stock = yf.Ticker(ticker)
    info: dict = stock.info

    fields_of_interest = {
        "shortName": info.get("shortName"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "currency": info.get("currency"),
        "shares_outstanding": info.get("sharesOutstanding"),
        "market_cap": info.get("marketCap"),
        "enterprise_value": info.get("enterpriseValue"),
        "trailing_pe": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "dividend_yield": info.get("dividendYield"),
        "beta": info.get("beta"),
    }

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    filepath = os.path.join(output_dir, f"{ticker.lower()}_company_info.csv")

    summary_df = pd.DataFrame(
        list(fields_of_interest.items()),
        columns=["field", "value"],
    )
    summary_df.to_csv(filepath, index=False)
    print(f"[extract_market_data] Saved company info → {filepath}")

    return fields_of_interest


def run_market_extraction(
    ticker: str = "ASML",
    start_date: str = "2000-01-01",
    output_dir: str = "data/raw",
) -> tuple[pd.DataFrame, dict]:
    """Convenience wrapper: extract prices + company info in one call.

    Parameters
    ----------
    ticker : str
        Yahoo Finance ticker symbol.
    start_date : str
        ISO-format start date.
    output_dir : str
        Directory for raw output files.

    Returns
    -------
    tuple[pd.DataFrame, dict]
        (price_history_df, company_info_dict)
    """
    prices = extract_price_history(
        ticker=ticker, start_date=start_date, output_dir=output_dir
    )
    info = extract_company_info(ticker=ticker, output_dir=output_dir)
    return prices, info


if __name__ == "__main__":
    run_market_extraction()
