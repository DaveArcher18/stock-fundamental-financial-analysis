"""
ASML Corporate Valuation Framework — Main Entry Point
=======================================================
Orchestrates the ETL → Processing → Insights pipeline.

Usage:
    python main.py

Steps:
    1. Load configuration from config/assumptions.yaml
    2. Extract market data (historical prices, company info)
    3. Load and clean financial statements (if CSVs exist)
    4. Compute ratios and ROIC (if financials are available)
    5. Print summary statistics
"""

import os
import sys
from pathlib import Path

import yaml
import pandas as pd

# Ensure the project root is on the path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from etl.extract_market_data import run_market_extraction
from etl.load_financials import load_all_statements, check_financials_exist
from processing.clean_financials import clean_financial_data
from processing.compute_ratios import compute_all_ratios
from processing.roic import compute_roic_table
from processing.working_capital import compute_working_capital_table
from insights.historical_analysis import (
    print_summary_statistics,
    print_ratio_summary,
    plot_price_history,
)


def load_config(config_path: str = "config/assumptions.yaml") -> dict:
    """Load the central assumptions configuration.

    Parameters
    ----------
    config_path : str
        Path to the YAML configuration file.

    Returns
    -------
    dict
        Parsed configuration dictionary.
    """
    full_path = PROJECT_ROOT / config_path
    with open(full_path, "r") as f:
        config = yaml.safe_load(f)
    print(f"[main] Loaded configuration from {full_path}")
    return config


def main() -> None:
    """Run the full ETL → Processing → Summary pipeline."""

    print("\n" + "═" * 60)
    print("  ASML CORPORATE VALUATION FRAMEWORK")
    print("═" * 60 + "\n")

    # ── 1. Load Configuration ─────────────────────────────────────────
    config = load_config()
    ticker: str = config["company"]["ticker"]
    start_date: str = config["market_data"]["price_start_date"]
    tax_rate: float = config["tax"]["effective_rate"]

    # Set up directory paths relative to project root
    raw_dir = str(PROJECT_ROOT / "data" / "raw")
    interim_dir = str(PROJECT_ROOT / "data" / "interim")
    processed_dir = str(PROJECT_ROOT / "data" / "processed")

    # ── 2. Market Data Extraction ─────────────────────────────────────
    print("\n── Step 1: Market Data Extraction ──\n")
    try:
        prices, company_info = run_market_extraction(
            ticker=ticker,
            start_date=start_date,
            output_dir=raw_dir,
        )
        print_summary_statistics(prices, company_info)
        plot_price_history(prices, ticker=ticker, output_dir=processed_dir)
    except Exception as e:
        print(f"[main] ⚠ Market data extraction failed: {e}")
        prices = pd.DataFrame()
        company_info = {}

    # ── 3. Financial Statement Loading ────────────────────────────────
    print("\n── Step 2: Financial Statement Loading ──\n")

    if check_financials_exist(source_dir=raw_dir):
        try:
            statements = load_all_statements(
                source_dir=raw_dir,
                output_dir=interim_dir,
            )
            income_stmt = clean_financial_data(statements["income_statement"])
            balance_sheet = clean_financial_data(statements["balance_sheet"])
            cash_flow = clean_financial_data(statements["cash_flow"])
            print("[main] ✓ Financial statements loaded and cleaned.")

        except Exception as e:
            print(f"[main] ⚠ Financial loading failed: {e}")
            income_stmt = balance_sheet = cash_flow = None
    else:
        print("[main] No financial statement CSVs found in data/raw/.")
        print("       Place income_statement.csv, balance_sheet.csv, and "
              "cash_flow.csv there to enable processing.")
        income_stmt = balance_sheet = cash_flow = None

    # ── 4. Ratio and ROIC Computation ─────────────────────────────────
    if income_stmt is not None:
        print("\n── Step 3: Financial Analysis ──\n")
        try:
            # Compute ratios
            ratios = compute_all_ratios(income_stmt, cash_flow)
            print_ratio_summary(ratios)

            # Save ratios
            ratios_path = os.path.join(processed_dir, "financial_ratios.csv")
            Path(processed_dir).mkdir(parents=True, exist_ok=True)
            ratios.to_csv(ratios_path)
            print(f"[main] Saved financial ratios → {ratios_path}")

            # Compute ROIC
            roic_table = compute_roic_table(income_stmt, balance_sheet, tax_rate=tax_rate)
            roic_path = os.path.join(processed_dir, "roic_analysis.csv")
            roic_table.to_csv(roic_path)
            print(f"[main] Saved ROIC analysis → {roic_path}")

            # Compute working capital
            wc_table = compute_working_capital_table(balance_sheet, income_stmt)
            wc_path = os.path.join(processed_dir, "working_capital.csv")
            wc_table.to_csv(wc_path)
            print(f"[main] Saved working capital analysis → {wc_path}")

        except Exception as e:
            print(f"[main] ⚠ Analysis failed: {e}")
    else:
        print("\n[main] Skipping financial analysis — no statements available yet.")

    # ── Done ──────────────────────────────────────────────────────────
    print("\n" + "═" * 60)
    print("  Pipeline complete.")
    print("  Next steps:")
    print("    • Add financial statement CSVs to data/raw/")
    print("    • Implement model functions in models/")
    print("    • Run scenario analysis")
    print("═" * 60 + "\n")


if __name__ == "__main__":
    main()
