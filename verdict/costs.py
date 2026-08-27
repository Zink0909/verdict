"""Trading frictions: turnover, cost sensitivity, spreads, budgeted positions.

Costs are a first-class output, not an epilogue. A high-turnover signal in a
liquid market is routinely dead on costs no matter how good the raw predictions
look, so turnover and the breakeven cost belong on the table *before* anyone
grows attached to a gross number.

Provenance: chart_cnn/chartcnn/portfolio.py (turnover, net-of-cost returns) and
buy_the_dip/buythedip/strategy.py + backtest.py (IV-scaled spread, budgeted
position sizing).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .evaluate import sharpe


def turnover(w_prev: pd.Series, w_now: pd.Series) -> float:
    """One-way turnover between two weight vectors: 0.5 * sum |dw|.

    Unchanged book -> 0; a full long/short flip -> ~2.0 (200%).
    """
    idx = w_prev.index.union(w_now.index)
    a = w_prev.reindex(idx).fillna(0.0)
    b = w_now.reindex(idx).fillna(0.0)
    return 0.5 * float((b - a).abs().sum())


def net_return(gross: float, turn: float, cost_bps: float, sides: int = 2) -> float:
    """Net = gross - turnover * cost. `sides=2` charges both legs of a long/short."""
    return gross - turn * (cost_bps / 1e4) * sides


def breakeven_cost_bps(gross_mean: float, turn: float, sides: int = 2) -> float:
    """One-way cost (bps) at which the average period return reaches zero.

    Reading this next to a plausible real cost is the fastest honest test of
    whether a signal is tradable at all.
    """
    if turn <= 0:
        return float("inf") if gross_mean > 0 else float("nan")
    return float(gross_mean / (turn * sides) * 1e4)


def breakeven_friction(levels, expectancies) -> float:
    """Where an expectancy curve crosses zero, given a friction sensitivity table.

    `breakeven_cost_bps` assumes a linear cost model; this makes no such
    assumption — it interpolates a measured curve, which is what you have when
    the friction changes not only the P&L per trade but which trades happen at
    all. Returns NaN if the curve never crosses zero over the measured range.

    Reading the crossing next to the friction a real venue charges is the whole
    test: an edge whose breakeven sits inside the first increment of cost is not
    an edge, it is an accounting artefact.
    """
    lv = np.asarray(levels, dtype=float)
    ex = np.asarray(expectancies, dtype=float)
    order = np.argsort(lv)
    lv, ex = lv[order], ex[order]
    for i in range(len(lv) - 1):
        a, b = ex[i], ex[i + 1]
        if a > 0 >= b:
            return float(lv[i] + (lv[i + 1] - lv[i]) * a / (a - b))
    return float("nan")


def cost_sensitivity(gross: pd.Series, turn, bps_grid=(0, 5, 10, 20),
                     periods_per_year: int = 12, sides: int = 2) -> pd.DataFrame:
    """Net mean return and Sharpe across a grid of cost assumptions.

    `turn` is either a constant turnover or a series aligned with `gross`.
    Reporting the whole grid — rather than one flattering cost — is the point.
    """
    g = pd.Series(gross).dropna()
    t = pd.Series(turn, index=g.index) if np.isscalar(turn) else pd.Series(turn).reindex(g.index)
    rows = []
    for bps in bps_grid:
        net = g - t * (bps / 1e4) * sides
        rows.append({"cost_bps": bps,
                     "mean_per_period": float(net.mean()),
                     "mean_annualized": float(net.mean() * periods_per_year),
                     "sharpe": sharpe(net, periods_per_year)})
    return pd.DataFrame(rows).set_index("cost_bps")


def iv_scaled_spread(iv: float, base_spread: float = 0.05, iv_ref: float = 0.30,
                     iv_slope: float = 1.0, max_spread: float = 0.30) -> float:
    """Option spread that widens with implied volatility.

    A fixed half-spread systematically understates cost exactly where it matters
    most: in a panic, when spreads blow out and the strategy is most active. The
    spread is scaled linearly in IV relative to a calm-market reference and
    capped. Still an assumption — but no longer an optimistic one where it hurts.
    """
    if iv is None or (isinstance(iv, float) and np.isnan(iv)) or iv <= 0:
        return base_spread
    s = base_spread * (1.0 + iv_slope * (iv / iv_ref - 1.0))
    return float(min(max(s, base_spread * 0.5), max_spread))


def budget_position(unit_price: float, budget: float = 10_000.0,
                    multiplier: int = 100) -> tuple[int, float]:
    """Whole units bought for a fixed dollar budget, and the amount invested.

    Comparing option structures by percentage return flatters whatever is
    cheapest; a uniform dollar budget with integer contracts is what makes a
    0.4-delta call and a 0.8-delta call comparable.
    """
    per_unit = unit_price * multiplier
    if per_unit <= 0:
        return 0, 0.0
    n = int(budget // per_unit)
    return n, float(n * per_unit)


def budget_pnl(cost_in: float, proceeds: float, budget: float = 10_000.0,
               multiplier: int = 100) -> tuple[int, float, float]:
    """(units, dollar P&L, return on invested) for a budgeted position."""
    n, invested = budget_position(cost_in, budget, multiplier)
    if n == 0:
        return 0, 0.0, float("nan")
    pnl = n * (proceeds - cost_in) * multiplier
    return n, float(pnl), float(pnl / invested)
