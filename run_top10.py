#!/usr/bin/env python3
"""
Run the valuation pipeline for the top 10 S&P 500 companies.

Usage:
    python run_top10.py              # Run all 10
    python run_top10.py AAPL MSFT    # Run specific tickers only

Each company gets its own output folder: output/{TICKER}/
The original config/assumptions.yaml is backed up and restored after all runs.
"""

import os
import sys
import shutil
import subprocess
import time
import yaml
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = PROJECT_ROOT / "config" / "assumptions.yaml"
BACKUP_PATH = PROJECT_ROOT / "config" / "assumptions.yaml.backup"

# ═══════════════════════════════════════════════════════════════════════════
# Company Configurations
# ═══════════════════════════════════════════════════════════════════════════

# Common US market parameters (Feb 2026)
US_DEFAULTS = {
    "risk_free_rate": 0.045,        # 10y US Treasury ~4.5%
    "equity_risk_premium": 0.05,    # Damodaran mature market ERP
    "country_risk_premium": 0.0,    # US = 0
    "benchmark_ticker": "^GSPC",    # S&P 500
    "base_url": "https://data.sec.gov/api/xbrl/companyfacts",
    "annual_forms": ["10-K", "10-K/A"],
    "years_to_keep": 10,
    "price_start_date": "2000-01-01",
    "user_agent": "StockValuation research@example.com",
    "marginal_rate": 0.21,          # US federal corporate rate
}


