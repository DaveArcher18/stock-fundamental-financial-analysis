"""
ASML Corporate Valuation Framework — Main Orchestrator
========================================================
Single entry point that runs the entire pipeline end-to-end:

    python main.py [--skip-extract] [--skip-analysis] [--skip-sensitivity]

Pipeline stages:
    ┌───────────────────────────────────────────────────────────┐
    │  1. CONFIGURATION   Load assumptions.yaml                │
    │  2. EXTRACTION      SEC XBRL + Yahoo Finance market data │
    │  3. ANALYSIS        Ratios, ROIC, working capital        │
    │  4. WACC            Config-driven and data-driven        │
    │  5. DCF             FCFF projections + terminal value     │
    │  6. SENSITIVITY     Two-way tables + tornado chart       │
    │  7. REVERSE DCF     Market-implied expectations          │
    │  8. SUMMARY         Consolidated valuation report        │
    └───────────────────────────────────────────────────────────┘

All output is saved to data/processed/ and printed to stdout.
"""

import argparse
import os
import sys
import time
from pathlib import Path

import pandas as pd
import yaml

# ── Project paths ─────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
CONFIG_PATH = PROJECT_ROOT / "config" / "assumptions.yaml"

# Ensure output directories exist
RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def load_config() -> dict:
    """Load the central assumptions configuration."""
    with open(CONFIG_PATH, "r") as f:
        config = yaml.safe_load(f)
    return config


def _banner(title: str, stage: int, total: int = 8) -> None:
    """Print a stage banner."""
    bar = "█" * stage + "░" * (total - stage)
    print(f"\n{'═' * 72}")
    print(f"  [{bar}]  Stage {stage}/{total}: {title}")
    print(f"{'═' * 72}\n")


def _load_financials() -> pd.DataFrame:
    """Load the processed annual financials."""
    path = PROCESSED_DIR / "financials_annual.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"No financials found at {path}. "
            f"Run stage 2 (extraction) first."
        )
    return pd.read_csv(path, index_col=0, parse_dates=True)


def _load_market_cap() -> float:
    """Load market cap from company info CSV."""
    path = RAW_DIR / "asml_company_info.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"No company info at {path}. "
            f"Run stage 2 (extraction) first."
        )
    info = pd.read_csv(path)
    return float(info[info["field"] == "market_cap"]["value"].values[0])


# ═══════════════════════════════════════════════════════════════════════════
# Stage Functions
# ═══════════════════════════════════════════════════════════════════════════


def stage_1_config() -> dict:
    """Stage 1: Load configuration."""
    _banner("CONFIGURATION", 1)
    config = load_config()

    print(f"  Company:           {config['company']['name']}")
    print(f"  Ticker:            {config['company']['ticker']}")
    print(f"  Currency:          {config['company']['currency']}")
    print(f"  Explicit years:    {config['projection']['explicit_years']}")
    print(f"  Terminal growth:   {config['projection']['terminal_growth_rate']*100:.1f}%")
    print(f"  WACC beta:         {config['cost_of_capital']['beta']}")
    print(f"  Risk-free rate:    {config['cost_of_capital']['risk_free_rate']*100:.1f}%")

    near_term = config["revenue"].get("near_term_growth_rates", [])
    if near_term:
        near_str = ", ".join(f"{g*100:.1f}%" for g in near_term)
        print(f"  Near-term growth:  [{near_str}]")
    print(f"  Long-term growth:  {config['revenue']['long_term_growth_rate']*100:.1f}%")
    print(f"  Op. margin target: {config['margins']['operating_margin']*100:.0f}%")

    print(f"\n  ✓ Configuration loaded from {CONFIG_PATH}")
    return config


def stage_2_extraction(config: dict) -> None:
    """Stage 2: Data extraction (SEC XBRL + market data)."""
    _banner("DATA EXTRACTION", 2)

    ticker = config["company"]["ticker"]
    start_date = config["market_data"]["price_start_date"]

    # ── SEC XBRL ──
    print("  ── SEC EDGAR XBRL Extraction ──\n")
    try:
        from etl.extract_sec_xbrl import extract_xbrl_data
        xbrl_result = extract_xbrl_data(
            cik=config["sec"]["cik"],
            user_agent=config["sec"]["user_agent"],
        )
        print(f"  ✓ XBRL: {len(xbrl_result)} years of annual data extracted")
    except Exception as e:
        print(f"  ⚠ XBRL extraction failed: {e}")
        print(f"    (continuing with existing data if available)")

    # ── Market Data ──
    print("\n  ── Market Data (Yahoo Finance) ──\n")
    try:
        from etl.extract_market_data import run_market_extraction
        prices, company_info = run_market_extraction(
            ticker=ticker,
            start_date=start_date,
            output_dir=str(RAW_DIR),
        )
        print(f"  ✓ Price history: {len(prices)} trading days")
        print(f"  ✓ Company info saved")
    except Exception as e:
        print(f"  ⚠ Market data extraction failed: {e}")


