"""Offline tests: synthetic prices and a fake yfinance ticker, no network."""

import math
import unittest

import numpy as np
import pandas as pd

from equityanalysis import metrics as m
from equityanalysis.analysis import analyze, default_benchmark
from equityanalysis.fundamentals import quarterly_table, snapshot_from_info, trailing_twelve_months
from equityanalysis.report import format_quarter_table, format_report


def prices(returns, start=100.0, end="2026-11-04"):
    idx = pd.bdate_range(end=end, periods=len(returns) + 1)
    return pd.Series(start * np.cumprod(np.concatenate([[1.0], 1 + np.asarray(returns)])), index=idx)


def fake_income(n_quarters=6):
    # yfinance layout: rows = line items, columns = quarter ends, newest first
    dates = pd.date_range(end="2026-09-30", periods=n_quarters, freq="QE")[::-1]
    rev = np.array([120, 110, 105, 100, 90, 80][:n_quarters], dtype=float) * 1e9
    ni = rev * 0.2
    return pd.DataFrame(
        [rev, rev * 0.5, rev * 0.3, ni],
        index=["Total Revenue", "Gross Profit", "Operating Income", "Net Income"],
        columns=dates,
    )


class FakeTicker:
    def __init__(self, close, info=None, income=None):
        self._close, self.info, self.quarterly_income_stmt = close, info, income

    def history(self, **kwargs):
        return pd.DataFrame({"Close": self._close})


class TestMetrics(unittest.TestCase):
    def test_max_drawdown(self):
        close = pd.Series([100, 120, 90, 130, 65, 70], index=pd.bdate_range("2026-01-01", periods=6))
        self.assertAlmostEqual(m.max_drawdown(close), 65 / 130 - 1)

    def test_beta_of_leveraged_series_is_two(self):
        rng = np.random.default_rng(0)
        b = pd.Series(rng.normal(0, 0.01, 300))
        beta, corr = m.beta_and_correlation(2 * b, b)
        self.assertAlmostEqual(beta, 2.0, places=10)
        self.assertAlmostEqual(corr, 1.0, places=10)

    def test_sharpe_uses_excess_returns(self):
        rng = np.random.default_rng(1)
        r = pd.Series(rng.normal(0.0005, 0.01, 500))
        rf = 0.03
        ex = r - ((1 + rf) ** (1 / 252) - 1)
        expected = ex.mean() / ex.std(ddof=1) * math.sqrt(252)
        self.assertAlmostEqual(m.sharpe_ratio(r, rf), expected, places=12)
        self.assertLess(m.sharpe_ratio(r, 0.05), m.sharpe_ratio(r, 0.0))

    def test_sortino_ignores_upside(self):
        r = pd.Series([0.02, -0.01] * 100)
        r_more_upside = pd.Series([0.04, -0.01] * 100)
        # same downside, more upside: Sortino must rise
        self.assertGreater(m.sortino_ratio(r_more_upside, 0.0), m.sortino_ratio(r, 0.0))

    def test_cagr(self):
        close = pd.Series([100.0, 121.0], index=pd.to_datetime(["2024-01-01", "2026-01-01"]))
        self.assertAlmostEqual(m.cagr(close), 0.1, places=3)

    def test_var(self):
        r = pd.Series(np.linspace(-0.05, 0.05, 101))
        self.assertAlmostEqual(m.value_at_risk(r, 0.95), 0.045, places=10)


class TestFundamentals(unittest.TestCase):
    def test_quarterly_table_sorted_with_yoy(self):
        q = quarterly_table(fake_income())
        self.assertTrue(q.index.is_monotonic_increasing)
        self.assertAlmostEqual(q["Revenue YoY"].iloc[-1], 120 / 90 - 1)  # vs same quarter last year
        self.assertAlmostEqual(q["Revenue QoQ"].iloc[-1], 120 / 110 - 1)
        self.assertAlmostEqual(q["Net Margin"].iloc[-1], 0.2)
        ttm = trailing_twelve_months(q)
        self.assertAlmostEqual(ttm["Revenue"], (120 + 110 + 105 + 100) * 1e9)

    def test_missing_rows_do_not_crash(self):
        income = fake_income().drop(index=["Gross Profit", "Operating Income"])
        q = quarterly_table(income)
        self.assertTrue(q["Gross Margin"].isna().all())

    def test_ttm_needs_four_quarters(self):
        self.assertIsNone(trailing_twelve_months(quarterly_table(fake_income(3)))["Revenue"])

    def test_snapshot_units(self):
        s = snapshot_from_info(
            {"currentPrice": 50.0, "dividendRate": 1.5, "debtToEquity": 150.0, "marketCap": 1e9, "freeCashflow": 5e7},
            "X",
        )
        self.assertAlmostEqual(s.dividend_yield, 0.03)
        self.assertAlmostEqual(s.debt_to_equity, 1.5)
        self.assertAlmostEqual(s.fcf_yield, 0.05)

    def test_snapshot_empty_info(self):
        s = snapshot_from_info({}, "X", fallback_price=10.0)
        self.assertEqual(s.price, 10.0)
        self.assertIsNone(s.trailing_pe)


class TestPipeline(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(3)
        bench_r = rng.normal(0.0004, 0.01, 260)
        self.bench = prices(bench_r)
        self.stock = prices(1.3 * bench_r + rng.normal(0, 0.005, 260))

    def loader(self, info=None, income=None):
        def load(symbol):
            if symbol == "^GSPC":
                return FakeTicker(self.bench)
            return FakeTicker(self.stock, info, income)
        return load

    def test_full_report(self):
        a = analyze("abc", rate=0.04, loader=self.loader({"longName": "ABC Corp", "currency": "USD"}, fake_income()))
        self.assertEqual(a.benchmark, "^GSPC")
        self.assertAlmostEqual(a.risk.beta, 1.3, delta=0.1)
        text = format_report(a)
        self.assertIn("ABC Corp", text)
        self.assertIn("LATEST QUARTER", text)
        self.assertIn("2026-09-30", format_quarter_table(a))

    def test_report_survives_missing_data(self):
        # regression: v1 crashed on None price / P/E and on missing statements
        a = analyze("abc", rate=0.04, loader=self.loader({}, None))
        text = format_report(a)
        self.assertIn("n/a", text)
        self.assertTrue(any("income statement" in w for w in a.warnings))

    def test_local_benchmarks(self):
        self.assertEqual(default_benchmark("MC.PA"), "^FCHI")
        self.assertEqual(default_benchmark("SAP.DE"), "^GDAXI")
        self.assertEqual(default_benchmark("AAPL"), "^GSPC")


if __name__ == "__main__":
    unittest.main()