COMPANIES = {
    # ──────────────────────────────────────────────────────────────────────
    # 1. APPLE
    # ──────────────────────────────────────────────────────────────────────
    "AAPL": {
        "company": {
            "name": "Apple Inc.",
            "ticker": "AAPL",
            "currency": "USD",
            "fiscal_year_end": "September",
        },
        "tax": {
            "effective_rate": 0.16,
            "marginal_rate": 0.21,
        },
        "cost_of_capital": {
            "risk_free_rate": 0.045,
            "equity_risk_premium": 0.05,
            "beta": 0.87,
            "country_risk_premium": 0.0,
            "pre_tax_cost_of_debt": 0.035,
            "target_debt_to_capital": 0.55,
            # CALIBRATION: Apple uses significant leverage for buybacks.
            # D/(D+E) ~55%. Beta 0.87 (Yahoo, 5y). Effective tax ~16%
            # (global IP structuring). Gross margin guided 47-49%.
        },
        "projection": {
            "explicit_years": 10,
            "terminal_growth_rate": 0.025,
        },
        "revenue": {
            "base_year_revenue": None,
            "near_term_growth_rates": [
                0.057,  # Yr 1: +5.7% — FY2025 consensus
                0.070,  # Yr 2: +7.0% — FY2026 consensus
                0.065,  # Yr 3: +6.5% — Services + India/SE Asia
                0.060,  # Yr 4: +6.0% — maturing hardware cycle
                0.050,  # Yr 5: +5.0% — steady state approaching
            ],
            "long_term_growth_rate": 0.04,
        },
        "margins": {
            "gross_margin": 0.47,
            "operating_margin": 0.35,
            "rd_to_revenue": 0.07,
            "sga_to_revenue": 0.06,
        },
        "capital_intensity": {
            "capex_to_revenue": 0.03,
            "depreciation_to_revenue": 0.03,
            "nwc_to_revenue": -0.05,
            # Apple has NEGATIVE working capital — collects before paying
        },
        "working_capital_days": {"dso": 60, "dio": 10, "dpo": 105},
        "roic": {"capitalize_rd": False, "rd_amortization_years": 5},
        "sensitivity": {
            "wacc_range": [0.06, 0.065, 0.07, 0.075, 0.08, 0.085, 0.09, 0.095, 0.10],
            "terminal_growth_range": [0.015, 0.020, 0.025, 0.030, 0.035],
        },
        "market_data": {"price_start_date": "2000-01-01", "benchmark_ticker": "^GSPC"},
        "sec": {
            "cik": "0000320193",
            "user_agent": "StockValuation research@example.com",
            "base_url": "https://data.sec.gov/api/xbrl/companyfacts",
            "annual_forms": ["10-K", "10-K/A"],
            "years_to_keep": 10,
        },
        "_calibration": (
            "APPLE (Feb 2026): FY ends Sep. Revenue ~$415B FY2025. "
            "β=0.87 (5y Yahoo). Operating margin 35%. Gross margin guided 47-49%. "
            "Massive buyback program funded by ~$100B annual FCF. "
            "Services growing ~15%/yr (>$100B run rate). Hardware ~flat. "
            "D/(D+E) ~55% — significant leverage for capital returns."
        ),
    },

    # ──────────────────────────────────────────────────────────────────────
    # 2. MICROSOFT
    # ──────────────────────────────────────────────────────────────────────
    "MSFT": {
        "company": {
            "name": "Microsoft Corporation",
            "ticker": "MSFT",
            "currency": "USD",
            "fiscal_year_end": "June",
        },
        "tax": {
            "effective_rate": 0.18,
            "marginal_rate": 0.21,
        },
        "cost_of_capital": {
            "risk_free_rate": 0.045,
            "equity_risk_premium": 0.05,
            "beta": 1.08,
            "country_risk_premium": 0.0,
            "pre_tax_cost_of_debt": 0.03,
            "target_debt_to_capital": 0.15,
        },
        "projection": {
            "explicit_years": 10,
            "terminal_growth_rate": 0.03,
        },
        "revenue": {
            "base_year_revenue": None,
            "near_term_growth_rates": [
                0.160,  # Yr 1: +16% — FY2026 (Azure AI + Copilot ramp)
                0.150,  # Yr 2: +15% — continued cloud acceleration
                0.140,  # Yr 3: +14% — Azure at scale, gaming steady
                0.120,  # Yr 4: +12% — gradual normalisation
                0.100,  # Yr 5: +10% — mature cloud growth
            ],
            "long_term_growth_rate": 0.06,
        },
        "margins": {
            "gross_margin": 0.70,
            "operating_margin": 0.46,
            "rd_to_revenue": 0.12,
            "sga_to_revenue": 0.12,
        },
        "capital_intensity": {
            "capex_to_revenue": 0.17,
            "depreciation_to_revenue": 0.07,
            "nwc_to_revenue": 0.05,
        },
        "working_capital_days": {"dso": 82, "dio": 15, "dpo": 65},
        "roic": {"capitalize_rd": False, "rd_amortization_years": 5},
        "sensitivity": {
            "wacc_range": [0.07, 0.075, 0.08, 0.085, 0.09, 0.095, 0.10, 0.105, 0.11],
            "terminal_growth_range": [0.015, 0.020, 0.025, 0.030, 0.035],
        },
        "market_data": {"price_start_date": "2000-01-01", "benchmark_ticker": "^GSPC"},
        "sec": {
            "cik": "0000789019",
            "user_agent": "StockValuation research@example.com",
            "base_url": "https://data.sec.gov/api/xbrl/companyfacts",
            "annual_forms": ["10-K", "10-K/A"],
            "years_to_keep": 10,
        },
        "_calibration": (
            "MICROSOFT (Feb 2026): FY ends June. Revenue ~$280B FY2025. "
            "β=1.08. OpM 46%. Azure growth ~30%+ (AI-driven). "
            "Capex surging to ~$80B/yr for AI infrastructure. "
            "Copilot monetisation inflecting. Gaming (Activision) integrated."
        ),
    },

    # ──────────────────────────────────────────────────────────────────────
    # 3. NVIDIA
    # ──────────────────────────────────────────────────────────────────────
    "NVDA": {
        "company": {
            "name": "NVIDIA Corporation",
            "ticker": "NVDA",
            "currency": "USD",
            "fiscal_year_end": "January",
        },
        "tax": {
            "effective_rate": 0.12,
            "marginal_rate": 0.21,
        },
        "cost_of_capital": {
            "risk_free_rate": 0.045,
            "equity_risk_premium": 0.05,
            "beta": 1.90,
            "country_risk_premium": 0.0,
            "pre_tax_cost_of_debt": 0.03,
            "target_debt_to_capital": 0.10,
        },
        "projection": {
            "explicit_years": 10,
            "terminal_growth_rate": 0.035,
        },
        "revenue": {
            "base_year_revenue": None,
            "near_term_growth_rates": [
                0.370,  # Yr 1: +37% — FY2026 (Blackwell ramp)
                0.250,  # Yr 2: +25% — continued hyperscaler demand
                0.200,  # Yr 3: +20% — enterprise AI adoption
                0.150,  # Yr 4: +15% — market broadening
                0.120,  # Yr 5: +12% — competition from custom silicon
            ],
            "long_term_growth_rate": 0.08,
        },
        "margins": {
            "gross_margin": 0.73,
            "operating_margin": 0.60,
            "rd_to_revenue": 0.10,
            "sga_to_revenue": 0.03,
        },
        "capital_intensity": {
            "capex_to_revenue": 0.05,
            "depreciation_to_revenue": 0.03,
            "nwc_to_revenue": 0.15,
        },
        "working_capital_days": {"dso": 55, "dio": 95, "dpo": 35},
        "roic": {"capitalize_rd": False, "rd_amortization_years": 5},
        "sensitivity": {
            "wacc_range": [0.10, 0.11, 0.12, 0.13, 0.14, 0.15, 0.16, 0.17, 0.18],
            "terminal_growth_range": [0.020, 0.025, 0.030, 0.035, 0.040],
        },
        "market_data": {"price_start_date": "2000-01-01", "benchmark_ticker": "^GSPC"},
        "sec": {
            "cik": "0001045810",
            "user_agent": "StockValuation research@example.com",
            "base_url": "https://data.sec.gov/api/xbrl/companyfacts",
            "annual_forms": ["10-K", "10-K/A"],
            "years_to_keep": 10,
        },
        "_calibration": (
            "NVIDIA (Feb 2026): FY ends Jan. Revenue ~$130B FY2025. "
            "β=1.90. OpM 62%. Data centre is 85%+ of revenue. "
            "Blackwell cycling at max capacity. Gross margins 73-75%. "
            "High WACC range (14%+) reflects extreme cyclicality risk."
        ),
    },

    # ──────────────────────────────────────────────────────────────────────
    # 4. AMAZON
    # ──────────────────────────────────────────────────────────────────────
    "AMZN": {
        "company": {
            "name": "Amazon.com, Inc.",
            "ticker": "AMZN",
            "currency": "USD",
            "fiscal_year_end": "December",
        },
        "tax": {
            "effective_rate": 0.12,
            "marginal_rate": 0.21,
        },
        "cost_of_capital": {
            "risk_free_rate": 0.045,
            "equity_risk_premium": 0.05,
            "beta": 1.22,
            "country_risk_premium": 0.0,
            "pre_tax_cost_of_debt": 0.035,
            "target_debt_to_capital": 0.15,
        },
        "projection": {
            "explicit_years": 10,
            "terminal_growth_rate": 0.03,
        },
        "revenue": {
            "base_year_revenue": None,
            "near_term_growth_rates": [
                0.120,  # Yr 1: +12% — 2026 consensus
                0.115,  # Yr 2: +11.5% — AWS + ads driving mix shift
                0.110,  # Yr 3: +11% — retail maturing, cloud scaling
                0.100,  # Yr 4: +10% — gradual deceleration
                0.090,  # Yr 5: +9%  — $1T+ revenue base effect
            ],
            "long_term_growth_rate": 0.06,
        },
        "margins": {
            "gross_margin": 0.50,
            "operating_margin": 0.14,
            "rd_to_revenue": 0.14,
            "sga_to_revenue": 0.07,
        },
        "capital_intensity": {
            "capex_to_revenue": 0.14,
            "depreciation_to_revenue": 0.07,
            "nwc_to_revenue": -0.08,
            # Amazon has negative NWC — collects days before paying suppliers
        },
        "working_capital_days": {"dso": 25, "dio": 35, "dpo": 75},
        "roic": {"capitalize_rd": False, "rd_amortization_years": 5},
        "sensitivity": {
            "wacc_range": [0.08, 0.085, 0.09, 0.095, 0.10, 0.105, 0.11, 0.115, 0.12],
            "terminal_growth_range": [0.020, 0.025, 0.030, 0.035, 0.040],
        },
        "market_data": {"price_start_date": "2000-01-01", "benchmark_ticker": "^GSPC"},
        "sec": {
            "cik": "0001018724",
            "user_agent": "StockValuation research@example.com",
            "base_url": "https://data.sec.gov/api/xbrl/companyfacts",
            "annual_forms": ["10-K", "10-K/A"],
            "years_to_keep": 10,
        },
        "_calibration": (
            "AMAZON (Feb 2026): FY ends Dec. Revenue ~$638B 2024, ~$717B 2025E. "
            "β=1.22. OpM 14% expanding toward 18% (AWS + ads mix shift). "
            "AWS growing ~20%, advertising ~25%. $200B capex in 2026 for AI infra. "
            "Negative NWC — cash-generative working capital model."
        ),
    },

    # ──────────────────────────────────────────────────────────────────────
    # 5. ALPHABET
    # ──────────────────────────────────────────────────────────────────────
    "GOOGL": {
        "company": {
            "name": "Alphabet Inc.",
            "ticker": "GOOGL",
            "currency": "USD",
            "fiscal_year_end": "December",
        },
        "tax": {
            "effective_rate": 0.15,
            "marginal_rate": 0.21,
        },
        "cost_of_capital": {
            "risk_free_rate": 0.045,
            "equity_risk_premium": 0.05,
            "beta": 1.09,
            "country_risk_premium": 0.0,
            "pre_tax_cost_of_debt": 0.03,
            "target_debt_to_capital": 0.05,
        },
        "projection": {
            "explicit_years": 10,
            "terminal_growth_rate": 0.03,
        },
        "revenue": {
            "base_year_revenue": None,
            "near_term_growth_rates": [
                0.140,  # Yr 1: +14% — 2026 consensus (search + cloud + AI)
                0.130,  # Yr 2: +13% — Cloud scaling, AI Overviews monetisation
                0.110,  # Yr 3: +11% — YouTube + subscriptions growth
                0.090,  # Yr 4: +9%  — regulatory headwinds possible
                0.080,  # Yr 5: +8%  — maturing ad market share
            ],
            "long_term_growth_rate": 0.05,
        },
        "margins": {
            "gross_margin": 0.58,
            "operating_margin": 0.32,
            "rd_to_revenue": 0.14,
            "sga_to_revenue": 0.10,
        },
        "capital_intensity": {
            "capex_to_revenue": 0.15,
            "depreciation_to_revenue": 0.07,
            "nwc_to_revenue": 0.05,
        },
        "working_capital_days": {"dso": 58, "dio": 0, "dpo": 18},
        "roic": {"capitalize_rd": False, "rd_amortization_years": 5},
        "sensitivity": {
            "wacc_range": [0.07, 0.075, 0.08, 0.085, 0.09, 0.095, 0.10, 0.105, 0.11],
            "terminal_growth_range": [0.020, 0.025, 0.030, 0.035, 0.040],
        },
        "market_data": {"price_start_date": "2000-01-01", "benchmark_ticker": "^GSPC"},
        "sec": {
            "cik": "0001652044",
            "user_agent": "StockValuation research@example.com",
            "base_url": "https://data.sec.gov/api/xbrl/companyfacts",
            "annual_forms": ["10-K", "10-K/A"],
            "years_to_keep": 10,
        },
        "_calibration": (
            "ALPHABET (Feb 2026): FY ends Dec. Revenue $403B 2025. "
            "β=1.09. OpM 32%. Google Cloud reached 30%+ operating margin. "
            "Search still 60%+ of revenue. $175-185B capex in 2026 for AI. "
            "Antitrust risk: DOJ remedy could force Chrome/search divestiture."
        ),
    },

    # ──────────────────────────────────────────────────────────────────────
    # 6. META
    # ──────────────────────────────────────────────────────────────────────
    "META": {
        "company": {
            "name": "Meta Platforms, Inc.",
            "ticker": "META",
            "currency": "USD",
            "fiscal_year_end": "December",
        },
        "tax": {
            "effective_rate": 0.13,
            "marginal_rate": 0.21,
        },
        "cost_of_capital": {
            "risk_free_rate": 0.045,
            "equity_risk_premium": 0.05,
            "beta": 1.28,
            "country_risk_premium": 0.0,
            "pre_tax_cost_of_debt": 0.04,
            "target_debt_to_capital": 0.10,
        },
        "projection": {
            "explicit_years": 10,
            "terminal_growth_rate": 0.03,
        },
        "revenue": {
            "base_year_revenue": None,
            "near_term_growth_rates": [
                0.220,  # Yr 1: +22% — 2026 (AI ad targeting + Reels)
                0.180,  # Yr 2: +18% — continued AI monetisation
                0.150,  # Yr 3: +15% — WhatsApp business ramp
                0.120,  # Yr 4: +12% — Reality Labs still investing
                0.100,  # Yr 5: +10% — maturing social ad market
            ],
            "long_term_growth_rate": 0.06,
        },
        "margins": {
            "gross_margin": 0.82,
            "operating_margin": 0.40,
            "rd_to_revenue": 0.28,
            "sga_to_revenue": 0.13,
        },
        "capital_intensity": {
            "capex_to_revenue": 0.25,
            "depreciation_to_revenue": 0.08,
            "nwc_to_revenue": 0.05,
        },
        "working_capital_days": {"dso": 50, "dio": 0, "dpo": 15},
        "roic": {"capitalize_rd": False, "rd_amortization_years": 5},
        "sensitivity": {
            "wacc_range": [0.08, 0.085, 0.09, 0.095, 0.10, 0.105, 0.11, 0.115, 0.12],
            "terminal_growth_range": [0.020, 0.025, 0.030, 0.035, 0.040],
        },
        "market_data": {"price_start_date": "2012-05-18", "benchmark_ticker": "^GSPC"},
        "sec": {
            "cik": "0001326801",
            "user_agent": "StockValuation research@example.com",
            "base_url": "https://data.sec.gov/api/xbrl/companyfacts",
            "annual_forms": ["10-K", "10-K/A"],
            "years_to_keep": 10,
        },
        "_calibration": (
            "META (Feb 2026): FY ends Dec. Revenue $201B 2025. "
            "β=1.28. OpM 41%. Family of Apps operates at ~50% OpM. "
            "Reality Labs losing ~$15B/yr. Capex surging to ~$60B for AI. "
            "R&D/rev 28% is high due to metaverse investment."
        ),
    },

    # ──────────────────────────────────────────────────────────────────────
    # 7. TESLA
    # ──────────────────────────────────────────────────────────────────────
    "TSLA": {
        "company": {
            "name": "Tesla, Inc.",
            "ticker": "TSLA",
            "currency": "USD",
            "fiscal_year_end": "December",
        },
        "tax": {
            "effective_rate": 0.10,
            "marginal_rate": 0.21,
        },
        "cost_of_capital": {
            "risk_free_rate": 0.045,
            "equity_risk_premium": 0.05,
            "beta": 1.74,
            "country_risk_premium": 0.0,
            "pre_tax_cost_of_debt": 0.05,
            "target_debt_to_capital": 0.05,
        },
        "projection": {
            "explicit_years": 10,
            "terminal_growth_rate": 0.03,
        },
        "revenue": {
            "base_year_revenue": None,
            "near_term_growth_rates": [
                0.170,  # Yr 1: +17% — 2026 (new compact model + recovery)
                0.200,  # Yr 2: +20% — affordable Tesla ramp + energy storage
                0.180,  # Yr 3: +18% — volume growth + FSD licensing
                0.150,  # Yr 4: +15% — continued expansion
                0.120,  # Yr 5: +12% — market share maturation
            ],
            "long_term_growth_rate": 0.06,
        },
        "margins": {
            "gross_margin": 0.18,
            "operating_margin": 0.12,
            "rd_to_revenue": 0.06,
            "sga_to_revenue": 0.04,
            # Target OpM 12% assumes margin recovery from current 5% trough
            # as volumes scale and cost-per-unit improves
        },
        "capital_intensity": {
            "capex_to_revenue": 0.13,
            "depreciation_to_revenue": 0.07,
            "nwc_to_revenue": 0.05,
        },
        "working_capital_days": {"dso": 15, "dio": 50, "dpo": 65},
        "roic": {"capitalize_rd": False, "rd_amortization_years": 5},
        "sensitivity": {
            "wacc_range": [0.10, 0.11, 0.12, 0.13, 0.14, 0.15, 0.16, 0.17, 0.18],
            "terminal_growth_range": [0.020, 0.025, 0.030, 0.035, 0.040],
        },
        "market_data": {"price_start_date": "2010-06-29", "benchmark_ticker": "^GSPC"},
        "sec": {
            "cik": "0001318605",
            "user_agent": "StockValuation research@example.com",
            "base_url": "https://data.sec.gov/api/xbrl/companyfacts",
            "annual_forms": ["10-K", "10-K/A"],
            "years_to_keep": 10,
        },
        "_calibration": (
            "TESLA (Feb 2026): FY ends Dec. Revenue ~$95B 2025 (-3% YoY). "
            "β=1.74. OpM compressed to 5% (from 17% in 2022). "
            "Price wars + AI/robotics investment crushing near-term margins. "
            "Market prices in Robotaxi + Optimus — DCF captures core auto only. "
            "NOTE: DCF will show significant overvaluation vs ~$350 market price."
        ),
    },

    # ──────────────────────────────────────────────────────────────────────
    # 8. BROADCOM
    # ──────────────────────────────────────────────────────────────────────
    "AVGO": {
        "company": {
            "name": "Broadcom Inc.",
            "ticker": "AVGO",
            "currency": "USD",
            "fiscal_year_end": "October",
        },
        "tax": {
            "effective_rate": 0.10,
            "marginal_rate": 0.21,
        },
        "cost_of_capital": {
            "risk_free_rate": 0.045,
            "equity_risk_premium": 0.05,
            "beta": 1.21,
            "country_risk_premium": 0.0,
            "pre_tax_cost_of_debt": 0.045,
            "target_debt_to_capital": 0.35,
            # Significant leverage from VMware acquisition
        },
        "projection": {
            "explicit_years": 10,
            "terminal_growth_rate": 0.03,
        },
        "revenue": {
            "base_year_revenue": None,
            "near_term_growth_rates": [
                0.280,  # Yr 1: +28% — FY2026 (AI semis + VMware synergies)
                0.200,  # Yr 2: +20% — custom AI accelerator ramp
                0.150,  # Yr 3: +15% — continued AI infrastructure
                0.120,  # Yr 4: +12% — broadening customer base
                0.100,  # Yr 5: +10% — maturing AI cycle
            ],
            "long_term_growth_rate": 0.06,
        },
        "margins": {
            "gross_margin": 0.75,
            "operating_margin": 0.45,
            "rd_to_revenue": 0.20,
            "sga_to_revenue": 0.05,
            # GAAP OpM ~35-40% due to VMware intangible amortisation.
            # Cash operating margin ~65%+. We use 45% as conservative GAAP target.
        },
        "capital_intensity": {
            "capex_to_revenue": 0.04,
            "depreciation_to_revenue": 0.15,
            "nwc_to_revenue": 0.10,
            # High D&A from VMware acquisition intangibles
        },
        "working_capital_days": {"dso": 35, "dio": 45, "dpo": 40},
        "roic": {"capitalize_rd": False, "rd_amortization_years": 5},
        "sensitivity": {
            "wacc_range": [0.07, 0.075, 0.08, 0.085, 0.09, 0.095, 0.10, 0.105, 0.11],
            "terminal_growth_range": [0.020, 0.025, 0.030, 0.035, 0.040],
        },
        "market_data": {"price_start_date": "2009-08-06", "benchmark_ticker": "^GSPC"},
        "sec": {
            "cik": "0001730168",
            "user_agent": "StockValuation research@example.com",
            "base_url": "https://data.sec.gov/api/xbrl/companyfacts",
            "annual_forms": ["10-K", "10-K/A"],
            "years_to_keep": 10,
        },
        "_calibration": (
            "BROADCOM (Feb 2026): FY ends Oct. Revenue $64B FY2025. "
            "β=1.21. Adj. EBITDA margin 67%. GAAP OpM lower due to VMware amortisation. "
            "AI semi revenue $20B (31% of total), growing 65% YoY. "
            "Custom AI accelerator designs for 3 hyperscalers. "
            "D/(D+E) ~35% from $69B VMware acquisition debt."
        ),
    },

    # ──────────────────────────────────────────────────────────────────────
    # 9. ELI LILLY
    # ──────────────────────────────────────────────────────────────────────
    "LLY": {
        "company": {
            "name": "Eli Lilly and Company",
            "ticker": "LLY",
            "currency": "USD",
            "fiscal_year_end": "December",
        },
        "tax": {
            "effective_rate": 0.15,
            "marginal_rate": 0.21,
        },
        "cost_of_capital": {
            "risk_free_rate": 0.045,
            "equity_risk_premium": 0.05,
            "beta": 0.50,
            "country_risk_premium": 0.0,
            "pre_tax_cost_of_debt": 0.04,
            "target_debt_to_capital": 0.35,
            # Using β=0.50 (between 0.39 Yahoo and 0.60 alternate).
            # Very low beta reflects defensive pharma characteristics.
        },
        "projection": {
            "explicit_years": 10,
            "terminal_growth_rate": 0.025,
        },
        "revenue": {
            "base_year_revenue": None,
            "near_term_growth_rates": [
                0.250,  # Yr 1: +25% — 2026 (Mounjaro + Zepbound explosion)
                0.220,  # Yr 2: +22% — GLP-1 market expanding globally
                0.180,  # Yr 3: +18% — continued ramp + new indications
                0.120,  # Yr 4: +12% — competition entering (Novo, Pfizer)
                0.080,  # Yr 5: +8%  — normalisation + pipeline launches
            ],
            "long_term_growth_rate": 0.04,
        },
        "margins": {
            "gross_margin": 0.82,
            "operating_margin": 0.40,
            "rd_to_revenue": 0.20,
            "sga_to_revenue": 0.20,
        },
        "capital_intensity": {
            "capex_to_revenue": 0.10,
            "depreciation_to_revenue": 0.05,
            "nwc_to_revenue": 0.15,
        },
        "working_capital_days": {"dso": 55, "dio": 170, "dpo": 70},
        "roic": {"capitalize_rd": False, "rd_amortization_years": 5},
        "sensitivity": {
            "wacc_range": [0.05, 0.055, 0.06, 0.065, 0.07, 0.075, 0.08, 0.085, 0.09],
            "terminal_growth_range": [0.015, 0.020, 0.025, 0.030, 0.035],
        },
        "market_data": {"price_start_date": "2000-01-01", "benchmark_ticker": "^GSPC"},
        "sec": {
            "cik": "0000059478",
            "user_agent": "StockValuation research@example.com",
            "base_url": "https://data.sec.gov/api/xbrl/companyfacts",
            "annual_forms": ["10-K", "10-K/A"],
            "years_to_keep": 10,
        },
        "_calibration": (
            "ELI LILLY (Feb 2026): FY ends Dec. Revenue $65B 2025 (+45% YoY). "
            "β=0.50 (defensive pharma). OpM 40%. "
            "Mounjaro (diabetes) + Zepbound (obesity) = two blockbusters. "
            "GLP-1 category could be $150B+ TAM by 2030. "
            "Patent cliff risk in late 2030s. R&D 20% of revenue."
        ),
    },

    # ──────────────────────────────────────────────────────────────────────
    # 10. BERKSHIRE HATHAWAY
    # ──────────────────────────────────────────────────────────────────────
    "BRK-B": {
        "company": {
            "name": "Berkshire Hathaway Inc.",
            "ticker": "BRK-B",
            "currency": "USD",
            "fiscal_year_end": "December",
        },
        "tax": {
            "effective_rate": 0.22,
            "marginal_rate": 0.21,
        },
        "cost_of_capital": {
            "risk_free_rate": 0.045,
            "equity_risk_premium": 0.05,
            "beta": 0.54,
            "country_risk_premium": 0.0,
            "pre_tax_cost_of_debt": 0.04,
            "target_debt_to_capital": 0.15,
        },
        "projection": {
            "explicit_years": 10,
            "terminal_growth_rate": 0.02,
        },
        "revenue": {
            "base_year_revenue": None,
            "near_term_growth_rates": [
                0.040,  # Yr 1: +4% — 2026 (insurance + operating businesses)
                0.040,  # Yr 2: +4%
                0.035,  # Yr 3: +3.5%
                0.035,  # Yr 4: +3.5%
                0.030,  # Yr 5: +3% — tracks nominal GDP
            ],
            "long_term_growth_rate": 0.03,
        },
        "margins": {
            "gross_margin": 0.35,
            "operating_margin": 0.20,
            "rd_to_revenue": 0.00,
            "sga_to_revenue": 0.05,
        },
        "capital_intensity": {
            "capex_to_revenue": 0.06,
            "depreciation_to_revenue": 0.03,
            "nwc_to_revenue": 0.10,
        },
        "working_capital_days": {"dso": 45, "dio": 25, "dpo": 40},
        "roic": {"capitalize_rd": False, "rd_amortization_years": 5},
        "sensitivity": {
            "wacc_range": [0.05, 0.055, 0.06, 0.065, 0.07, 0.075, 0.08, 0.085, 0.09],
            "terminal_growth_range": [0.010, 0.015, 0.020, 0.025, 0.030],
        },
        "market_data": {"price_start_date": "2000-01-01", "benchmark_ticker": "^GSPC"},
        "sec": {
            "cik": "0001067983",
            "user_agent": "StockValuation research@example.com",
            "base_url": "https://data.sec.gov/api/xbrl/companyfacts",
            "annual_forms": ["10-K", "10-K/A"],
            "years_to_keep": 10,
        },
        "_calibration": (
            "BERKSHIRE HATHAWAY (Feb 2026): FY ends Dec. Revenue ~$372B 2024. "
            "β=0.54. OpM ~20%. CAUTION: BRK is a financial/insurance conglomerate. "
            "Value comes from insurance float, equity portfolio ($300B+), and "
            "wholly-owned subsidiaries. A traditional DCF on operating earnings "
            "will NOT capture the full picture. Results should be treated as "
            "illustrative only. $330B cash pile is a significant value driver."
        ),
    },
}


