# Corporate Valuation Framework

A modular, first-principles Python framework for DCF-based equity valuation.  Originally built for ASML Holding N.V., but designed to work for **any publicly traded company** by changing a single configuration file.

---

## What It Does

| Capability | Detail |
|---|---|
| **Historical analysis** | Margins, ROIC, reinvestment intensity, working-capital dynamics across cycles |
| **Forward projections** | Revenue drivers, cost structure, capex, and working capital from configurable scenarios |
| **Intrinsic valuation** | Explicit-period FCFF discounted at WACC + Gordon Growth terminal value |
| **Sensitivity analysis** | Two-way tables (Growth × WACC) and reverse-DCF implied expectations |
| **Visualisations** | 8 publication-quality charts narrating the valuation story |
| **Report generation** | Automated Markdown equity research note |

All valuation logic is hand-built — no black-box finance libraries.

---

## Architecture

```
├── config/
│   └── assumptions.yaml          ← All tuneable parameters — change this to analyse a new company
│
├── etl/
│   ├── extract_market_data.py    ← yfinance: prices, market cap, shares outstanding
│   ├── extract_sec_xbrl.py       ← SEC EDGAR XBRL: 10-year financials (income, balance, cash flow)
│   ├── extract_macro_data.py     ← FRED: risk-free rate scaffold
│   └── load_financials.py        ← Loader for manually entered CSV financials
│
├── processing/
│   ├── clean_financials.py       ← Column standardisation, type coercion, missing-value handling
│   ├── compute_ratios.py         ← Margin, growth, and efficiency ratios
│   ├── roic.py                   ← ROIC, invested capital, incremental ROIC
│   └── working_capital.py        ← NWC breakdown and ΔNWC computation
│
├── models/
│   ├── wacc.py                   ← Cost of equity (CAPM), cost of debt, WACC
│   ├── dcf.py                    ← FCFF projection, terminal value, enterprise value
│   ├── reverse_engineering.py    ← Implied growth / ROIC from market price
│   └── sensitivity.py            ← Two-way sensitivity tables
│
├── insights/
│   ├── historical_analysis.py    ← Historical trend summaries
│   └── valuation_summary.py      ← Automated equity research note in Markdown
│
├── visualisations/
│   ├── chart_style.py            ← Shared design system (FT/Economist style)
│   ├── valuation_multiples.py    ← Charts 1–2: P/E + EV/EBITDA over time
│   ├── revenue_growth.py         ← Chart 3: Revenue bars + growth overlay
│   ├── price_vs_intrinsic.py     ← Chart 4: Market price vs DCF value
│   ├── margin_evolution.py       ← Chart 5: Gross / operating / net margin layers
│   ├── roic_vs_wacc.py           ← Chart 6: Value creation spread
│   ├── fcf_yield.py              ← Chart 7: Free cash flow yield
│   ├── sensitivity_heatmap.py    ← Chart 8: Growth × WACC heatmap
│   └── generate_all.py           ← CLI runner for all 8 charts
│
├── data/
│   ├── raw/                      ← Unprocessed source data (auto-downloaded)
│   ├── interim/                  ← Partially cleaned data
│   └── processed/                ← Analysis-ready datasets
│
├── reports/
│   ├── charts/                   ← Generated chart PNGs (8 files)
│   └── {ticker}_valuation_report.md
│
├── main.py                       ← Orchestration entry point (9-stage pipeline)
└── requirements.txt
```

---

## Quick Start

### 1. Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure

Edit `config/assumptions.yaml` with the target company's parameters (see [Configuration Reference](#configuration-reference) below).

### 3. Run

```bash
python main.py
```

This runs all 9 pipeline stages end-to-end:

| Stage | What It Does | Skip Flag |
|-------|-------------|-----------|
| 1. Configuration | Loads and validates `assumptions.yaml` | — |
| 2. Extraction | Downloads price history, company info, SEC XBRL financials | `--skip-extract` |
| 3. Analysis | Cleans data, computes ratios, ROIC, working capital | `--skip-analysis` |
| 4. WACC | Computes cost of equity (CAPM), cost of debt, WACC | — |
| 5. DCF Valuation | Projects FCFF, terminal value, enterprise → equity value | — |
| 6. Sensitivity | Two-way sensitivity tables (Growth × WACC) | `--skip-sensitivity` |
| 7. Reverse DCF | Implied growth and ROIC from current market price | `--skip-sensitivity` |
| 8. Summary Report | Generates comprehensive Markdown equity research note | — |
| 9. Visualisations | Produces 8 publication-quality chart PNGs | `--skip-viz` |

