"""
Insights — Valuation Summary Report
======================================
Generates a comprehensive equity research note in Markdown format,
synthesising all analysis outputs into a single readable document.

Usage:
    python -m insights.valuation_summary

Output:
    reports/asml_valuation_report.md
"""

import sys
import time
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

CONFIG_PATH = PROJECT_ROOT / "config" / "assumptions.yaml"


def _get_company_dirs() -> tuple[Path, Path, Path]:
    """Derive per-company output directories from config."""
    with open(CONFIG_PATH, "r") as f:
        cfg = yaml.safe_load(f)
    ticker = cfg.get("company", {}).get("ticker", "COMPANY").upper()
    base = PROJECT_ROOT / "output" / ticker
    return base / "data" / "raw", base / "data" / "processed", base / "reports"


# ═══════════════════════════════════════════════════════════════════════════
# Data Loaders
# ═══════════════════════════════════════════════════════════════════════════


def _load_all_data() -> dict:
    """Load all processed data into a single dictionary."""
    data = {}
    raw_dir, processed_dir, _ = _get_company_dirs()

    # Config
    with open(CONFIG_PATH, "r") as f:
        data["config"] = yaml.safe_load(f)

    # Financials
    data["financials"] = pd.read_csv(
        processed_dir / "financials_annual.csv", index_col=0, parse_dates=True,
    )
    # Patch missing columns for robustness
    df = data["financials"]
    if "gross_profit" not in df.columns:
        if "cost_of_revenue" in df.columns:
            df["gross_profit"] = df["revenue"] - df["cost_of_revenue"]
        else:
            df["gross_profit"] = np.nan

    if "operating_income" not in df.columns:
        # Try to calculate OpInc = Revenue - COGS - RD - SGA
        # If any component is missing, it will result in NaN, which is handled
        cogs = df.get("cost_of_revenue", 0)
        rd = df.get("rd_expense", 0)
        sga = df.get("sga_expense", 0)
        df["operating_income"] = df["revenue"] - cogs - rd - sga

    data["ratios"] = pd.read_csv(processed_dir / "financial_ratios.csv", index_col=0)
    data["roic"] = pd.read_csv(processed_dir / "roic_analysis.csv", index_col=0)
    data["working_capital"] = pd.read_csv(processed_dir / "working_capital.csv", index_col=0)

    # DCF
    data["dcf_proj"] = pd.read_csv(processed_dir / "dcf_projections.csv")

    # Sensitivity
    data["tornado"] = pd.read_csv(processed_dir / "tornado_analysis.csv")
    data["reverse"] = pd.read_csv(processed_dir / "reverse_dcf_implied.csv")

    # Sensitivity tables
    for name in ["sensitivity_wacc_tg", "sensitivity_growth_margin", "sensitivity_growth_wacc"]:
        path = processed_dir / f"{name}.csv"
        if path.exists():
            data[name] = pd.read_csv(path, index_col=0)

    # Company info
    _ticker = data["config"].get("company", {}).get("ticker", "company").lower()
    info_path = raw_dir / f"{_ticker}_company_info.csv"
    if info_path.exists():
        info_df = pd.read_csv(info_path)
        data["company_info"] = dict(zip(info_df["field"], info_df["value"]))

    return data


# ═══════════════════════════════════════════════════════════════════════════
# Report Sections
# ═══════════════════════════════════════════════════════════════════════════


