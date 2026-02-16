"""
ETL — Extract SEC EDGAR XBRL Financial Data
=============================================
Programmatically retrieves structured financial statement data from the
SEC Company Facts API (XBRL) for any company by CIK.

Data source:
    https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json

This module:
    1. Fetches the full Company Facts JSON from SEC EDGAR
    2. Extracts XBRL-tagged financial concepts (US GAAP taxonomy)
    3. Filters to annual filings (20-F / 10-K), deduplicates by fiscal year
    4. Returns a clean DataFrame with standardised column names
    5. Saves raw JSON and processed CSV

Reusable for any SEC filer — pass a different CIK and concept map.

SEC API rules:
    - User-Agent header required (name + email)
    - Rate limit: max 10 requests/second
    - Retry with exponential backoff on transient failures
"""

import json
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import requests


# ═══════════════════════════════════════════════════════════════════════════
# Default US GAAP concept mapping
# ═══════════════════════════════════════════════════════════════════════════
# Maps XBRL concept tags → standardised column names.
# Multiple tags can map to the same column; the extractor tries them in
# the order listed and uses the first that has data for a given fiscal year.
# ═══════════════════════════════════════════════════════════════════════════

DEFAULT_CONCEPT_MAP: dict[str, str] = {
    # ── Income Statement ──────────────────────────────────────────────
    "RevenueFromContractWithCustomerExcludingAssessedTax": "revenue",
    "Revenues": "revenue",
    "SalesRevenueNet": "revenue",
    "CostOfGoodsAndServicesSold": "cost_of_revenue",
    "CostOfRevenue": "cost_of_revenue",
    "GrossProfit": "gross_profit",
    "ResearchAndDevelopmentExpense": "rd_expense",
    "SellingGeneralAndAdministrativeExpense": "sga_expense",
    "OperatingIncomeLoss": "operating_income",
    "NetIncomeLoss": "net_income",
    "InterestExpense": "interest_expense",
    "InterestExpenseDebt": "interest_expense",
    "InterestExpenseNonoperating": "interest_expense",
    "IncomeTaxExpenseBenefit": "income_tax_expense",
    # ── Balance Sheet ─────────────────────────────────────────────────
    "Assets": "total_assets",
    "AssetsCurrent": "total_current_assets",
    "Liabilities": "total_liabilities",
    "LiabilitiesCurrent": "total_current_liabilities",
    "StockholdersEquity": "total_equity",
    "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest": "total_equity",
    "CashAndCashEquivalentsAtCarryingValue": "cash",
    "CashCashEquivalentsAndShortTermInvestments": "cash",
    "ShortTermBorrowings": "short_term_debt",
    "ShortTermDebtWeightedAverageInterestRateOverTime": "short_term_debt",
    "CurrentPortionOfLongTermDebt": "current_portion_long_term_debt",
    "LongTermDebtCurrent": "current_portion_long_term_debt",
    "LongTermDebtNoncurrent": "long_term_debt",
    "LongTermDebt": "long_term_debt",
    "DebtCurrent": "debt_current",
    "DebtLongTermAndShortTermCombinedAmount": "total_debt",
    "AccountsReceivableNetCurrent": "accounts_receivable",
    "AccountsReceivableNet": "accounts_receivable",
    "InventoryNet": "inventory",
    "AccountsPayableCurrent": "accounts_payable",
    "AccountsPayableAndAccruedLiabilitiesCurrent": "accounts_payable",
    "ContractWithCustomerLiabilityCurrent": "contract_liabilities",
    "ContractWithCustomerLiability": "contract_liabilities",
    # ── Cash Flow Statement ───────────────────────────────────────────
    "NetCashProvidedByUsedInOperatingActivities": "operating_cash_flow",
    "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations": "operating_cash_flow",
    "PaymentsToAcquirePropertyPlantAndEquipment": "capex",
    "DepreciationDepletionAndAmortization": "depreciation",
    "Depreciation": "depreciation",
    "DepreciationAndAmortization": "depreciation",
    "PaymentsOfDividendsCommonStock": "dividends_paid",
    "PaymentsOfDividends": "dividends_paid",
    "PaymentsOfOrdinaryDividends": "dividends_paid",
    "DividendsCommonStockCash": "dividends_paid",
    "PaymentsForRepurchaseOfCommonStock": "share_buybacks",
    # ── Shares ────────────────────────────────────────────────────────
    "CommonStockSharesOutstanding": "shares_outstanding",
    "WeightedAverageNumberOfShareOutstandingBasicAndDiluted": "shares_outstanding_diluted",
    "WeightedAverageNumberOfSharesOutstandingBasic": "shares_outstanding_basic",
    "EntityCommonStockSharesOutstanding": "shares_outstanding",
}

# Which SEC form types count as "annual" filings
ANNUAL_FORMS: set[str] = {"20-F", "20-F/A", "10-K", "10-K/A"}