**Faster reruns** (skip extraction, use cached data):
```bash
python main.py --skip-extract
```

**Charts only:**
```bash
python -m visualisations.generate_all
```

---

## Analysing a Different Company

The entire pipeline is **ticker-agnostic**. To switch from ASML to, say, **Apple**, you only change `config/assumptions.yaml` — no code edits needed.

### Step 1: Update `assumptions.yaml`

```yaml
# ── Identity ────────────────────────────────────────────
company:
  name: "Apple Inc."
  ticker: "AAPL"
  currency: "USD"

# ── SEC EDGAR ───────────────────────────────────────────
sec:
  cik: "0000320193"          # Apple's CIK (find at sec.gov/cgi-bin/browse-edgar)
  taxonomy: "us-gaap"

# ── Projections (your analyst judgement) ────────────────
revenue:
  near_term_growth_rates: [0.05, 0.06, 0.07, 0.06, 0.05]
  long_term_growth_rate: 0.04

margins:
  operating_margin: 0.32

cost_of_capital:
  risk_free_rate: 0.04
  equity_risk_premium: 0.05
  beta: 1.20
  pre_tax_cost_of_debt: 0.03
  target_debt_to_capital: 0.25

projection:
  explicit_years: 10
  terminal_growth_rate: 0.025

capital_intensity:
  capex_to_revenue: 0.03
  depreciation_to_revenue: 0.03
  nwc_to_revenue: -0.15      # Apple has negative NWC (supplier financing)
```

### Step 2: Run

```bash
python main.py
```

### What Happens

| Stage | What the pipeline does for Apple |
|-------|----------------------------------|
| **1. Config** | Reads `AAPL` as ticker, `Apple Inc.` as company name |
| **2. Extract** | Downloads `aapl_price_history.csv` and `aapl_company_info.csv` via yfinance; pulls 10-year financials from SEC EDGAR using CIK `0000320193` |
| **3. Analysis** | Computes Apple's margins, ROIC, working capital ratios from the downloaded financials |
| **4. WACC** | Calculates Apple's cost of capital using β=1.20, D/C=25%, etc. |
| **5. DCF** | Projects Apple's FCFF using your growth/margin assumptions → intrinsic value per share |
| **6. Sensitivity** | Growth × WACC two-way tables centred on Apple's current price |
| **7. Reverse DCF** | "What growth does the market imply at Apple's current price?" |
| **8. Report** | Generates `reports/aapl_valuation_report.md` |
| **9. Charts** | Generates 8 PNGs in `reports/charts/` with titles like *"Apple Inc. — Trailing P/E Ratio"* |

All output files use the ticker prefix: `aapl_price_history.csv`, `aapl_company_info.csv`, `aapl_valuation_report.md`.

> [!NOTE]
> **Narrative zones** (the shaded "Hidden Champion → EUV Inflection → Premium Monopoly" arcs on time-series charts) are ASML-specific story arcs defined in `chart_style.py`. They'll still appear on other companies but won't be semantically meaningful. Making these configurable per-company via `assumptions.yaml` is a planned enhancement.

> [!IMPORTANT]
> The **report prose** in `insights/valuation_summary.py` contains ASML-specific narrative (company description, investor day references). For a different company, the numbers and tables will be correct, but the qualitative commentary will reference ASML. Generalizing this into company-specific templates is a future effort.

---

## Data Requirements

To run the full pipeline for **any company**, you need:

### Automatic (fetched by the pipeline)