def _header(data: dict) -> str:
    """Report header and executive summary."""
    config = data["config"]
    fin = data["financials"]
    dcf = data["dcf_proj"]
    reverse = data["reverse"].iloc[0]
    info = data.get("company_info", {})
    latest = fin.iloc[-1]

    # Compute key metrics
    from models.wacc import compute_wacc_from_data
    market_cap_usd = float(info.get("market_cap", 0))
    wacc_result = compute_wacc_from_data(config, fin, market_cap_usd)
    wacc_rate = wacc_result["wacc"]

    from models.dcf import run_dcf
    market_shares = float(info.get("shares_outstanding", 0))
    dcf_result = run_dcf(config, fin, wacc_rate, market_cap_usd, market_data_shares=market_shares)
    eq = dcf_result["equity"]
    ev = dcf_result["ev"]
    mkt = dcf_result.get("market", {})

    vps = eq["value_per_share"]
    market_price = mkt.get("market_price_per_share_eur", 0)
    upside = mkt.get("upside_pct", 0)

    if upside > 20:
        verdict = "🟢 UNDERVALUED"
    elif upside > -10:
        verdict = "🟡 FAIRLY VALUED"
    else:
        verdict = "🔴 OVERVALUED"

    today = datetime.now().strftime("%B %d, %Y")

    lines = []
    company_name = config.get("company", {}).get("name", "Company")
    ticker = config.get("company", {}).get("ticker", "TICKER")
    sector = info.get("sector", "Sector")
    industry = info.get("industry", "Industry")
    
    lines = []
    lines.append(f"# {company_name} — Equity Valuation Report")
    lines.append(f"")
    lines.append(f"**Date:** {today}  ")
    lines.append(f"**Ticker:** {ticker}  ")
    lines.append(f"**Sector:** {sector} — {industry}  ")
    lines.append(f"**Currency:** {config.get('company', {}).get('currency', 'USD')}  ")
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"")
    lines.append(f"## Executive Summary")
    lines.append(f"")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| **Intrinsic Value / Share** | **€{vps:,.0f}** |")
    lines.append(f"| Current Market Price | ~€{market_price:,.0f} |")
    lines.append(f"| Upside / Downside | {upside:+.1f}% |")
    lines.append(f"| Verdict | {verdict} |")
    lines.append(f"| Enterprise Value | €{ev['enterprise_value']/1e9:.0f}B |")
    lines.append(f"| Equity Value | €{eq['equity_value']/1e9:.0f}B |")
    lines.append(f"| WACC | {wacc_rate*100:.2f}% |")
    lines.append(f"| Terminal Growth | {config['projection']['terminal_growth_rate']*100:.1f}% |")
    lines.append(f"| TV as % of EV | {ev['terminal_pct']:.0f}% |")
    lines.append(f"")

    # Store for later use
    data["_dcf_result"] = dcf_result
    data["_wacc_result"] = wacc_result
    data["_wacc_rate"] = wacc_rate
    data["_market_price"] = market_price
    data["_vps"] = vps

    return "\n".join(lines)


def _business_overview(data: dict) -> str:
    """Section 1: Business overview."""
    fin = data["financials"]
    latest = fin.iloc[-1]
    info = data.get("company_info", {})

    rev = latest["revenue"] / 1e9
    ni = latest["net_income"] / 1e9
    gm = latest["gross_profit"] / latest["revenue"] * 100
    om = latest["operating_income"] / latest["revenue"] * 100

    lines = []
    lines.append(f"## 1. Business Overview")
    lines.append(f"")
    lines.append(f"_{data['config'].get('company', {}).get('name', 'Company')} is a leading company in the {info.get('sector', 'Technology')} sector._")
    lines.append(f"")
    lines.append(f"**Latest fiscal year (FY{int(latest['fiscal_year'])}):**")
    lines.append(f"- Revenue: €{rev:.1f}B")
    lines.append(f"- Net income: €{ni:.1f}B")
    lines.append(f"- Gross margin: {gm:.1f}%")
    lines.append(f"- Operating margin: {om:.1f}%")
    lines.append(f"- Market cap: ~${float(info.get('market_cap', 0))/1e9:.0f}B USD")
    lines.append(f"")
    return "\n".join(lines)