# ═══════════════════════════════════════════════════════════════════════════
# Core Functions
# ═══════════════════════════════════════════════════════════════════════════


def fetch_company_facts(
    cik: str,
    user_agent: str = "ASMLValuation research@example.com",
    base_url: str = "https://data.sec.gov/api/xbrl/companyfacts",
    max_retries: int = 3,
    backoff_factor: float = 2.0,
) -> dict:
    """Fetch the full Company Facts JSON from SEC EDGAR.

    Parameters
    ----------
    cik : str
        SEC Central Index Key, zero-padded to 10 digits
        (e.g. ``"0000937966"``).
    user_agent : str
        Required by SEC — must include a name and contact email.
    base_url : str
        SEC Company Facts API base URL.
    max_retries : int
        Number of retry attempts on transient HTTP errors.
    backoff_factor : float
        Exponential backoff multiplier between retries.

    Returns
    -------
    dict
        Parsed JSON response containing all XBRL facts for the company.

    Raises
    ------
    requests.HTTPError
        If the request fails after all retries.
    """
    # Ensure CIK is zero-padded to 10 digits
    cik_padded = cik.lstrip("0").zfill(10)
    url = f"{base_url}/CIK{cik_padded}.json"

    headers = {
        "User-Agent": user_agent,
        "Accept": "application/json",
    }

    for attempt in range(1, max_retries + 1):
        try:
            print(f"[extract_sec_xbrl] Fetching {url}  (attempt {attempt}/{max_retries})")
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            print(f"[extract_sec_xbrl] ✓ Received {len(json.dumps(data)) / 1e6:.1f} MB of data")
            return data

        except requests.exceptions.HTTPError as e:
            if response.status_code == 429 or response.status_code >= 500:
                wait = backoff_factor ** attempt
                print(f"[extract_sec_xbrl] ⚠ HTTP {response.status_code} — "
                      f"retrying in {wait:.0f}s …")
                time.sleep(wait)
            else:
                raise
        except requests.exceptions.RequestException as e:
            wait = backoff_factor ** attempt
            print(f"[extract_sec_xbrl] ⚠ Request error: {e} — "
                  f"retrying in {wait:.0f}s …")
            time.sleep(wait)

    # Final attempt — let it raise
    response = requests.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()


def extract_financial_concepts(
    data: dict,
    concept_map: Optional[dict[str, str]] = None,
    annual_forms: Optional[set[str]] = None,
    years_to_keep: int = 10,
    taxonomy: str = "us-gaap",
) -> pd.DataFrame:
    """Extract and consolidate financial concepts from Company Facts JSON.

    Parameters
    ----------
    data : dict
        Raw Company Facts JSON from :func:`fetch_company_facts`.
    concept_map : dict[str, str] | None
        Mapping of ``{XBRL_tag: standardised_column_name}``.
        Defaults to :data:`DEFAULT_CONCEPT_MAP`.
    annual_forms : set[str] | None
        Set of form types considered "annual".
        Defaults to :data:`ANNUAL_FORMS`.
    years_to_keep : int
        Number of most recent fiscal years to retain.
    taxonomy : str
        XBRL taxonomy namespace (``"us-gaap"`` or ``"ifrs-full"``).

    Returns
    -------
    pd.DataFrame
        Tidy DataFrame indexed by ``fiscal_year`` with one column per
        standardised financial concept.
    """
    if concept_map is None:
        concept_map = DEFAULT_CONCEPT_MAP
    if annual_forms is None:
        annual_forms = ANNUAL_FORMS

    facts = data.get("facts", {}).get(taxonomy, {})

    # Group XBRL tags by standardised column name, preserving priority order
    # (first tag listed in the map has highest priority)
    tag_groups: dict[str, list[str]] = defaultdict(list)
    for xbrl_tag, std_name in concept_map.items():
        tag_groups[std_name].append(xbrl_tag)

    # Extract annual values for each standardised concept
    concept_series: dict[str, pd.Series] = {}

    for std_name, xbrl_tags in tag_groups.items():
        # Try tags in priority order; merge results
        merged = _extract_concept_annual_values(
            facts=facts,
            xbrl_tags=xbrl_tags,
            annual_forms=annual_forms,
        )
        if not merged.empty:
            concept_series[std_name] = merged

    if not concept_series:
        print("[extract_sec_xbrl] ⚠ No concepts extracted — check taxonomy/tag names.")
        return pd.DataFrame()

    # Combine into a single DataFrame
    df = pd.DataFrame(concept_series)
    df.index.name = "fiscal_year_end"
    df = df.sort_index()

    # ── Clean up sparse artifact rows ─────────────────────────────────
    # Some XBRL entries are point-in-time snapshots (e.g. start-of-year
    # balance sheet) that produce rows with only 1–2 populated fields.
    # Drop rows where > 75% of data columns are NaN.
    data_cols = list(df.columns)
    threshold = len(data_cols) * 0.25  # must have at least 25% non-null
    df = df.dropna(thresh=int(threshold))

    # Derive fiscal_year as the calendar year of the period end date
    df["fiscal_year"] = df.index.year

    # ── Deduplicate fiscal years ──────────────────────────────────────
    # If multiple rows share the same fiscal_year (e.g. 2018-01-01 and
    # 2018-12-31), keep the row with the most non-null values.
    if df["fiscal_year"].duplicated().any():
        df["_completeness"] = df[data_cols].notna().sum(axis=1)
        df = df.sort_values(["fiscal_year", "_completeness"], ascending=[True, False])
        df = df.drop_duplicates(subset=["fiscal_year"], keep="first")
        df = df.drop(columns=["_completeness"])
        df = df.sort_index()

    # Keep only the latest N years
    if years_to_keep and len(df) > years_to_keep:
        df = df.iloc[-years_to_keep:]

    # Reorder: fiscal_year first, then alphabetical
    cols = ["fiscal_year"] + sorted([c for c in df.columns if c != "fiscal_year"])
    df = df[cols]

    return df