def stage_3_analysis(config: dict) -> dict:
    """Stage 3: Financial analysis (ratios, ROIC, working capital)."""
    _banner("FINANCIAL ANALYSIS", 3)

    try:
        from processing.run_analysis import main as run_analysis_main
        run_analysis_main()
        print(f"\n  ✓ Analysis complete — results in {PROCESSED_DIR}/")
        return {"status": "ok"}
    except Exception as e:
        print(f"  ⚠ Analysis failed: {e}")
        import traceback; traceback.print_exc()
        return {"status": "failed", "error": str(e)}


def stage_4_wacc(config: dict) -> dict:
    """Stage 4: WACC computation."""
    _banner("WACC COMPUTATION", 4)

    from models.wacc import (
        compute_wacc_from_config,
        compute_wacc_from_data,
        print_wacc_summary,
    )

    financials = _load_financials()
    market_cap_usd = _load_market_cap()

    # Config-driven
    config_wacc = compute_wacc_from_config(config)
    print_wacc_summary(config_wacc, title="WACC (Config-Driven)")

    # Data-driven
    data_wacc = compute_wacc_from_data(
        config=config,
        financials=financials,
        market_cap_usd=market_cap_usd,
    )
    print_wacc_summary(data_wacc, title="WACC (Data-Driven)")

    # Compare
    diff = (data_wacc["wacc"] - config_wacc["wacc"]) * 100
    print(f"  ── Comparison ──")
    print(f"  Config WACC: {config_wacc['wacc']*100:.2f}%")
    print(f"  Data WACC:   {data_wacc['wacc']*100:.2f}%")
    print(f"  Difference:  {diff:+.2f}pp")
    print(f"  → Using data-driven WACC for DCF\n")

    return {
        "config": config_wacc,
        "data": data_wacc,
        "selected_wacc": data_wacc["wacc"],
    }


def stage_5_dcf(config: dict, wacc_rate: float) -> dict:
    """Stage 5: DCF valuation."""
    _banner("DCF VALUATION", 5)

    from models.dcf import run_dcf, print_dcf_summary

    financials = _load_financials()
    market_cap_usd = _load_market_cap()

    result = run_dcf(
        config=config,
        financials=financials,
        wacc_rate=wacc_rate,
        market_cap_usd=market_cap_usd,
    )
    print_dcf_summary(result)

    # Save
    result["projections"].to_csv(PROCESSED_DIR / "dcf_projections.csv", index=False)
    print(f"  ✓ Saved projections → {PROCESSED_DIR / 'dcf_projections.csv'}")

    return result