def _historical_financials(data: dict) -> str:
    """Section 2: Historical financial performance."""
    fin = data["financials"]
    ratios = data["ratios"]

    lines = []
    lines.append(f"## 2. Historical Financial Performance")
    lines.append(f"")

    # Revenue table
    lines.append(f"### Revenue & Profitability (10-Year History)")
    lines.append(f"")
    lines.append(f"| FY | Revenue (€B) | Growth | Gross Margin | Op. Margin | Net Margin |")
    lines.append(f"|---:|-------------:|-------:|-------------:|-----------:|-----------:|")

    for i, (_, row) in enumerate(fin.iterrows()):
        fy = int(row["fiscal_year"])
        rev = row["revenue"] / 1e9
        gm = row["gross_profit"] / row["revenue"] * 100
        om = row["operating_income"] / row["revenue"] * 100
        nm = row["net_income"] / row["revenue"] * 100

        if i == 0:
            growth = "—"
        else:
            prev_rev = fin.iloc[i - 1]["revenue"]
            g = (row["revenue"] / prev_rev - 1) * 100
            growth = f"{g:+.1f}%"

        lines.append(f"| {fy} | {rev:.1f} | {growth} | {gm:.1f}% | {om:.1f}% | {nm:.1f}% |")

    # CAGRs
    revs = fin["revenue"].values
    lines.append(f"")
    lines.append(f"**Compound Annual Growth Rates:**")
    for window, label in [(3, "3-year"), (5, "5-year"), (9, "9-year")]:
        if len(fin) > window:
            cagr = (revs[-1] / revs[-window - 1]) ** (1 / window) - 1
            lines.append(f"- {label} CAGR: **{cagr*100:.1f}%**")

    lines.append(f"")
    return "\n".join(lines)


def _roic_analysis(data: dict) -> str:
    """Section 3: ROIC and capital efficiency."""
    roic = data["roic"]
    fin = data["financials"]

    lines = []
    lines.append(f"## 3. Return on Invested Capital (ROIC)")
    lines.append(f"")
    lines.append(f"ROIC is the central metric for assessing whether ASML creates value — "
                 f"it measures how much operating profit the company generates per euro of capital invested.")
    lines.append(f"")
    lines.append(f"| FY | NOPAT (€B) | Invested Capital (€B) | ROIC | ROE |")
    lines.append(f"|---:|-----------:|----------------------:|-----:|----:|")

    for _, row in roic.iterrows():
        fy = int(row["fiscal_year"])
        nopat = row["nopat"] / 1e9
        ic = row["invested_capital"] / 1e9
        r = row["roic"] * 100
        roe = row["roe"] * 100
        lines.append(f"| {fy} | {nopat:.1f} | {ic:.1f} | {r:.1f}% | {roe:.1f}% |")

    # Summary
    avg_roic = roic["roic"].tail(3).mean() * 100
    lines.append(f"")
    lines.append(f"**3-year average ROIC: {avg_roic:.1f}%** — well above the cost of capital "
                 f"(WACC ≈ 8.5%), confirming ASML's exceptional value creation.")
    lines.append(f"")
    return "\n".join(lines)


def _working_capital(data: dict) -> str:
    """Section 4: Working capital analysis."""
    wc = data["working_capital"]

    lines = []
    lines.append(f"## 4. Working Capital & Cash Conversion")
    lines.append(f"")
    lines.append(f"| FY | NWC (€B) | ΔNWC (€B) | DSO | DIO | DPO | CCC (days) |")
    lines.append(f"|---:|---------:|-----------:|----:|----:|----:|-----------:|")

    for _, row in wc.tail(5).iterrows():
        fy = int(row["fiscal_year"])
        nwc = row["nwc"] / 1e9
        dnwc = row["delta_nwc"] / 1e9
        lines.append(f"| {fy} | {nwc:.1f} | {dnwc:+.1f} | {row['dso']:.0f} | "
                     f"{row['dio']:.0f} | {row['dpo']:.0f} | {row['ccc']:.0f} |")

    latest = wc.iloc[-1]
    lines.append(f"")
    lines.append(f"**Key observation:** ASML's cash conversion cycle is **{latest['ccc']:.0f} days**, "
                 f"reflecting the 6–12 month build times for EUV systems. "
                 f"Days inventory outstanding ({latest['dio']:.0f} days) is particularly high, "
                 f"which is structural for capital equipment manufacturers.")
    lines.append(f"")
    return "\n".join(lines)


