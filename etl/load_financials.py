"""
ETL — Load Financial Statements
================================
Structured loader for manually entered CSV financial statements.

Expects three CSVs in a source directory:
    • income_statement.csv
    • balance_sheet.csv
    • cash_flow.csv

Validates structure, performs light normalisation, and stores cleaned
versions in data/interim/.

This loader is company-agnostic — no ASML-specific transformations.
"""

import os
from pathlib import Path
from typing import Optional

import pandas as pd


# ---------------------------------------------------------------------------
# Expected column schemas (minimal required columns)
# ---------------------------------------------------------------------------
INCOME_STATEMENT_COLUMNS = [
    "date",
    "revenue",
    "cost_of_revenue",
    "gross_profit",
    "rd_expense",
    "sga_expense",
    "operating_income",
    "interest_expense",
    "pretax_income",
    "income_tax",
    "net_income",
]

BALANCE_SHEET_COLUMNS = [
    "date",
    "cash",
    "accounts_receivable",
    "inventory",
    "total_current_assets",
    "ppe_net",
    "total_assets",
    "accounts_payable",
    "short_term_debt",
    "total_current_liabilities",
    "long_term_debt",
    "total_liabilities",
    "total_equity",
]

CASH_FLOW_COLUMNS = [
    "date",
    "net_income",
    "depreciation",
    "change_in_working_capital",
    "operating_cash_flow",
    "capex",
    "investing_cash_flow",
    "financing_cash_flow",
    "free_cash_flow",
]

STATEMENT_SCHEMAS: dict[str, list[str]] = {
    "income_statement": INCOME_STATEMENT_COLUMNS,
    "balance_sheet": BALANCE_SHEET_COLUMNS,
    "cash_flow": CASH_FLOW_COLUMNS,
}


def _validate_columns(
    df: pd.DataFrame,
    expected: list[str],
    statement_name: str,
) -> None:
    """Raise ``ValueError`` if *expected* columns are missing from *df*."""
    missing = set(expected) - set(df.columns)
    if missing:
        raise ValueError(
            f"[load_financials] {statement_name} is missing columns: "
            f"{sorted(missing)}.  Found: {sorted(df.columns)}"
        )


def _normalise_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Lowercase, strip whitespace, and replace spaces/hyphens with underscores."""
    df.columns = (
        df.columns
        .str.strip()
        .str.lower()
        .str.replace(r"[\s\-]+", "_", regex=True)
    )
    return df


def load_single_statement(
    filepath: str,
    expected_columns: list[str],
    statement_name: str,
) -> pd.DataFrame:
    """Load and lightly validate a single financial-statement CSV.

    Parameters
    ----------
    filepath : str
        Path to the CSV file.
    expected_columns : list[str]
        Column names that must be present after normalisation.
    statement_name : str
        Human-readable label used in error messages.

    Returns
    -------
    pd.DataFrame
        DataFrame with normalised column names and a parsed ``date`` column.
    """
    if not os.path.isfile(filepath):
        raise FileNotFoundError(
            f"[load_financials] File not found: {filepath}"
        )

    df = pd.read_csv(filepath)
    df = _normalise_columns(df)
    _validate_columns(df, expected_columns, statement_name)

    # Parse date column
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.sort_values("date").reset_index(drop=True)

    return df


def load_all_statements(
    source_dir: str = "data/raw",
    output_dir: str = "data/interim",
) -> dict[str, pd.DataFrame]:
    """Load all three financial statements from *source_dir*.

    Parameters
    ----------
    source_dir : str
        Directory containing the raw CSVs.
    output_dir : str
        Directory where cleaned CSVs are written.

    Returns
    -------
    dict[str, pd.DataFrame]
        Keys: ``"income_statement"``, ``"balance_sheet"``, ``"cash_flow"``.

    Raises
    ------
    FileNotFoundError
        If any expected CSV is missing from *source_dir*.
    ValueError
        If required columns are absent after normalisation.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    results: dict[str, pd.DataFrame] = {}

    for statement_name, expected_cols in STATEMENT_SCHEMAS.items():
        filename = f"{statement_name}.csv"
        filepath = os.path.join(source_dir, filename)

        print(f"[load_financials] Loading {statement_name} from {filepath} …")
        df = load_single_statement(filepath, expected_cols, statement_name)

        # Save cleaned version to interim
        out_path = os.path.join(output_dir, filename)
        df.to_csv(out_path, index=False)
        print(f"[load_financials] Saved cleaned {statement_name} → {out_path} "
              f"({len(df)} rows)")

        results[statement_name] = df

    return results


def check_financials_exist(source_dir: str = "data/raw") -> bool:
    """Return ``True`` if all three expected CSVs exist in *source_dir*.

    Parameters
    ----------
    source_dir : str
        Directory to check.

    Returns
    -------
    bool
    """
    for statement_name in STATEMENT_SCHEMAS:
        filepath = os.path.join(source_dir, f"{statement_name}.csv")
        if not os.path.isfile(filepath):
            return False
    return True


if __name__ == "__main__":
    if check_financials_exist():
        statements = load_all_statements()
        for name, df in statements.items():
            print(f"\n{name}: {df.shape}")
            print(df.head())
    else:
        print("[load_financials] No financial statement CSVs found in data/raw/.")
        print("  Place income_statement.csv, balance_sheet.csv, and cash_flow.csv there first.")
