"""Risk and performance metrics on a daily price series. Pure functions, no network."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def simple_returns(close: pd.Series) -> pd.Series:
    return close.pct_change().dropna()


def daily_rf(annual_rate: float) -> float:
    """Annual (effective) risk-free rate converted to a daily rate."""
    return (1.0 + annual_rate) ** (1.0 / TRADING_DAYS) - 1.0


def annualized_volatility(returns: pd.Series) -> float:
    return float(returns.std(ddof=1) * math.sqrt(TRADING_DAYS))


def cagr(close: pd.Series) -> float:
    """Compound annual growth rate between the first and last observation (calendar time)."""
    years = (close.index[-1] - close.index[0]).days / 365.25
    if years <= 0:
        raise ValueError("Price series must span more than one day.")
    return float((close.iloc[-1] / close.iloc[0]) ** (1.0 / years) - 1.0)


def sharpe_ratio(returns: pd.Series, risk_free_rate: float) -> float | None:
    """Annualised Sharpe ratio on daily excess returns: mean(r - rf) / std(r - rf) * sqrt(252)."""
    excess = returns - daily_rf(risk_free_rate)
    sd = excess.std(ddof=1)
    if not sd or not math.isfinite(sd):
        return None
    return float(excess.mean() / sd * math.sqrt(TRADING_DAYS))


def sortino_ratio(returns: pd.Series, risk_free_rate: float) -> float | None:
    """Like Sharpe, but only penalises downside deviation (target = risk-free rate)."""
    excess = returns - daily_rf(risk_free_rate)
    downside = math.sqrt(float((np.minimum(excess, 0.0) ** 2).mean()))
    if downside == 0:
        return None
    return float(excess.mean() / downside * math.sqrt(TRADING_DAYS))


def drawdown_series(close: pd.Series) -> pd.Series:
    """Percentage drop from the running peak (0 at new highs, negative otherwise)."""
    return close / close.cummax() - 1.0


def max_drawdown(close: pd.Series) -> float:
    return float(drawdown_series(close).min())


def beta_and_correlation(stock_returns: pd.Series, bench_returns: pd.Series) -> tuple[float | None, float | None]:
    """OLS beta and correlation on dates where both series trade."""
    joined = pd.concat([stock_returns, bench_returns], axis=1, join="inner").dropna()
    if len(joined) < 20:
        return None, None
    s, b = joined.iloc[:, 0], joined.iloc[:, 1]
    var_b = b.var(ddof=1)
    if var_b == 0:
        return None, None
    return float(s.cov(b) / var_b), float(s.corr(b))


def value_at_risk(returns: pd.Series, level: float = 0.95) -> float:
    """1-day historical VaR as a positive loss fraction (e.g. 0.025 = 2.5%)."""
    return float(-np.quantile(returns, 1.0 - level))


@dataclass(frozen=True)
class RiskReport:
    period_start: pd.Timestamp
    period_end: pd.Timestamp
    total_return: float
    cagr: float
    volatility: float
    sharpe: float | None
    sortino: float | None
    max_drawdown: float
    var_95: float
    beta: float | None
    correlation: float | None
    bench_total_return: float | None
    risk_free_rate: float


def risk_report(close: pd.Series, bench_close: pd.Series | None, risk_free_rate: float) -> RiskReport:
    close = close.dropna()
    if len(close) < 30:
        raise ValueError("Need at least 30 daily prices for risk metrics.")
    rets = simple_returns(close)
    beta = corr = bench_tr = None
    if bench_close is not None and len(bench_close.dropna()) > 1:
        bench_close = bench_close.dropna()
        beta, corr = beta_and_correlation(rets, simple_returns(bench_close))
        aligned = bench_close.loc[(bench_close.index >= close.index[0]) & (bench_close.index <= close.index[-1])]
        if len(aligned) > 1:
            bench_tr = float(aligned.iloc[-1] / aligned.iloc[0] - 1.0)
    return RiskReport(
        period_start=close.index[0],
        period_end=close.index[-1],
        total_return=float(close.iloc[-1] / close.iloc[0] - 1.0),
        cagr=cagr(close),
        volatility=annualized_volatility(rets),
        sharpe=sharpe_ratio(rets, risk_free_rate),
        sortino=sortino_ratio(rets, risk_free_rate),
        max_drawdown=max_drawdown(close),
        var_95=value_at_risk(rets, 0.95),
        beta=beta,
        correlation=corr,
        bench_total_return=bench_tr,
        risk_free_rate=risk_free_rate,
    )