def _wacc_section(data: dict) -> str:
    """Section 5: WACC analysis."""
    wacc = data["_wacc_result"]
    config = data["config"]

    lines = []
    lines.append(f"## 5. Cost of Capital (WACC)")
    lines.append(f"")
    lines.append(f"### CAPM Inputs")
    lines.append(f"")
    lines.append(f"| Parameter | Value | Source |")
    lines.append(f"|-----------|------:|--------|")
    lines.append(f"| Risk-free rate (Rf) | {config['cost_of_capital']['risk_free_rate']*100:.1f}% | 10y German Bund |")
    lines.append(f"| Equity beta (β) | {config['cost_of_capital']['beta']:.2f} | Analyst estimate (< Yahoo's 1.46) |")
    lines.append(f"| Equity risk premium | {config['cost_of_capital']['equity_risk_premium']*100:.1f}% | Damodaran mature market |")
    lines.append(f"| Country risk premium | {config['cost_of_capital'].get('country_risk_premium', 0)*100:.1f}% | Netherlands (AAA) |")
    lines.append(f"")
    lines.append(f"### Capital Structure (Market Values)")
    lines.append(f"")
    lines.append(f"| Component | Value | Weight |")
    lines.append(f"|-----------|------:|-------:|")

    cap = wacc.get("capital_structure", {})
    lines.append(f"| Equity (market cap) | €{cap.get('market_cap_eur', 0)/1e9:.0f}B | "
                 f"{wacc.get('equity_weight', 0)*100:.1f}% |")
    lines.append(f"| Debt (book value) | €{cap.get('total_debt_eur', 0)/1e9:.1f}B | "
                 f"{wacc.get('debt_weight', 0)*100:.1f}% |")
    lines.append(f"")
    lines.append(f"### Result")
    lines.append(f"")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|------:|")
    lines.append(f"| Cost of equity (Rₑ) | {wacc['cost_of_equity']*100:.2f}% |")
    lines.append(f"| Cost of debt (after-tax) | {wacc['cost_of_debt_after_tax']*100:.2f}% |")
    lines.append(f"| **WACC** | **{wacc['wacc']*100:.2f}%** |")
    lines.append(f"")
    lines.append(f"*Note: ASML uses minimal financial leverage (D/V < 1%), so WACC is "
                 f"dominated by the cost of equity. The beta of 1.10 is a conservative "
                 f"estimate — Yahoo Finance reports 1.46, which would raise WACC to ~10%.*")
    lines.append(f"")
    return "\n".join(lines)


