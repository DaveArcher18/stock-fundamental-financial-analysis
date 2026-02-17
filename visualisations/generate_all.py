"""
Generate All Visualisations
==============================
CLI entry point for the full valuation chart campaign.

Usage:
    python -m visualisations.generate_all [--output-dir reports/charts]

Generates all 8 charts to the output directory.
"""

import argparse
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Suppress matplotlib font warnings
import warnings
warnings.filterwarnings("ignore", category=UserWarning, module="matplotlib")

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend


def run_campaign(output_dir: str = None):
    """Generate all 8 charts programmatically.

    Parameters
    ----------
    output_dir : str | None
        Directory for chart PNGs. Defaults to ``reports/charts``.
    """
    if output_dir is None:
        output_dir = str(PROJECT_ROOT / "reports" / "charts")

    from visualisations.chart_style import load_company_config
    company_name, _ = load_company_config()

    print(f"\n{'═' * 60}")
    print(f"  {company_name.upper()} VISUALISATION CAMPAIGN")
    print(f"{'═' * 60}\n")

    start = time.time()

    # ── Chart 1: P/E Ratio ──
    print("  [1/8] P/E Ratio Over Time...")
    from visualisations.valuation_multiples import _load_data, plot_pe_ratio
    prices, financials = _load_data()
    plot_pe_ratio(prices, financials, output_dir)

    # ── Chart 2: EV/EBITDA ──
    print("  [2/8] EV/EBITDA Over Time...")
    from visualisations.valuation_multiples import plot_ev_ebitda
    plot_ev_ebitda(prices, financials, output_dir)

    # ── Chart 3: Revenue Growth ──
    print("  [3/8] Revenue & Growth...")
    from visualisations.revenue_growth import plot_revenue_growth
    plot_revenue_growth(output_dir)

    # ── Chart 4: Price vs Intrinsic ──
    print("  [4/8] Price vs. Intrinsic Value...")
    from visualisations.price_vs_intrinsic import plot_price_vs_intrinsic
    plot_price_vs_intrinsic(output_dir)

    # ── Chart 5: Margin Evolution ──
    print("  [5/8] Margin Evolution...")
    from visualisations.margin_evolution import plot_margin_evolution
    plot_margin_evolution(output_dir)

    # ── Chart 6: ROIC vs WACC ──
    print("  [6/8] ROIC vs. WACC...")
    from visualisations.roic_vs_wacc import plot_roic_vs_wacc
    plot_roic_vs_wacc(output_dir)

    # ── Chart 7: FCF Yield ──
    print("  [7/8] FCF Yield...")
    from visualisations.fcf_yield import plot_fcf_yield
    plot_fcf_yield(output_dir)

    # ── Chart 8: Sensitivity Heatmap ──
    print("  [8/8] Sensitivity Heatmap...")
    from visualisations.sensitivity_heatmap import plot_sensitivity_heatmap
    plot_sensitivity_heatmap(output_dir)

    elapsed = time.time() - start

    # Verify
    charts_dir = Path(output_dir)
    chart_files = sorted(charts_dir.glob("*.png"))

    print(f"\n{'═' * 60}")
    print(f"  Campaign complete! ({elapsed:.1f}s)")
    print(f"  {len(chart_files)} charts generated → {output_dir}/")
    print(f"{'─' * 60}")
    for f in chart_files:
        size_kb = f.stat().st_size / 1024
        print(f"    {'✓' if size_kb > 10 else '⚠'} {f.name} ({size_kb:.0f} KB)")
    print(f"{'═' * 60}\n")


def main():
    parser = argparse.ArgumentParser(description="Generate visualisation campaign")
    parser.add_argument("--output-dir", default=None,
                        help="Output directory for chart PNGs (default: reports/charts)")
    args = parser.parse_args()
    run_campaign(output_dir=args.output_dir)


if __name__ == "__main__":
    main()