# ═══════════════════════════════════════════════════════════════════════════
# Runner
# ═══════════════════════════════════════════════════════════════════════════


def write_config(ticker: str) -> None:
    """Write the assumptions.yaml for a given company."""
    config = COMPANIES[ticker].copy()
    # Promote calibration notes to description for report generation
    calibration = config.pop("_calibration", "")
    config["company"]["description"] = calibration

    # Build the YAML header comment
    header = (
        f"# {'=' * 77}\n"
        f"# {config['company']['name']} — Central Assumptions File\n"
        f"# {'=' * 77}\n"
        f"# Auto-generated by run_top10.py\n"
        f"#Params: {calibration}\n"
        f"# {'=' * 77}\n\n"
    )

    with open(CONFIG_PATH, "w") as f:
        f.write(header)
        yaml.dump(config, f, default_flow_style=False, sort_keys=False, width=120)

    print(f"  ✓ Config written for {ticker}")


def run_pipeline(ticker: str, skip_viz: bool = False) -> bool:
    """Run main.py for the current config. Returns True on success."""
    # Always skip extraction for re-runs to save time and API calls
    cmd = [sys.executable, str(PROJECT_ROOT / "main.py"), "--skip-extract"]
    if skip_viz:
        cmd.append("--skip-viz")

    print(f"\n{'═' * 72}")
    print(f"  RUNNING PIPELINE: {COMPANIES[ticker]['company']['name']} ({ticker})")
    print(f"{'═' * 72}\n")

    result = subprocess.run(cmd, cwd=str(PROJECT_ROOT))
    return result.returncode == 0