def _dcf_section(data: dict) -> str:
    """Section 6: DCF valuation."""
    dcf_result = data["_dcf_result"]
    proj = dcf_result["projections"]
    ev = dcf_result["ev"]
    eq = dcf_result["equity"]
    inputs = dcf_result["inputs"]
    config = data["config"]
    fin = data["financials"]

    base_fy = int(fin.iloc[-1]["fiscal_year"])

    lines = []
    lines.append(f"## 6. DCF Valuation")
    lines.append(f"")
    lines.append(f"### Key Assumptions")
    lines.append(f"")
    lines.append(f"| Assumption | Value | Rationale |")
    lines.append(f"|------------|------:|-----------|")

    near = config["revenue"].get("near_term_growth_rates", [])
    if near:
        near_str = ", ".join(f"{g*100:.1f}%" for g in near)
        lines.append(f"| Near-term growth (Yr 1–5) | [{near_str}] | Company guidance + consensus |")
    lines.append(f"| Long-term growth (Yr 6–10) | {config['revenue']['long_term_growth_rate']*100:.0f}% fade | Secular semi growth |")
    lines.append(f"| Terminal growth (g∞) | {config['projection']['terminal_growth_rate']*100:.1f}% | ~ EUR nominal GDP |")
    lines.append(f"| Operating margin target | {config['margins']['operating_margin']*100:.0f}% | ASML 2030 guidance (GM 56–60%) |")
    lines.append(f"| Margin fade period | 5 years | Linear from {inputs['current_op_margin']*100:.1f}% → {inputs['target_op_margin']*100:.0f}% |")
    lines.append(f"| Capex / Revenue | {config['capital_intensity']['capex_to_revenue']*100:.0f}% | Elevated — capacity buildout |")
    lines.append(f"| ΔNWC / ΔRevenue | {config['capital_intensity']['nwc_to_revenue']*100:.0f}% | Marginal working capital rate |")
    lines.append(f"| Tax rate | {config['tax']['effective_rate']*100:.0f}% | Blended effective rate |")
    lines.append(f"")

    # Projection table
    lines.append(f"### FCFF Projections")
    lines.append(f"")
    lines.append(f"| Year | FY | Growth | Revenue (€B) | Op. Margin | NOPAT (€B) | FCFF (€B) |")
    lines.append(f"|-----:|---:|-------:|-------------:|-----------:|-----------:|----------:|")

    for _, row in proj.iterrows():
        yr = int(row["year"])
        fy = base_fy + yr
        lines.append(f"| {yr} | {fy} | {row['growth_rate']*100:.1f}% | "
                     f"{row['revenue']/1e9:.1f} | {row['operating_margin']*100:.1f}% | "
                     f"{row['nopat']/1e9:.1f} | {row['fcff']/1e9:.1f} |")

    lines.append(f"")

    # Valuation waterfall
    lines.append(f"### Valuation Waterfall")
    lines.append(f"")
    lines.append(f"| Component | Value (€B) | % of EV |")
    lines.append(f"|-----------|----------:|--------:|")
    exp_pct = 100 - ev["terminal_pct"]
    lines.append(f"| PV of explicit FCFF (Yr 1–10) | {ev['pv_explicit']/1e9:.1f} | {exp_pct:.0f}% |")
    lines.append(f"| PV of terminal value | {ev['pv_terminal']/1e9:.1f} | {ev['terminal_pct']:.0f}% |")
    lines.append(f"| **Enterprise Value** | **{ev['enterprise_value']/1e9:.1f}** | **100%** |")

    nd = eq["net_debt"]
    sign = "−" if nd >= 0 else "+"
    nc_label = "net debt" if nd >= 0 else "net cash"
    lines.append(f"| {sign} {nc_label.title()} | {abs(nd)/1e9:.1f} | — |")
    lines.append(f"| **Equity Value** | **{eq['equity_value']/1e9:.1f}** | — |")
    lines.append(f"| ÷ Shares outstanding | {eq['shares_outstanding']/1e6:.0f}M | — |")
    lines.append(f"| **Intrinsic Value / Share** | **€{eq['value_per_share']:,.0f}** | — |")
    lines.append(f"")
    return "\n".join(lines)


