"""Plain-text report. Every field tolerates missing data (prints n/a instead of crashing)."""

from __future__ import annotations

import math

from .analysis import EquityAnalysis

WIDTH = 64


def _ok(x) -> bool:
    return x is not None and isinstance(x, (int, float)) and math.isfinite(x)


def money(x, ccy: str = "") -> str:
    if not _ok(x):
        return "n/a"
    sign = "-" if x < 0 else ""
    x = abs(x)
    for unit, div in (("T", 1e12), ("B", 1e9), ("M", 1e6), ("K", 1e3)):
        if x >= div:
            return f"{sign}{x / div:,.2f}{unit} {ccy}".strip()
    return f"{sign}{x:,.2f} {ccy}".strip()


def pct(x, decimals: int = 1, signed: bool = False) -> str:
    if not _ok(x):
        return "n/a"
    return f"{x * 100:+.{decimals}f}%" if signed else f"{x * 100:.{decimals}f}%"


def ratio(x, suffix: str = "x") -> str:
    return f"{x:.2f}{suffix}" if _ok(x) else "n/a"


def _row(label: str, value: str) -> str:
    return f"  {label:<32}{value:>{WIDTH - 34}}"


def format_report(a: EquityAnalysis) -> str:
    s, r = a.snapshot, a.risk
    ccy, fccy = s.currency, s.financial_currency
    lines = [
        "=" * WIDTH,
        f" {a.symbol} — {s.name}".center(WIDTH),
        (f" {s.sector}".center(WIDTH) if s.sector else ""),
        "=" * WIDTH,
        " MARKET",
        _row("Price", money(s.price, ccy)),
        _row("Market cap", money(s.market_cap, ccy)),
        _row("Enterprise value", money(s.enterprise_value, ccy)),
        _row("52w range", f"{money(s.low_52w)} - {money(s.high_52w)}"),
        _row("Distance from 52w high", pct(s.pct_from_52w_high, signed=True)),
        "-" * WIDTH,
        " VALUATION",
        _row("P/E trailing / forward", f"{ratio(s.trailing_pe)} / {ratio(s.forward_pe)}"),
        _row("EV / EBITDA", ratio(s.ev_to_ebitda)),
        _row("EV / Revenue", ratio(s.ev_to_revenue)),
        _row("Price / Book", ratio(s.price_to_book)),
        _row("FCF yield", pct(s.fcf_yield)),
        _row("Dividend yield / payout", f"{pct(s.dividend_yield, 2)} / {pct(s.payout_ratio)}"),
        _row("ROE", pct(s.roe)),
        _row("Debt / Equity", ratio(s.debt_to_equity)),
        "-" * WIDTH,
        f" RISK ({r.period_start:%Y-%m-%d} to {r.period_end:%Y-%m-%d}, daily data)",
        _row("Total return / CAGR", f"{pct(r.total_return, signed=True)} / {pct(r.cagr, signed=True)}"),
        _row(f"Benchmark {a.benchmark} return", pct(r.bench_total_return, signed=True)),
        _row("Volatility (annualised)", pct(r.volatility)),
        _row("Sharpe / Sortino", f"{ratio(r.sharpe, '')} / {ratio(r.sortino, '')}"),
        _row("Max drawdown", pct(r.max_drawdown)),
        _row("1-day VaR 95% (historical)", pct(r.var_95, 2)),
        _row(f"Beta / correlation vs {a.benchmark}", f"{ratio(r.beta, '')} / {ratio(r.correlation, '')}"),
        _row("Risk-free rate", f"{pct(r.risk_free_rate, 2)} [{a.rate_source}]"),
    ]
    lines = [line for line in lines if line != ""]

    if a.quarters is not None and not a.quarters.empty:
        q = a.quarters.iloc[-1]
        lines += [
            "-" * WIDTH,
            f" LATEST QUARTER ({a.quarters.index[-1]:%Y-%m-%d}, {fccy})",
            _row("Revenue", money(q["Revenue"], fccy)),
            _row("Revenue growth YoY / QoQ", f"{pct(q['Revenue YoY'], signed=True)} / {pct(q['Revenue QoQ'], signed=True)}"),
            _row("Net income", money(q["Net Income"], fccy)),
            _row("Net income growth YoY", pct(q["Net Income YoY"], signed=True)),
            _row("Gross / operating / net margin",
                 f"{pct(q['Gross Margin'])} / {pct(q['Operating Margin'])} / {pct(q['Net Margin'])}"),
        ]
        if a.ttm and a.ttm.get("Revenue") is not None:
            lines += [
                _row("TTM revenue", money(a.ttm["Revenue"], fccy)),
                _row("TTM net income / net margin", f"{money(a.ttm['Net Income'], fccy)} / {pct(a.ttm['Net Margin'])}"),
            ]
    lines.append("=" * WIDTH)
    if a.warnings:
        lines.append(" WARNINGS")
        lines += [f"  ! {w}" for w in a.warnings]
        lines.append("=" * WIDTH)
    return "\n".join(lines)


def format_quarter_table(a: EquityAnalysis) -> str:
    if a.quarters is None or a.quarters.empty:
        return ""
    t = a.quarters[["Revenue", "Net Income", "Net Margin", "Revenue YoY", "Revenue QoQ"]].copy()
    t.index = t.index.strftime("%Y-%m-%d")
    for col in ("Revenue", "Net Income"):
        t[col] = t[col].map(lambda v: money(v))
    for col in ("Net Margin", "Revenue YoY", "Revenue QoQ"):
        t[col] = t[col].map(lambda v: pct(v, signed=col != "Net Margin"))
    return t.to_string()
