"""EquityAnalysisTool command-line entry point.

Examples
--------
    python main.py AAPL
    python main.py MC.PA --period 3y            # benchmark auto-set to CAC 40
    python main.py NVDA --benchmark ^NDX --rate 0.04 --save nvda.png --csv nvda_quarters.csv --no-plot
"""

from __future__ import annotations

import argparse
import sys

from equityanalysis import __version__
from equityanalysis.analysis import analyze
from equityanalysis.report import format_quarter_table, format_report

PERIODS = ("6mo", "1y", "2y", "3y", "5y", "10y")


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Risk, valuation and fundamentals report for a listed stock.")
    p.add_argument("ticker", nargs="?", help="Yahoo Finance ticker, e.g. AAPL, MC.PA, AIR.PA")
    p.add_argument("-p", "--period", default="1y", choices=PERIODS, help="Price history window (default 1y)")
    p.add_argument("-b", "--benchmark", help="Benchmark ticker (default: local index from the exchange suffix, else ^GSPC)")
    p.add_argument("-r", "--rate", type=float, help="Annual risk-free rate as decimal (default: 13w T-bill for USD)")
    p.add_argument("--save", help="Save the chart dashboard to this PNG path")
    p.add_argument("--csv", help="Export the quarterly table to this CSV path")
    p.add_argument("--no-plot", action="store_true", help="Do not open the chart window")
    p.add_argument("--version", action="version", version=f"EquityAnalysisTool {__version__}")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    symbol = (args.ticker or input("Ticker: ")).strip().upper()
    if not symbol:
        raise ValueError("Ticker is required.")

    print(f"\nFetching data for {symbol}...")
    a = analyze(symbol, period=args.period, benchmark=args.benchmark, rate=args.rate)
    print(format_report(a))

    table = format_quarter_table(a)
    if table:
        print("\nQUARTERLY HISTORY")
        print(table)

    if args.csv and a.quarters is not None:
        a.quarters.to_csv(args.csv)
        print(f"\nQuarterly table saved to {args.csv}")

    if args.save or not args.no_plot:
        from equityanalysis.plots import plot_dashboard

        plot_dashboard(a, save_path=args.save, show=not args.no_plot)
        if args.save:
            print(f"Chart saved to {args.save}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nStopped.")
        sys.exit(130)
    except (ValueError, RuntimeError) as err:
        print(f"\nError: {err}", file=sys.stderr)
        sys.exit(1)