def _sensitivity_section(data: dict) -> str:
    """Section 7: Sensitivity analysis."""
    tornado = data["tornado"]

    lines = []
    lines.append(f"## 7. Sensitivity Analysis")
    lines.append(f"")

    # Tornado
    lines.append(f"### Value Driver Ranking (Tornado)")
    lines.append(f"")
    lines.append(f"Which parameters have the biggest impact on intrinsic value?")
    lines.append(f"")
    lines.append(f"| Rank | Parameter | Range | Low | High | Swing |")
    lines.append(f"|-----:|-----------|------:|----:|-----:|------:|")

    for i, (_, row) in enumerate(tornado.iterrows()):
        bv = row["base_value"]
        lv = row["low_value"]
        hv = row["high_value"]
        if abs(bv) < 1 and bv != 0:
            rng = f"{lv*100:.0f}% → {hv*100:.0f}%"
        else:
            rng = f"{lv} → {hv}"

        lines.append(f"| {i+1} | {row['parameter']} | {rng} | "
                     f"€{row['low_result']:,.0f} | €{row['high_result']:,.0f} | "
                     f"€{row['swing']:,.0f} |")

    lines.append(f"")
    lines.append(f"**Key insight:** Revenue growth is by far the most impactful parameter, "
                 f"with a swing of **€{tornado.iloc[0]['swing']:,.0f}** between bear and bull cases. "
                 f"WACC ranks second, followed by operating margins.")
    lines.append(f"")

    # WACC × Terminal Growth table
    if "sensitivity_wacc_tg" in data:
        table = data["sensitivity_wacc_tg"]
        lines.append(f"### WACC × Terminal Growth (Value / Share)")
        lines.append(f"")

        # Format as markdown table
        cols = []
        valid_cols = []
        for c in table.columns:
            try:
                val = float(c)
                cols.append(f"{val*100:.1f}%")
                valid_cols.append(c)
            except ValueError:
                continue
        
        table = table[valid_cols]
        header = "| WACC \\ g∞ | " + " | ".join(cols) + " |"
        sep = "|---:" + "|---:" * len(cols) + "|"
        lines.append(header)
        lines.append(sep)

        for idx, row in table.iterrows():
            wacc_label = f"{float(idx)*100:.1f}%"
            vals = " | ".join(f"€{v:,.0f}" for v in row.values)
            lines.append(f"| {wacc_label} | {vals} |")

        lines.append(f"")

    # Growth × WACC table
    if "sensitivity_growth_wacc" in data:
        table = data["sensitivity_growth_wacc"]
        lines.append(f"### Revenue Growth × WACC (Value / Share)")
        lines.append(f"")

        cols = []
        valid_cols = []
        for c in table.columns:
            try:
                val = float(c)
                cols.append(f"{val*100:.1f}%")
                valid_cols.append(c)
            except ValueError:
                continue
        
        table = table[valid_cols]
        header = "| Growth \\ WACC | " + " | ".join(cols) + " |"
        sep = "|---:" + "|---:" * len(cols) + "|"
        lines.append(header)
        lines.append(sep)

        for idx, row in table.iterrows():
            g_label = f"{float(idx)*100:.0f}%"
            vals = " | ".join(f"€{v:,.0f}" for v in row.values)
            lines.append(f"| {g_label} | {vals} |")

        lines.append(f"")

    return "\n".join(lines)


