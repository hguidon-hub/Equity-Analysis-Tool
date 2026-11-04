"""Fetch data from Yahoo Finance and assemble one EquityAnalysis."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import pandas as pd

from .fundamentals import Snapshot, quarterly_table, snapshot_from_info, trailing_twelve_months
from .metrics import RiskReport, risk_report

US_TBILL = "^IRX"
NON_USD_FALLBACK_RATE = 0.02
USD_FALLBACK_RATE = 0.04

# Local benchmark by exchange suffix: beta vs the S&P 500 is meaningless for a CAC 40 stock.
BENCHMARK_BY_SUFFIX = {
    ".PA": "^FCHI",
    ".DE": "^GDAXI",
    ".L": "^FTSE",
    ".AS": "^AEX",
    ".MI": "FTSEMIB.MI",
    ".MC": "^IBEX",
    ".SW": "^SSMI",
    ".TO": "^GSPTSE",
    ".T": "^N225",
    ".HK": "^HSI",
}


def default_benchmark(symbol: str) -> str:
    for suffix, bench in BENCHMARK_BY_SUFFIX.items():
        if symbol.upper().endswith(suffix):
            return bench
    return "^GSPC"


def load_ticker(symbol: str):
    import yfinance as yf  # lazy import: tests run without the package

    return yf.Ticker(symbol)


def get_close(ticker, period: str) -> pd.Series:
    data = ticker.history(period=period, interval="1d", auto_adjust=True)
    if data is None or data.empty:
        raise RuntimeError("No price history returned by Yahoo Finance.")
    close = data["Close"].dropna()
    idx = pd.to_datetime(close.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None).normalize()  # align exchanges in different time zones
    close.index = idx
    return close


def get_risk_free_rate(currency: str, loader=load_ticker) -> tuple[float, str]:
    """Annual effective rate and its source label."""
    if currency != "USD":
        return NON_USD_FALLBACK_RATE, f"fallback {NON_USD_FALLBACK_RATE:.1%} ({currency}; use --rate)"
    try:
        last = float(loader(US_TBILL).history(period="5d", interval="1d")["Close"].dropna().iloc[-1])
        if math.isfinite(last) and last > 0:
            return last / 100.0, "13w US T-bill (^IRX)"
    except Exception:
        pass
    return USD_FALLBACK_RATE, f"fallback {USD_FALLBACK_RATE:.1%} (use --rate)"


@dataclass
class EquityAnalysis:
    symbol: str
    benchmark: str
    period: str
    snapshot: Snapshot
    risk: RiskReport
    quarters: pd.DataFrame | None
    ttm: dict | None
    close: pd.Series = field(repr=False)
    bench_close: pd.Series | None = field(repr=False, default=None)
    rate_source: str = ""
    warnings: list[str] = field(default_factory=list)


def analyze(
    symbol: str,
    period: str = "1y",
    benchmark: str | None = None,
    rate: float | None = None,
    loader=load_ticker,
) -> EquityAnalysis:
    """``loader`` maps a symbol to a yfinance-like Ticker (swap in a fake for tests)."""
    symbol = symbol.strip().upper()
    benchmark = benchmark or default_benchmark(symbol)
    warnings: list[str] = []

    ticker = loader(symbol)
    close = get_close(ticker, period)

    try:
        info = ticker.info or {}
    except Exception:
        info = {}
        warnings.append("Company profile unavailable from Yahoo; valuation fields are empty.")
    snap = snapshot_from_info(info, symbol, fallback_price=float(close.iloc[-1]))

    try:
        bench_close = get_close(loader(benchmark), period)
    except Exception:
        bench_close = None
        warnings.append(f"Benchmark {benchmark} unavailable; beta not computed.")

    if rate is None:
        rate, rate_source = get_risk_free_rate(snap.currency, loader)
    else:
        rate_source = "user input"

    risk = risk_report(close, bench_close, rate)

    quarters = ttm = None
    try:
        quarters = quarterly_table(ticker.quarterly_income_stmt)
        ttm = trailing_twelve_months(quarters)
        if len(quarters) < 5:
            warnings.append(f"Only {len(quarters)} quarters available: year-on-year growth is limited.")
    except Exception:
        warnings.append("Quarterly income statement unavailable (ETF, index or data gap).")

    if snap.financial_currency != snap.currency:
        warnings.append(
            f"Statements are in {snap.financial_currency} while the share trades in {snap.currency}."
        )

    return EquityAnalysis(
        symbol=symbol,
        benchmark=benchmark,
        period=period,
        snapshot=snap,
        risk=risk,
        quarters=quarters,
        ttm=ttm,
        close=close,
        bench_close=bench_close,
        rate_source=rate_source,
        warnings=warnings,
    )
