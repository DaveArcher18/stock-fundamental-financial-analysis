"""
Chart 4: Price vs. Intrinsic Value
====================================
Market price line overlaid with DCF-derived intrinsic value estimates.

Usage:
    python -m visualisations.price_vs_intrinsic
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from visualisations.chart_style import (
    COLORS, create_figure, add_narrative_zones, add_event_annotations,
    add_source_footer, save_chart, load_company_config, get_output_dirs,
)


def _estimate_historical_intrinsic(financials, config, wacc_rate):
    """Estimate intrinsic value at each fiscal year-end using that year's data as base."""
    from models.dcf import (
        build_growth_schedule, build_margin_schedule,
        project_fcf, terminal_value, enterprise_value, equity_value_per_share,
    )

    results = {}
    for idx, row in financials.iterrows():
        fy = int(row["fiscal_year"])
        base_rev = row["revenue"]
        shares = row["shares_outstanding"]
        net_debt = row["long_term_debt"] - row["cash"]
        current_margin = row["operating_income"] / row["revenue"]

        n = config["projection"]["explicit_years"]
        tg = config["projection"]["terminal_growth_rate"]
        tax = config["tax"]["effective_rate"]
        target_margin = config["margins"]["operating_margin"]
        capex_r = config["capital_intensity"]["capex_to_revenue"]
        depr_r = config["capital_intensity"]["depreciation_to_revenue"]
        nwc_r = config["capital_intensity"]["nwc_to_revenue"]
        lt_growth = config["revenue"]["long_term_growth_rate"]

        # Use long-term growth for all years (no near-term overrides for historical)
        growth_sched = build_growth_schedule(n, [], lt_growth)
        margin_sched = build_margin_schedule(n, current_margin, target_margin)

        projections = project_fcf(
            base_revenue=base_rev, growth_rates=growth_sched,
            operating_margins=margin_sched, tax_rate=tax,
            capex_to_revenue=capex_r, depreciation_to_revenue=depr_r,
            nwc_to_revenue=nwc_r,
        )

        last_fcff = projections.iloc[-1]["fcff"]
        tv = terminal_value(last_fcff, tg, wacc_rate)
        ev_dict = enterprise_value(projections["fcff"], wacc_rate, tv, n)
        equity = ev_dict["enterprise_value"] - net_debt
        vps = equity / shares if shares > 0 else 0

        results[pd.Timestamp(idx)] = vps

    return pd.Series(results).sort_index()


def plot_price_vs_intrinsic(output_dir="reports/charts"):
    """Chart 4: Market price vs DCF intrinsic value."""
    import yaml

    _, ticker = load_company_config()
    raw_dir, processed_dir = get_output_dirs()
    prices = pd.read_csv(
        raw_dir / f"{ticker.lower()}_price_history.csv",
        index_col=0, parse_dates=True,
    )
    prices.index = pd.to_datetime(prices.index, utc=True).tz_localize(None)
    financials = pd.read_csv(
        processed_dir / "financials_annual.csv",
        index_col=0, parse_dates=True,
    )

    with open(PROJECT_ROOT / "config" / "assumptions.yaml") as f:
        config = yaml.safe_load(f)

    # Use data-driven WACC
    from models.wacc import compute_wacc_from_data
    info = pd.read_csv(raw_dir / f"{ticker.lower()}_company_info.csv")
    market_cap_usd = float(info[info["field"] == "market_cap"]["value"].values[0])
    wacc_result = compute_wacc_from_data(config, financials, market_cap_usd)
    wacc_rate = wacc_result["wacc"]

    # Compute historical intrinsic values
    iv_series = _estimate_historical_intrinsic(financials, config, wacc_rate)

    # Convert price to EUR (approximate) for comparability
    usd_eur = 0.92
    close_eur = prices["Close"] * usd_eur
    close_eur = close_eur[close_eur.index >= "2015-01-01"]

    fig, ax = create_figure(12, 6)

    # Market price
    ax.plot(close_eur.index, close_eur.values, color=COLORS["asml_blue"],
            linewidth=1.5, alpha=0.8, label="Market price (EUR)")

    # Intrinsic value as stepped line
    iv_extended = iv_series.reindex(close_eur.index, method="ffill")
    ax.plot(iv_extended.index, iv_extended.values, color=COLORS["green"],
            linewidth=2.5, linestyle="--", label="DCF intrinsic value")

    # Shade gap
    ax.fill_between(iv_extended.index, iv_extended.values, close_eur.reindex(iv_extended.index).values,
                     where=close_eur.reindex(iv_extended.index).values > iv_extended.values,
                     color=COLORS["coral"], alpha=0.1, label="Overvalued zone")
    ax.fill_between(iv_extended.index, iv_extended.values, close_eur.reindex(iv_extended.index).values,
                     where=close_eur.reindex(iv_extended.index).values <= iv_extended.values,
                     color=COLORS["green"], alpha=0.1, label="Undervalued zone")

    # Intrinsic value dots at year-end
    ax.scatter(iv_series.index, iv_series.values, color=COLORS["green"],
               s=60, zorder=5, edgecolor=COLORS["white"], linewidth=1.5)

    # Labels on dots
    for date, val in iv_series.items():
        ax.annotate(f"€{val:.0f}", xy=(date, val),
                    xytext=(0, -15), textcoords="offset points",
                    fontsize=7, ha="center", color=COLORS["green"], fontweight="bold")

    company_name, _ = load_company_config()
    ax.set_title(f"{company_name} — Market Price vs. DCF Intrinsic Value", color=COLORS["navy"])
    ax.set_ylabel("Price per Share (EUR)", color=COLORS["dark_text"])
    ax.set_ylim(0, close_eur.max() * 1.1)

    ax.legend(loc="upper left", fontsize=9)
    add_event_annotations(ax)
    add_source_footer(fig, "DCF model using current assumptions applied to historical base years")

    return save_chart(fig, "04_price_vs_intrinsic", output_dir)


if __name__ == "__main__":
    plot_price_vs_intrinsic()