def stage_6_sensitivity(config: dict, wacc_rate: float) -> dict:
    """Stage 6: Sensitivity analysis."""
    _banner("SENSITIVITY ANALYSIS", 6)

    from models.sensitivity import (
        two_way_sensitivity,
        tornado_chart_data,
        _dcf_value_per_share,
        print_sensitivity_table,
        print_tornado,
    )

    financials = _load_financials()
    market_cap_usd = _load_market_cap()
    shares = financials.iloc[-1]["shares_outstanding"]
    market_price_eur = (market_cap_usd * 0.92) / shares

    base_params = {
        "financials": financials,
        "wacc_rate": wacc_rate,
        "terminal_growth": config["projection"]["terminal_growth_rate"],
        "growth_rate": config["revenue"]["long_term_growth_rate"],
        "operating_margin": config["margins"]["operating_margin"],
        "tax_rate": config["tax"]["effective_rate"],
        "capex_to_revenue": config["capital_intensity"]["capex_to_revenue"],
        "depreciation_to_revenue": config["capital_intensity"]["depreciation_to_revenue"],
        "nwc_to_revenue": config["capital_intensity"]["nwc_to_revenue"],
    }

    # ── Table 1: WACC × Terminal Growth ──
    wacc_range = sorted(set([0.07, 0.075, 0.08, 0.085, round(wacc_rate, 3), 0.095, 0.10, 0.105, 0.11]))
    tg_range = [0.015, 0.020, 0.025, 0.030, 0.035]

    table1 = two_way_sensitivity(
        _dcf_value_per_share, base_params,
        "wacc_rate", wacc_range,
        "terminal_growth", tg_range,
    )
    print_sensitivity_table(
        table1, "WACC", "Terminal Growth (g∞)",
        "TABLE 1: Value/Share — WACC × Terminal Growth",
        base_x=wacc_rate,
        base_y=config["projection"]["terminal_growth_rate"],
    )

    # ── Table 2: Growth × Margin ──
    growth_range = [0.04, 0.06, 0.08, 0.10, 0.12, 0.14, 0.16, 0.18]
    margin_range = [0.30, 0.32, 0.35, 0.38, 0.40]

    table2 = two_way_sensitivity(
        _dcf_value_per_share, base_params,
        "growth_rate", growth_range,
        "operating_margin", margin_range,
    )
    print_sensitivity_table(
        table2, "Revenue Growth", "Operating Margin",
        "TABLE 2: Value/Share — Revenue Growth × Operating Margin",
        base_x=config["revenue"]["long_term_growth_rate"],
        base_y=config["margins"]["operating_margin"],
    )

    # ── Table 3: Growth × WACC ──
    table3 = two_way_sensitivity(
        _dcf_value_per_share, base_params,
        "growth_rate", growth_range,
        "wacc_rate", wacc_range,
    )
    print_sensitivity_table(
        table3, "Revenue Growth", "WACC",
        "TABLE 3: Value/Share — Revenue Growth × WACC",
        base_x=config["revenue"]["long_term_growth_rate"],
        base_y=wacc_rate,
    )

    # ── Tornado ──
    tornado_specs = {
        "growth_rate":             (0.03,  0.18),
        "operating_margin":        (0.28,  0.42),
        "wacc_rate":               (0.07,  0.11),
        "terminal_growth":         (0.015, 0.035),
        "tax_rate":                (0.10,  0.20),
        "capex_to_revenue":        (0.04,  0.10),
        "nwc_to_revenue":          (0.10,  0.20),
    }
    tornado = tornado_chart_data(_dcf_value_per_share, base_params, tornado_specs)
    print_tornado(tornado, title="TORNADO: Impact on Value/Share")

    # ── Implied growth ──
    lo, hi = 0.01, 0.30
    for _ in range(50):
        mid = (lo + hi) / 2
        params = dict(base_params)
        params["growth_rate"] = mid
        val = _dcf_value_per_share(**params)
        if val < market_price_eur:
            lo = mid
        else:
            hi = mid
    implied_growth = (lo + hi) / 2

    print(f"{'═' * 72}")
    print(f"  To justify ~€{market_price_eur:,.0f}/share, ASML needs")
    print(f"  {implied_growth*100:.1f}% revenue growth p.a. for 10 years")
    print(f"{'═' * 72}\n")

    # Save
    table1.to_csv(PROCESSED_DIR / "sensitivity_wacc_tg.csv")
    table2.to_csv(PROCESSED_DIR / "sensitivity_growth_margin.csv")
    table3.to_csv(PROCESSED_DIR / "sensitivity_growth_wacc.csv")
    tornado.to_csv(PROCESSED_DIR / "tornado_analysis.csv", index=False)
    print(f"  ✓ Saved sensitivity tables → {PROCESSED_DIR}/")

    return {
        "tables": {"wacc_tg": table1, "growth_margin": table2, "growth_wacc": table3},
        "tornado": tornado,
        "implied_growth": implied_growth,
    }