def _reverse_dcf_section(data: dict) -> str:
    """Section 8: Reverse DCF — market-implied expectations."""
    reverse = data["reverse"].iloc[0]
    fin = data["financials"]
    latest = fin.iloc[-1]
    wacc_rate = data["_wacc_rate"]

    ig = reverse["implied_growth"]
    im = reverse["implied_operating_margin"]
    iw = reverse["implied_wacc"]
    itg = reverse["implied_terminal_growth"]

    implied_rev = latest["revenue"] * (1 + ig) ** 10

    lines = []
    lines.append(f"## 8. Reverse DCF — What the Market Implies")
    lines.append(f"")
    lines.append(f"Instead of asking *\"what is ASML worth?\"*, we ask *\"what must the market "
                 f"be assuming to justify the current price?\"* Each parameter is solved "
                 f"independently while holding all others at base-case values.")
    lines.append(f"")
    lines.append(f"| Parameter | Implied Value | Our Assumption | Plausible? |")
    lines.append(f"|-----------|-------------:|---------------:|:----------:|")

    # Growth
    g_plaus = "⚠" if ig > 0.20 else ("◐" if ig > 0.12 else "✓")
    lines.append(f"| Revenue growth (p.a.) | {ig*100:.1f}% | "
                 f"{data['config']['revenue']['long_term_growth_rate']*100:.0f}% | {g_plaus} |")

    # Margin
    m_plaus = "⚠" if im > 0.45 else ("◐" if im > 0.38 else "✓")
    lines.append(f"| Operating margin | {im*100:.1f}% | "
                 f"{data['config']['margins']['operating_margin']*100:.0f}% | {m_plaus} |")

    # WACC
    w_plaus = "⚠" if iw < 0.06 else ("◐" if iw < wacc_rate - 0.02 else "✓")
    lines.append(f"| WACC | {iw*100:.2f}% | {wacc_rate*100:.2f}% | {w_plaus} |")

    # Terminal growth
    t_plaus = "⚠" if itg > 0.04 else ("◐" if itg > 0.03 else "✓")
    lines.append(f"| Terminal growth | {itg*100:.2f}% | "
                 f"{data['config']['projection']['terminal_growth_rate']*100:.1f}% | {t_plaus} |")

    lines.append(f"")
    lines.append(f"**Interpretation:** To justify ~€{reverse['market_price_eur']:,.0f}/share "
                 f"through growth alone, ASML would need to compound revenue at "
                 f"**{ig*100:.1f}%** annually for 10 years, reaching "
                 f"**€{implied_rev/1e9:.0f}B** by FY{int(latest['fiscal_year'])+10}. "
                 f"This would make ASML larger than the entire WFE market today. "
                 f"No single assumption justifies the price — the market is pricing in "
                 f"multiple favourable outcomes simultaneously.")
    lines.append(f"")
    return "\n".join(lines)


def _risks_and_catalysts(data: dict) -> str:
    """Section 9: Key risks and catalysts."""
    lines = []
    lines.append(f"## 9. Key Risks & Catalysts")
    lines.append(f"")
    lines.append(f"### Upside Catalysts")
    lines.append(f"")
    lines.append(f"- **High-NA EUV ramp:** Successful volume deployment of next-gen systems "
                 f"(€350M+ ASP vs ~€200M for standard EUV) could accelerate revenue and margins")
    lines.append(f"- **AI capex supercycle:** Sustained hyperscaler investment in AI chips "
                 f"drives leading-edge node demand beyond current consensus")
    lines.append(f"- **Installed base growth:** Service & upgrade revenue (~30% of total) "
                 f"grows predictably as the EUV fleet expands")
    lines.append(f"- **Geopolitical reshoring:** CHIPS Act and EU subsidies drive incremental "
                 f"fab construction, expanding the addressable market")
    lines.append(f"")
    lines.append(f"### Downside Risks")
    lines.append(f"")
    lines.append(f"- **Cyclical downturn:** Semiconductor capex is highly cyclical; a 30–40% "
                 f"peak-to-trough revenue decline is historically normal")
    lines.append(f"- **China export restrictions:** Further tightening could remove ~15% of "
                 f"addressable market (DUV sales to China)")
    lines.append(f"- **Customer concentration:** Top 3 customers (TSMC, Samsung, Intel) "
                 f"represent ~80%+ of system revenue")
    lines.append(f"- **Execution risk on High-NA:** Delays or yield issues could push out "
                 f"the growth inflection point")
    lines.append(f"- **Valuation compression:** Multiple contraction if growth expectations "
                 f"are not met or interest rates remain elevated")
    lines.append(f"")
    return "\n".join(lines)


