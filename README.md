# EquityAnalysisTool

![tests](https://github.com/hguidon-hub/Equity-Analysis-Tool/actions/workflows/tests.yml/badge.svg)

Command-line tool that produces a one-page **risk, valuation and fundamentals** report for any stock
on Yahoo Finance, US or European, with a chart dashboard and a CSV export of the quarterly figures.

```
$ python main.py MC.PA --period 3y --save lvmh.png
```

## What it covers

| Block | Metrics |
|---|---|
| Market | Price, market cap, enterprise value, 52-week range, distance from 52-week high |
| Valuation | P/E trailing and forward, EV/EBITDA, EV/Revenue, P/B, FCF yield, dividend yield and payout, ROE, debt/equity |
| Risk | Total return and CAGR vs benchmark, annualised volatility, Sharpe and Sortino on daily excess returns, max drawdown, 1-day historical VaR 95%, beta and correlation vs the local index |
| Fundamentals | Latest quarter revenue and net income, **YoY** and QoQ growth, gross/operating/net margins, trailing twelve months |
| Dashboard | Rebased performance vs benchmark, underwater drawdown chart, quarterly revenue and net income, margin trends |

Design choices that matter:

- **Local benchmark by default.** Beta is computed against the CAC 40 for `.PA` tickers, the DAX for
  `.DE`, the FTSE 100 for `.L` and so on, S&P 500 otherwise. Beta of a French stock against the
  S&P 500 is not a meaningful number. Override with `--benchmark`.
- **Year-on-year growth, not just quarter-on-quarter.** QoQ mixes in seasonality (a retailer's Q4 vs Q3
  says nothing about the business), so YoY against the same quarter last year is the headline figure.
- **Sharpe on excess returns.** The risk-free rate is converted to a daily rate and subtracted before
  computing mean and volatility. USD tickers use the 13-week T-bill (`^IRX`); for other currencies
  pass `--rate`.
- **Currency-aware.** Market data is shown in the trading currency and statements in the reporting
  currency, with a warning when they differ (ADRs, dual listings).
- **Robust to missing data.** Every field prints `n/a` rather than crashing when Yahoo returns nothing,
  which is common for ETFs, small caps and non-US listings.

## Install and run

```bash
git clone https://github.com/hguidon-hub/Equity-Analysis-Tool.git
cd Equity-Analysis-Tool
pip install -r requirements.txt

python main.py AAPL                                          # report + chart window
python main.py MC.PA --period 3y                             # benchmark auto-set to ^FCHI
python main.py NVDA -b ^NDX -r 0.04 --save nvda.png --csv nvda.csv --no-plot
```

## Project structure

```
equityanalysis/
  metrics.py        Returns, volatility, Sharpe, Sortino, drawdown, VaR, beta (pure functions)
  fundamentals.py   Quarterly table, margins, YoY growth, TTM, valuation snapshot
  analysis.py       Yahoo Finance access and orchestration
  report.py         Text report and quarterly table
  plots.py          2x2 matplotlib dashboard
main.py             CLI
tests/              14 offline unit tests (fake Yahoo ticker, no network)
```

## Validation

```bash
python -m unittest discover -s tests -t . -v
```

The tests run on every push (GitHub Actions) and check, among others: max drawdown on a known path,
beta of exactly 2 for a 2x leveraged series, Sharpe against a hand computation, Sortino rising with
upside only, CAGR, historical VaR, YoY vs QoQ growth on a known income statement, unit conversions of
Yahoo fields (debt/equity in percent, yields from cash amounts) and a full report with empty data.

## Limitations

- Yahoo Finance data is free, delayed and sometimes incomplete; quarterly statements usually cover
  only the last 5 to 6 quarters, which limits YoY history.
- Risk metrics are backward-looking and use simple daily returns; VaR is historical, with no
  volatility scaling.
- Valuation multiples come from Yahoo as published, without adjustment for one-offs or
  share-based compensation.

## Author

Hugo Guidon, MSc in Finance (Financial Markets), emlyon business school.
