"""One-page 2x2 dashboard for an EquityAnalysis."""

from __future__ import annotations

import numpy as np

from .analysis import EquityAnalysis
from .metrics import drawdown_series

BLUE, RED, GREY, GREEN = "#1f4e79", "#c0392b", "#7f8c8d", "#1e8449"


def plot_dashboard(a: EquityAnalysis, save_path: str | None = None, show: bool = True):
    import matplotlib

    if not show:
        matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    fig.suptitle(f"{a.symbol} — {a.snapshot.name} — {a.period}", fontsize=14, fontweight="bold")

    # 1. Rebased performance vs benchmark
    ax = axes[0, 0]
    ax.plot(a.close.index, a.close / a.close.iloc[0] * 100, color=BLUE, lw=1.8, label=a.symbol)
    if a.bench_close is not None and not a.bench_close.empty:
        b = a.bench_close.loc[a.bench_close.index >= a.close.index[0]]
        if not b.empty:
            ax.plot(b.index, b / b.iloc[0] * 100, color=GREY, lw=1.5, label=a.benchmark)
    ax.set_title("Performance rebased to 100")
    ax.legend(fontsize=9)
    ax.grid(alpha=0.3)

    # 2. Drawdown (underwater) chart
    ax = axes[0, 1]
    dd = drawdown_series(a.close) * 100
    ax.fill_between(dd.index, dd, 0, color=RED, alpha=0.35)
    ax.plot(dd.index, dd, color=RED, lw=1)
    ax.set_title(f"Drawdown from peak — max {a.risk.max_drawdown:.1%}")
    ax.set_ylabel("%")
    ax.grid(alpha=0.3)

    for ax in (axes[0, 0], axes[0, 1]):
        locator = mdates.AutoDateLocator()
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))

    q = a.quarters
    fccy = a.snapshot.financial_currency
    if q is not None and not q.empty:
        labels = [d.strftime("%b %y") for d in q.index]
        x = np.arange(len(q))

        # 3. Quarterly revenue and net income
        ax = axes[1, 0]
        w = 0.4
        ax.bar(x - w / 2, q["Revenue"] / 1e9, w, color=BLUE, label="Revenue")
        ax.bar(x + w / 2, q["Net Income"] / 1e9, w, color=GREEN, label="Net income")
        ax.set_xticks(x, labels)
        ax.set_ylabel(f"{fccy} bn")
        ax.set_title("Quarterly revenue and net income")
        ax.axhline(0, color="black", lw=0.8)
        ax.legend(fontsize=9)
        ax.grid(alpha=0.3, axis="y")

        # 4. Margins
        ax = axes[1, 1]
        for col, color in (("Gross Margin", GREY), ("Operating Margin", BLUE), ("Net Margin", GREEN)):
            if q[col].notna().any():
                ax.plot(x, q[col] * 100, marker="o", color=color, lw=1.8, label=col)
        ax.set_xticks(x, labels)
        ax.set_ylabel("% of revenue")
        ax.set_title("Margins")
        ax.legend(fontsize=9)
        ax.grid(alpha=0.3)
    else:
        for ax in (axes[1, 0], axes[1, 1]):
            ax.text(0.5, 0.5, "No financial statements available", ha="center", va="center", transform=ax.transAxes)
            ax.set_axis_off()

    fig.tight_layout()
    if save_path:
        fig.savefig(save_path, dpi=130, bbox_inches="tight")
    if show:
        plt.show()
    return fig