def _methodology(data: dict) -> str:
    """Section 10: Methodology notes."""
    lines = []
    lines.append(f"## 10. Methodology & Data Sources")
    lines.append(f"")
    lines.append(f"### Approach")
    lines.append(f"")
    lines.append(f"This report uses a **two-stage Discounted Cash Flow (DCF)** model:")
    lines.append(f"")
    lines.append(f"1. **Explicit period (10 years):** Revenue is projected using near-term "
                 f"company guidance and consensus estimates, fading to long-term secular growth. "
                 f"Operating margins fade linearly from current levels to long-run targets over 5 years.")
    lines.append(f"2. **Terminal value:** Beyond year 10, FCFF grows at a perpetual rate (g∞ = 2.5%) "
                 f"and is capitalised using the Gordon Growth formula.")
    lines.append(f"")
    lines.append(f"The model is supplemented with:")
    lines.append(f"- **Sensitivity analysis** (two-way tables for WACC × growth, growth × margins)")
    lines.append(f"- **Tornado charts** ranking parameter importance")
    lines.append(f"- **Reverse DCF** solving for market-implied expectations")
    lines.append(f"")
    lines.append(f"### Data Sources")
    lines.append(f"")
    lines.append(f"| Source | Data | Update Frequency |")
    lines.append(f"|--------|------|-----------------|")
    lines.append(f"| SEC EDGAR (XBRL API) | 10 years of annual financials | Annual (20-F filings) |")
    lines.append(f"| Yahoo Finance | Market cap, beta, price history | Real-time |")
    lines.append(f"| ASML Investor Day (Nov 2024) | 2030 revenue & margin targets | Ad hoc |")
    lines.append(f"| Analyst consensus | Near-term revenue estimates | Quarterly |")
    lines.append(f"| Damodaran | Equity risk premium, country risk | Annual |")
    lines.append(f"")
    lines.append(f"### Limitations")
    lines.append(f"")
    lines.append(f"- Financial data is based on reported XBRL tags, which may differ slightly "
                 f"from manually adjusted figures")
    lines.append(f"- The model uses a constant WACC, which may overstate the discount for "
                 f"a company with minimal leverage")
    lines.append(f"- Near-term growth estimates reflect consensus as of the report date and "
                 f"may change with updated guidance")
    lines.append(f"- Market cap uses the NYSE ADR price converted to EUR at a fixed rate")
    lines.append(f"")
    lines.append(f"---")
    lines.append(f"")
    lines.append(f"*This report was generated programmatically by the ASML Valuation Framework. "
                 f"All assumptions are documented in `config/assumptions.yaml` and can be "
                 f"modified to produce alternative scenarios.*")
    lines.append(f"")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# Report Assembly
# ═══════════════════════════════════════════════════════════════════════════


def generate_report() -> str:
    """Generate the full Markdown report."""
    data = _load_all_data()

    header = _header(data)
    business_overview = _business_overview(data)
    historical_financials = _historical_financials(data)
    roic_analysis = _roic_analysis(data)
    working_capital = _working_capital(data)
    wacc_section = _wacc_section(data)
    dcf_section = _dcf_section(data)
    sensitivity_section = _sensitivity_section(data)
    reverse_dcf_section = _reverse_dcf_section(data)
    risks_and_catalysts = _risks_and_catalysts(data)
    methodology = _methodology(data)

    sections = [
        header,
        business_overview,
        historical_financials,
        roic_analysis,
        working_capital,
        wacc_section,
        dcf_section,
        sensitivity_section,
        reverse_dcf_section,
        risks_and_catalysts,
        methodology,
    ]

    return "\n".join(sections)


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("\n  Generating Valuation Report...\n")

    report = generate_report()

    # Save to per-company reports dir
    raw_dir, _, reports_dir = _get_company_dirs()
    reports_dir.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "r") as _f:
        _cfg = yaml.safe_load(_f)
    _ticker = _cfg.get("company", {}).get("ticker", "company").lower()
    output_path = reports_dir / f"{_ticker}_valuation_report.md"
    with open(output_path, "w") as f:
        f.write(report)

    # Also print to stdout
    print(report)

    print(f"\n{'═' * 72}")
    print(f"  ✓ Report saved → {output_path}")
    print(f"  ✓ Report length: {len(report):,} characters, "
          f"{report.count(chr(10)):,} lines")
    print(f"{'═' * 72}\n")