def _extract_concept_annual_values(
    facts: dict,
    xbrl_tags: list[str],
    annual_forms: set[str],
) -> pd.Series:
    """Extract annual values for a single concept, trying multiple tags.

    For each fiscal year end date, the value from the highest-priority tag
    (earliest in *xbrl_tags*) is used.  If a tag has no data for a year,
    the next tag is tried.

    Parameters
    ----------
    facts : dict
        The ``facts > {taxonomy}`` sub-dict from company facts JSON.
    xbrl_tags : list[str]
        XBRL tag names to try, in priority order.
    annual_forms : set[str]
        Form types that count as "annual".

    Returns
    -------
    pd.Series
        Series indexed by fiscal year end date (as ``pd.Timestamp``).
    """
    all_values: dict[pd.Timestamp, float] = {}

    for tag in xbrl_tags:
        concept_data = facts.get(tag, {})
        units_data = concept_data.get("units", {})

        for unit_key, entries in units_data.items():
            for entry in entries:
                form = entry.get("form", "")
                if form not in annual_forms:
                    continue

                end_date_str = entry.get("end")
                if not end_date_str:
                    continue

                try:
                    end_date = pd.Timestamp(end_date_str)
                except (ValueError, TypeError):
                    continue

                val = entry.get("val")
                if val is None:
                    continue

                # Only set if we don't already have a value for this date
                # (preserves priority: first tag wins)
                if end_date not in all_values:
                    all_values[end_date] = float(val)

    if not all_values:
        return pd.Series(dtype=float)

    series = pd.Series(all_values).sort_index()

    # Deduplicate: if multiple entries for same fiscal year, keep latest end date
    series = series[~series.index.duplicated(keep="last")]

    return series


# ═══════════════════════════════════════════════════════════════════════════
# Persistence
# ═══════════════════════════════════════════════════════════════════════════


