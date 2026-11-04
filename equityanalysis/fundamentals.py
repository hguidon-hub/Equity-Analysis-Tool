"""Income-statement trends and valuation snapshot. Pure functions on yfinance-shaped data."""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

# yfinance row label -> our column name (first match wins)
INCOME_ROWS = {
    "Revenue": ["Total Revenue", "Operating Revenue"],
    "Gross Profit": ["Gross Profit"],
    "Operating Income": ["Operating Income", "EBIT"],
    "Net Income": ["Net Income", "Net Income Common Stockholders"],
}


def _num(x) -> float | None:
    try:
        x = float(x)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def quarterly_table(income: pd.DataFrame) -> pd.DataFrame:
    """Turn yfinance's quarterly income statement (rows = items, columns = dates, newest first)
    into a tidy table sorted oldest -> newest with margins and growth rates.

    Growth is reported both quarter-on-quarter and year-on-year. YoY (vs the same quarter
    a year earlier) is the one that matters: QoQ mixes in seasonality.
    """
    if income is None or income.empty:
        raise ValueError("No income statement data.")
    data = {}
    for col, candidates in INCOME_ROWS.items():
        label = next((c for c in candidates if c in income.index), None)
        data[col] = income.loc[label] if label else pd.Series(float("nan"), index=income.columns)
    df = pd.DataFrame(data)
    df.index = pd.to_datetime(df.index)
    df = df.sort_index().astype(float)
    df = df.dropna(how="all", subset=["Revenue", "Net Income"])

    rev = df["Revenue"].where(df["Revenue"] > 0)
    df["Gross Margin"] = df["Gross Profit"] / rev
    df["Operating Margin"] = df["Operating Income"] / rev
    df["Net Margin"] = df["Net Income"] / rev
    df["Revenue QoQ"] = df["Revenue"].pct_change(fill_method=None)
    df["Revenue YoY"] = df["Revenue"].pct_change(4, fill_method=None)
    df["Net Income YoY"] = (df["Net Income"] - df["Net Income"].shift(4)) / df["Net Income"].shift(4).abs()
    df.index.name = "Quarter End"
    return df


def trailing_twelve_months(df: pd.DataFrame) -> dict[str, float | None]:
    """Sum of the last four quarters (None if fewer than four are available)."""
    last4 = df.tail(4)
    out = {}
    for col in ("Revenue", "Operating Income", "Net Income"):
        vals = last4[col]
        out[col] = float(vals.sum()) if len(vals) == 4 and vals.notna().all() else None
    out["Net Margin"] = (
        out["Net Income"] / out["Revenue"] if out["Revenue"] and out["Net Income"] is not None else None
    )
    return out


@dataclass(frozen=True)
class Snapshot:
    name: str
    sector: str | None
    currency: str
    financial_currency: str
    price: float | None
    market_cap: float | None
    enterprise_value: float | None
    trailing_pe: float | None
    forward_pe: float | None
    price_to_book: float | None
    ev_to_ebitda: float | None
    ev_to_revenue: float | None
    fcf_yield: float | None
    dividend_yield: float | None
    payout_ratio: float | None
    roe: float | None
    debt_to_equity: float | None  # as a multiple (1.5 = 150%)
    high_52w: float | None
    low_52w: float | None

    @property
    def pct_from_52w_high(self) -> float | None:
        if self.price and self.high_52w:
            return self.price / self.high_52w - 1.0
        return None


def snapshot_from_info(info: dict, symbol: str, fallback_price: float | None = None) -> Snapshot:
    """Build a valuation snapshot from yfinance ``Ticker.info``.

    Yields are recomputed from cash amounts (dividendRate, freeCashflow) rather than read from
    Yahoo's yield fields, whose units have changed between yfinance versions.
    """
    info = info or {}
    price = _num(info.get("currentPrice")) or _num(info.get("regularMarketPrice")) or fallback_price
    mcap = _num(info.get("marketCap"))
    div_rate = _num(info.get("dividendRate"))
    fcf = _num(info.get("freeCashflow"))
    dte = _num(info.get("debtToEquity"))
    currency = info.get("currency") or "USD"
    return Snapshot(
        name=info.get("longName") or info.get("shortName") or symbol,
        sector=info.get("sector"),
        currency=currency,
        financial_currency=info.get("financialCurrency") or currency,
        price=price,
        market_cap=mcap,
        enterprise_value=_num(info.get("enterpriseValue")),
        trailing_pe=_num(info.get("trailingPE")),
        forward_pe=_num(info.get("forwardPE")),
        price_to_book=_num(info.get("priceToBook")),
        ev_to_ebitda=_num(info.get("enterpriseToEbitda")),
        ev_to_revenue=_num(info.get("enterpriseToRevenue")),
        fcf_yield=fcf / mcap if fcf is not None and mcap else None,
        dividend_yield=(div_rate / price) if div_rate and price else 0.0,
        payout_ratio=_num(info.get("payoutRatio")),
        roe=_num(info.get("returnOnEquity")),
        debt_to_equity=dte / 100.0 if dte is not None else None,  # Yahoo reports it in percent
        high_52w=_num(info.get("fiftyTwoWeekHigh")),
        low_52w=_num(info.get("fiftyTwoWeekLow")),
    )
