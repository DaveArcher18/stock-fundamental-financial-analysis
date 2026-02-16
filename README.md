# ASML Corporate Valuation Framework

A modular, production-style Python framework for corporate finance analysis and intrinsic valuation of ASML Holding N.V., built entirely from first principles using only publicly available data.

## Purpose

This project implements a discounted free-cash-flow-to-firm (FCFF) valuation model for ASML, a capital-intensive, near-monopoly semiconductor equipment company. The framework is designed to:

- **Analyse historical financials** — margins, returns on invested capital, reinvestment intensity, and working-capital dynamics across semiconductor capex cycles.
- **Build forward projections** — revenue drivers, cost structure, capex, and working capital tied to configurable scenario assumptions.
- **Estimate intrinsic value** — via explicit-period FCFF discounted at WACC plus a terminal value, with sensitivity and reverse-DCF cross-checks.
- **Understand market-implied expectations** — reverse-engineer the growth, ROIC, and capital intensity assumptions embedded in the current share price.

All valuation logic is hand-built — no black-box finance libraries are used.

---

## Architecture

```
asml_valuation/
│
├── data/
│   ├── raw/              # Unprocessed source data (market prices, macro, raw CSVs)
│   ├── interim/          # Partially cleaned / standardised data
│   └── processed/        # Analysis-ready datasets
│
├── etl/
│   ├── extract_market_data.py    # yfinance market data extraction
│   ├── extract_macro_data.py     # Macro / risk-free rate scaffold (FRED)
│   └── load_financials.py        # Loader for manually entered financial statements
│
├── processing/
│   ├── clean_financials.py       # Column standardisation, type coercion, missing-value handling
│   ├── compute_ratios.py         # Margin, growth, and efficiency ratios
│   ├── roic.py                   # ROIC, invested capital, incremental ROIC
│   └── working_capital.py        # NWC breakdown and ∆NWC computation
│
├── models/
│   ├── wacc.py                   # Cost of equity, cost of debt, WACC
│   ├── dcf.py                    # FCFF projection, terminal value, enterprise value
│   ├── reverse_engineering.py    # Implied growth / ROIC from market price
│   └── sensitivity.py            # Two-way sensitivity tables
│
├── insights/
│   ├── historical_analysis.py    # Historical trend summaries and visualisations
│   └── valuation_summary.py      # Consolidated valuation output
│
├── config/
│   └── assumptions.yaml          # All tuneable parameters in one place
│
├── main.py                       # Orchestration entry point
├── requirements.txt              # Pinned dependencies
└── README.md                     # This file
```

### Design Principles

| Principle | Implementation |
|---|---|
| **No hardcoded assumptions** | Every model parameter lives in `config/assumptions.yaml` and is passed explicitly to functions. |
| **Pure functions** | Processing and model functions are stateless — given the same inputs they always produce the same outputs. |
| **Type hints + docstrings** | Every public function is annotated and documented. |
| **Modular pipeline** | ETL → Processing → Models → Insights. Each layer can be tested and run independently. |
| **Extensible** | Adding a new scenario or ratio is a matter of adding a config entry and a small function — no refactoring needed. |

---

## Quick Start

### 1. Install Dependencies

```bash
cd asml_valuation
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Run Market Data Extraction (ETL)

```bash
python main.py
```

This will:
1. Pull full historical ASML price data via yfinance and save to `data/raw/`.
2. Attempt to load and clean financial statements from `data/raw/` (if CSVs exist).
3. Print basic summary statistics.

### 3. Prepare Financial Statements

Place the following CSV files in `data/raw/`:

| File | Expected Columns |
|---|---|
| `income_statement.csv` | `date`, `revenue`, `cost_of_revenue`, `gross_profit`, `rd_expense`, `sga_expense`, `operating_income`, `interest_expense`, `pretax_income`, `income_tax`, `net_income` |
| `balance_sheet.csv` | `date`, `cash`, `accounts_receivable`, `inventory`, `total_current_assets`, `ppe_net`, `total_assets`, `accounts_payable`, `short_term_debt`, `total_current_liabilities`, `long_term_debt`, `total_liabilities`, `total_equity` |
| `cash_flow.csv` | `date`, `net_income`, `depreciation`, `change_in_working_capital`, `operating_cash_flow`, `capex`, `investing_cash_flow`, `financing_cash_flow`, `free_cash_flow` |

### 4. Run Processing

After financial data is loaded:

```python
from processing.clean_financials import clean_financial_data
from processing.compute_ratios import compute_all_ratios
from processing.roic import compute_roic_table

cleaned = clean_financial_data(raw_df)
ratios = compute_all_ratios(cleaned_income, cleaned_cashflow)
roic = compute_roic_table(cleaned_income, cleaned_balance)
```

### 5. Extend to Valuation

Implement model functions in `models/` using the provided scaffolds:

```python
from models.wacc import wacc
from models.dcf import enterprise_value

discount_rate = wacc(cost_of_equity=0.09, cost_of_debt=0.03, tax_rate=0.15, equity_weight=0.85)
ev = enterprise_value(fcf_projections, discount_rate, terminal_value)
```

---

## Configuration

All assumptions are centralised in `config/assumptions.yaml`:

```yaml
ticker: "ASML"
tax_rate: 0.15
risk_free_rate: 0.035
equity_risk_premium: 0.05
beta: 1.1
projection_years: 10
terminal_growth_rate: 0.025
```

Modify this file to run different scenarios — no code changes required.

---

## Data Sources

| Source | Used For |
|---|---|
| [Yahoo Finance (yfinance)](https://pypi.org/project/yfinance/) | Historical prices, market cap, shares outstanding |
| [FRED](https://fred.stlouisfed.org/) | Risk-free rate (scaffold) |
| ASML Annual Reports | Financial statements (manually entered CSVs) |

---

## License

This project is for educational and research purposes only. It does not constitute financial advice.