def save_raw_json(
    data: dict,
    output_dir: str = "data/raw/xbrl",
    filename: str = "company_facts.json",
) -> str:
    """Save the raw Company Facts JSON for auditability.

    Parameters
    ----------
    data : dict
        Full JSON response from SEC EDGAR.
    output_dir : str
        Target directory.
    filename : str
        Output filename.

    Returns
    -------
    str
        Absolute path to the saved file.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    filepath = os.path.join(output_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    size_mb = os.path.getsize(filepath) / 1e6
    print(f"[extract_sec_xbrl] Saved raw JSON → {filepath}  ({size_mb:.1f} MB)")
    return filepath


def save_processed_financials(
    df: pd.DataFrame,
    output_dir: str = "data/processed",
    filename: str = "financials_annual.csv",
) -> str:
    """Export the processed financials DataFrame as CSV.

    Parameters
    ----------
    df : pd.DataFrame
        Cleaned annual financials.
    output_dir : str
        Target directory.
    filename : str
        Output filename.

    Returns
    -------
    str
        Absolute path to the saved file.
    """
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    filepath = os.path.join(output_dir, filename)
    df.to_csv(filepath, index=True)
    print(f"[extract_sec_xbrl] Saved processed financials → {filepath}  "
          f"({len(df)} rows × {len(df.columns)} cols)")
    return filepath


# ═══════════════════════════════════════════════════════════════════════════
# Diagnostics
# ═══════════════════════════════════════════════════════════════════════════


def print_diagnostics(df: pd.DataFrame) -> None:
    """Print a diagnostic summary of the extracted data.

    Shows:
        - Fiscal years extracted
        - Data points per concept
        - Missing fields per year

    Parameters
    ----------
    df : pd.DataFrame
        Processed financials DataFrame.
    """
    print("\n" + "═" * 65)
    print("  SEC EDGAR XBRL — EXTRACTION DIAGNOSTICS")
    print("═" * 65)

    if df.empty:
        print("  ⚠ No data extracted.")
        print("═" * 65 + "\n")
        return

    # Fiscal years
    years = sorted(df["fiscal_year"].unique()) if "fiscal_year" in df.columns else []
    print(f"\n  Fiscal years extracted:  {len(years)}")
    if years:
        print(f"  Range:                   {years[0]} → {years[-1]}")
        print(f"  Years:                   {', '.join(str(y) for y in years)}")

    # Data points per concept
    data_cols = [c for c in df.columns if c != "fiscal_year"]
    print(f"\n  {'Concept':<30s}  {'Non-null':>8s}  {'Missing':>8s}")
    print(f"  {'─' * 30}  {'─' * 8}  {'─' * 8}")

    for col in sorted(data_cols):
        non_null = df[col].notna().sum()
        missing = df[col].isna().sum()
        marker = "  ⚠" if missing > 0 else ""
        print(f"  {col:<30s}  {non_null:>8d}  {missing:>8d}{marker}")

    # Total
    total_cells = len(df) * len(data_cols)
    total_filled = df[data_cols].notna().sum().sum()
    total_missing = total_cells - total_filled
    completeness = total_filled / total_cells * 100 if total_cells > 0 else 0

    print(f"\n  Total data points:       {total_filled:,} / {total_cells:,}  "
          f"({completeness:.0f}% complete)")

    # Missing fields per year
    print(f"\n  {'Year':<6s}  {'Missing fields'}")
    print(f"  {'─' * 6}  {'─' * 40}")

    for _, row in df.iterrows():
        year = int(row.get("fiscal_year", 0))
        missing_cols = [c for c in data_cols if pd.isna(row.get(c))]
        if missing_cols:
            print(f"  {year:<6d}  {', '.join(missing_cols)}")
        else:
            print(f"  {year:<6d}  (complete)")

    print("═" * 65 + "\n")


# ═══════════════════════════════════════════════════════════════════════════
# Orchestrator
# ═══════════════════════════════════════════════════════════════════════════


def run_sec_extraction(
    cik: str = "0000937966",
    user_agent: str = "ASMLValuation research@example.com",
    concept_map: Optional[dict[str, str]] = None,
    years_to_keep: int = 10,
    raw_output_dir: str = "data/raw/xbrl",
    processed_output_dir: str = "data/processed",
) -> pd.DataFrame:
    """End-to-end SEC XBRL extraction pipeline.

    Parameters
    ----------
    cik : str
        SEC CIK for the target company.
    user_agent : str
        User-Agent string for SEC API compliance.
    concept_map : dict[str, str] | None
        Custom concept mapping.  Defaults to :data:`DEFAULT_CONCEPT_MAP`.
    years_to_keep : int
        Number of most recent fiscal years to retain.
    raw_output_dir : str
        Directory for raw JSON output.
    processed_output_dir : str
        Directory for processed CSV output.

    Returns
    -------
    pd.DataFrame
        Processed annual financials.
    """
    # Step 1: Fetch
    data = fetch_company_facts(cik=cik, user_agent=user_agent)

    # Step 2: Save raw JSON
    save_raw_json(data, output_dir=raw_output_dir)

    # Step 3: Extract & clean
    df = extract_financial_concepts(
        data=data,
        concept_map=concept_map,
        years_to_keep=years_to_keep,
    )

    # Step 4: Save processed CSV
    if not df.empty:
        save_processed_financials(df, output_dir=processed_output_dir)

    # Step 5: Diagnostics
    print_diagnostics(df)

    return df


# ═══════════════════════════════════════════════════════════════════════════
# CLI entry point
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import sys
    from pathlib import Path

    # Resolve paths relative to project root
    project_root = Path(__file__).resolve().parent.parent
    raw_dir = str(project_root / "data" / "raw" / "xbrl")
    processed_dir = str(project_root / "data" / "processed")

    # Load config if available, otherwise use defaults
    config_path = project_root / "config" / "assumptions.yaml"
    cik = "0000937966"
    user_agent = "ASMLValuation research@example.com"

    if config_path.exists():
        import yaml
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        sec_config = config.get("sec", {})
        cik = sec_config.get("cik", cik)
        user_agent = sec_config.get("user_agent", user_agent)

    df = run_sec_extraction(
        cik=cik,
        user_agent=user_agent,
        raw_output_dir=raw_dir,
        processed_output_dir=processed_dir,
    )

    if not df.empty:
        print("\n── Preview (last 5 years) ──\n")
        print(df.tail().to_string())
    else:
        print("\n⚠ No data extracted. Check CIK and network connectivity.")
        sys.exit(1)