| Data | Source | Requirement |
|------|--------|-------------|
| Historical prices | [Yahoo Finance](https://pypi.org/project/yfinance/) via `yfinance` | Valid ticker symbol |
| Company info (market cap, shares, beta) | Yahoo Finance | Same ticker |
| Financial statements (10 years) | [SEC EDGAR XBRL](https://data.sec.gov/) | Valid CIK number |

### Manual (you provide in `assumptions.yaml`)

| Parameter | Description | Example |
|-----------|-------------|---------|
| `company.ticker` | Yahoo Finance ticker | `"ASML"` |
| `company.name` | Display name | `"ASML Holding N.V."` |
| `sec.cik` | SEC EDGAR CIK number | `"0000937966"` |
| `revenue.near_term_growth_rates` | Year-by-year growth overrides (1–5 years) | `[0.155, 0.116, ...]` |
| `margins.operating_margin` | Target operating margin | `0.38` |
| `cost_of_capital.*` | Risk-free rate, ERP, beta, cost of debt, D/C ratio | See config |
| `projection.terminal_growth_rate` | Long-run nominal growth | `0.025` |
| `capital_intensity.*` | Capex/rev, D&A/rev, NWC/rev | See config |

> **Note:** Non-US companies that file 20-F with the SEC work natively. For companies that don't file with the SEC, place financial CSVs manually in `data/raw/` — see `etl/load_financials.py` for the expected format.

---

## Configuration Reference

All assumptions live in `config/assumptions.yaml`. The file is fully commented with calibration notes. Key sections:

```yaml
company:
  name: "ASML Holding N.V."
  ticker: "ASML"
  currency: "EUR"

cost_of_capital:
  risk_free_rate: 0.03        # 10y sovereign yield
  equity_risk_premium: 0.05   # Damodaran ERP
  beta: 1.10                  # Levered beta
  pre_tax_cost_of_debt: 0.035
  target_debt_to_capital: 0.01

projection:
  explicit_years: 10
  terminal_growth_rate: 0.025

revenue:
  near_term_growth_rates: [0.155, 0.116, 0.151, 0.143, 0.083]
  long_term_growth_rate: 0.06

margins:
  operating_margin: 0.38

capital_intensity:
  capex_to_revenue: 0.07
  depreciation_to_revenue: 0.03
  nwc_to_revenue: 0.17

sensitivity:
  wacc_range: [0.07, 0.075, 0.08, 0.085, 0.09, 0.095, 0.10, 0.105, 0.11]
  terminal_growth_range: [0.015, 0.020, 0.025, 0.030, 0.035]
```

Modify this file to run different scenarios — no code changes required.

---

## Design Principles

| Principle | Implementation |
|---|---|
| **No hardcoded assumptions** | Every parameter lives in `assumptions.yaml` and is passed explicitly |
| **Pure functions** | Processing and model functions are stateless — same inputs → same outputs |
| **Type hints + docstrings** | Every public function is annotated and documented |
| **Modular pipeline** | ETL → Processing → Models → Insights → Visualisations |
| **Ticker-agnostic** | Change `assumptions.yaml` to analyse any company |

---

## Data Sources

| Source | Used For |
|---|---|
| [Yahoo Finance (yfinance)](https://pypi.org/project/yfinance/) | Historical prices, market cap, shares outstanding |
| [SEC EDGAR XBRL](https://data.sec.gov/) | 10-year financial statements (income, balance sheet, cash flow) |
| [FRED](https://fred.stlouisfed.org/) | Risk-free rate (scaffold) |

---

## Outputs

| Output | Path |
|---|---|
| Valuation report | `reports/{ticker}_valuation_report.md` |
| P/E ratio chart | `reports/charts/01_pe_ratio.png` |
| EV/EBITDA chart | `reports/charts/02_ev_ebitda.png` |
| Revenue & growth | `reports/charts/03_revenue_growth.png` |
| Price vs intrinsic value | `reports/charts/04_price_vs_intrinsic.png` |
| Margin evolution | `reports/charts/05_margin_evolution.png` |
| ROIC vs WACC | `reports/charts/06_roic_vs_wacc.png` |
| FCF yield | `reports/charts/07_fcf_yield.png` |
| Sensitivity heatmap | `reports/charts/08_sensitivity_heatmap.png` |

---

## License

This project is for educational and research purposes only. It does not constitute financial advice.