def main():
    """Run the valuation pipeline for all (or specified) top-10 companies."""
    # Parse CLI args for specific tickers
    requested = [t.upper() for t in sys.argv[1:]] if len(sys.argv) > 1 else list(COMPANIES.keys())

    # Validate tickers
    for t in requested:
        if t not in COMPANIES:
            print(f"  ✗ Unknown ticker: {t}")
            print(f"    Available: {', '.join(COMPANIES.keys())}")
            sys.exit(1)

    # Backup original config
    if CONFIG_PATH.exists():
        shutil.copy2(CONFIG_PATH, BACKUP_PATH)
        print(f"  ✓ Original config backed up → {BACKUP_PATH}")

    total = len(requested)
    results = {}
    overall_start = time.time()

    for i, ticker in enumerate(requested, 1):
        print(f"\n\n{'█' * 72}")
        print(f"  [{i}/{total}]  {COMPANIES[ticker]['company']['name']} ({ticker})")
        print(f"{'█' * 72}")

        start = time.time()
        try:
            write_config(ticker)
            success = run_pipeline(ticker, skip_viz=True)
            elapsed = time.time() - start
            results[ticker] = ("✓ OK" if success else "⚠ FAILED", f"{elapsed:.1f}s")
            if success:
                print(f"\n  ✓ {ticker} complete in {elapsed:.1f}s")
            else:
                print(f"\n  ⚠ {ticker} pipeline returned non-zero exit code")
        except Exception as e:
            elapsed = time.time() - start
            results[ticker] = (f"✗ ERROR: {e}", f"{elapsed:.1f}s")
            print(f"\n  ✗ {ticker} failed: {e}")

    # Restore original config
    if BACKUP_PATH.exists():
        shutil.copy2(BACKUP_PATH, CONFIG_PATH)
        BACKUP_PATH.unlink()
        print(f"\n  ✓ Original config restored")

    # Summary
    total_elapsed = time.time() - overall_start
    print(f"\n\n{'═' * 72}")
    print(f"  S&P 500 TOP 10 — PIPELINE RESULTS")
    print(f"{'═' * 72}\n")
    print(f"  {'Ticker':<8s}  {'Status':<30s}  {'Time':>8s}")
    print(f"  {'─' * 8}  {'─' * 30}  {'─' * 8}")
    for ticker in requested:
        status, elapsed = results.get(ticker, ("SKIPPED", "—"))
        name = COMPANIES[ticker]["company"]["name"][:25]
        print(f"  {ticker:<8s}  {status:<30s}  {elapsed:>8s}")

    print(f"\n  Total runtime: {total_elapsed:.0f}s ({total_elapsed/60:.1f} min)")
    print(f"  Output:        {PROJECT_ROOT / 'output'}/")
    print(f"{'═' * 72}\n")


if __name__ == "__main__":
    main()