def stage_7_reverse_dcf(config: dict, wacc_rate: float) -> dict:
    """Stage 7: Reverse DCF — market-implied expectations."""
    _banner("REVERSE DCF", 7)

    from models.reverse_engineering import (
        implied_growth_rate,
        implied_operating_margin,
        implied_wacc,
        implied_terminal_growth,
        print_reverse_dcf_summary,
    )

    financials = _load_financials()
    market_cap_usd = _load_market_cap()

    usd_eur = 0.92
    shares = financials.iloc[-1]["shares_outstanding"]
    market_cap_eur = market_cap_usd * usd_eur
    market_price_eur = market_cap_eur / shares
    latest = financials.iloc[-1]
    net_debt = latest["long_term_debt"] - latest["cash"]
    ev_eur = market_cap_eur + net_debt

    print(f"  Solving for market-implied parameters...\n")

    ig = implied_growth_rate(market_price_eur, financials, config, wacc_rate)
    print(f"  ✓ Implied growth:           {ig*100:.1f}%")

    im = implied_operating_margin(market_price_eur, financials, config, wacc_rate)
    print(f"  ✓ Implied operating margin:  {im*100:.1f}%")

    iw = implied_wacc(market_price_eur, financials, config)
    print(f"  ✓ Implied WACC:              {iw*100:.2f}%")

    itg = implied_terminal_growth(market_price_eur, financials, config, wacc_rate)
    print(f"  ✓ Implied terminal growth:   {itg*100:.2f}%")

    results = {
        "market": {
            "price_eur": market_price_eur,
            "market_cap_eur": market_cap_eur,
            "ev_eur": ev_eur,
        },
        "implied": {
            "growth_rate": ig,
            "operating_margin": im,
            "wacc": iw,
            "terminal_growth": itg,
        },
        "base_revenue": latest["revenue"],
        "current_op_margin": latest["operating_income"] / latest["revenue"],
        "actual_wacc": wacc_rate,
        "config_tg": config["projection"]["terminal_growth_rate"],
    }

    print_reverse_dcf_summary(results)

    # Save
    summary_df = pd.DataFrame([{
        "market_price_eur": market_price_eur,
        "implied_growth": ig,
        "implied_operating_margin": im,
        "implied_wacc": iw,
        "implied_terminal_growth": itg,
        "actual_wacc": wacc_rate,
    }])
    summary_df.to_csv(PROCESSED_DIR / "reverse_dcf_implied.csv", index=False)
    print(f"  ✓ Saved → {PROCESSED_DIR / 'reverse_dcf_implied.csv'}")

    return results


def stage_8_summary(config: dict, wacc_result: dict, dcf_result: dict,
                     sensitivity_result: dict, reverse_result: dict) -> None:
    """Stage 8: Consolidated summary."""
    _banner("VALUATION SUMMARY", 8)

    eq = dcf_result["equity"]
    ev = dcf_result["ev"]
    mkt = dcf_result.get("market", {})
    inputs = dcf_result["inputs"]
    implied = reverse_result.get("implied", {})

    width = 72
    print(f"  {'─' * (width - 4)}")
    print(f"  ASML Holding N.V. — Intrinsic Valuation")
    print(f"  Date: {time.strftime('%Y-%m-%d')}")
    print(f"  {'─' * (width - 4)}")

    print(f"\n  ── Valuation Output ──")
    print(f"  Enterprise Value:     €{ev['enterprise_value']/1e9:.1f}B")
    print(f"  Equity Value:         €{eq['equity_value']/1e9:.1f}B")
    print(f"  Intrinsic Value/Shr:  €{eq['value_per_share']:.2f}")

    if mkt:
        upside = mkt["upside_pct"]
        arrow = "▲" if upside > 0 else "▼"
        print(f"\n  Market Price:         ~€{mkt['market_price_per_share_eur']:.2f}")
        print(f"  Upside/Downside:      {arrow} {upside:+.1f}%")

    print(f"\n  ── Key Assumptions ──")
    print(f"  WACC:                 {inputs['wacc']*100:.2f}%")
    print(f"  Terminal growth:      {inputs['terminal_growth']*100:.1f}%")
    print(f"  FY2034 revenue:       €{dcf_result['projections'].iloc[-1]['revenue']/1e9:.0f}B")
    print(f"  Terminal op. margin:  {inputs['target_op_margin']*100:.0f}%")
    print(f"  TV as % of EV:        {ev['terminal_pct']:.0f}%")

    print(f"\n  ── What the Market Implies ──")
    print(f"  Implied growth:       {implied.get('growth_rate', 0)*100:.1f}% p.a.")
    print(f"  Implied margin:       {implied.get('operating_margin', 0)*100:.1f}%")
    print(f"  Implied WACC:         {implied.get('wacc', 0)*100:.2f}%")

    print(f"\n  ── Tornado: Top 3 Value Drivers ──")
    tornado = sensitivity_result.get("tornado")
    if tornado is not None:
        for _, row in tornado.head(3).iterrows():
            print(f"    {row['parameter']:<25s}  swing: €{row['swing']:,.0f}")

    # Overall verdict
    if mkt:
        upside = mkt["upside_pct"]
        if upside > 20:
            verdict = "STRONG BUY  — significant margin of safety"
        elif upside > 10:
            verdict = "BUY  — modest upside with defensible assumptions"
        elif upside > -10:
            verdict = "HOLD — trading near intrinsic value"
        elif upside > -20:
            verdict = "REDUCE — modestly overvalued"
        else:
            verdict = "OVERVALUED — market pricing in aggressive expectations"

        print(f"\n  {'═' * (width - 4)}")
        print(f"  ▸ VERDICT: {verdict}")
        print(f"  {'═' * (width - 4)}")

    # Files produced
    print(f"\n  ── Output Files ──")
    output_files = [
        "financials_annual.csv",
        "financial_ratios.csv",
        "roic_analysis.csv",
        "working_capital.csv",
        "dcf_projections.csv",
        "sensitivity_wacc_tg.csv",
        "sensitivity_growth_margin.csv",
        "sensitivity_growth_wacc.csv",
        "tornado_analysis.csv",
        "reverse_dcf_implied.csv",
    ]
    for f in output_files:
        p = PROCESSED_DIR / f
        status = "✓" if p.exists() else "✗"
        print(f"    {status} {f}")

    print(f"\n{'═' * width}")
    print(f"  Pipeline complete. All outputs saved to {PROCESSED_DIR}/")
    print(f"{'═' * width}\n")


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════


def main() -> None:
    """Run the full ASML valuation pipeline."""

    parser = argparse.ArgumentParser(
        description="ASML Corporate Valuation Framework",
    )
    parser.add_argument(
        "--skip-extract", action="store_true",
        help="Skip data extraction (use existing data files)",
    )
    parser.add_argument(
        "--skip-analysis", action="store_true",
        help="Skip financial analysis stage",
    )
    parser.add_argument(
        "--skip-sensitivity", action="store_true",
        help="Skip sensitivity + reverse DCF (faster)",
    )
    args = parser.parse_args()

    start_time = time.time()

    print(f"\n{'═' * 72}")
    print(f"  ╔══════════════════════════════════════════════════════╗")
    print(f"  ║   ASML CORPORATE VALUATION FRAMEWORK                ║")
    print(f"  ║   End-to-End Pipeline                               ║")
    print(f"  ╚══════════════════════════════════════════════════════╝")
    print(f"{'═' * 72}")

    # ── Stage 1: Configuration ────────────────────────────────────────
    config = stage_1_config()

    # ── Stage 2: Extraction ───────────────────────────────────────────
    if not args.skip_extract:
        stage_2_extraction(config)
    else:
        _banner("DATA EXTRACTION (SKIPPED)", 2)
        print("  → Using existing data files")

    # ── Stage 3: Analysis ─────────────────────────────────────────────
    if not args.skip_analysis:
        stage_3_analysis(config)
    else:
        _banner("FINANCIAL ANALYSIS (SKIPPED)", 3)
        print("  → Using existing analysis files")

    # ── Stage 4: WACC ─────────────────────────────────────────────────
    wacc_result = stage_4_wacc(config)
    selected_wacc = wacc_result["selected_wacc"]

    # ── Stage 5: DCF ──────────────────────────────────────────────────
    dcf_result = stage_5_dcf(config, selected_wacc)

    # ── Stage 6 & 7: Sensitivity + Reverse DCF ────────────────────────
    sensitivity_result = {}
    reverse_result = {}

    if not args.skip_sensitivity:
        sensitivity_result = stage_6_sensitivity(config, selected_wacc)
        reverse_result = stage_7_reverse_dcf(config, selected_wacc)
    else:
        _banner("SENSITIVITY & REVERSE DCF (SKIPPED)", 6)
        print("  → Run without --skip-sensitivity for full analysis")

    # ── Stage 8: Summary ──────────────────────────────────────────────
    stage_8_summary(config, wacc_result, dcf_result,
                     sensitivity_result, reverse_result)

    elapsed = time.time() - start_time
    print(f"  Total runtime: {elapsed:.1f}s\n")


if __name__ == "__main__":
    main()
