"""Construction of the time-series momentum strategy and its three benchmarks.

Everything the protocol compares lives in this one module on purpose. The
strategy and the benchmarks that are supposed to explain it away must share the
same panel, the same sizing scheme, the same lag convention and the same
return accounting, or a difference between them is a difference in plumbing
rather than a difference in information.

Lag convention, stated once and enforced everywhere: a position dated ``t`` is
computed from information available at ``t`` and earns the return from ``t`` to
``t+1``. `portfolio_returns` does the shifting, so no construction function may
shift anything itself.

Portfolio-level volatility targeting is deliberately *not* applied. It is a
scalar multiplier, so it changes no test statistic in the protocol — not the
spanning alpha's t, not the bootstrap interval's sign, not the breakeven cost —
while an expanding-window version would add path dependence that makes the
sign-randomisation comparison harder to read. Realised volatility is reported
instead, and the reader can scale mentally.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

SECTORS = {"energy": ["CL", "NG"], "metals": ["GC", "HG"], "grains": ["ZC", "ZS", "ZW"]}
SIGMA_EACH = 0.15      # per-market ex-ante volatility budget
MAX_POS = 4.0          # position cap, as in the source construction
VOL_FLOOR = 0.05       # keeps a quiet market from demanding an enormous position

# Dollar P&L for a one-unit price move in the standard contract. The energy and
# metals series are quoted in dollars per physical unit; the grain execution
# series exported by QuantConnect is also expressed in dollars per bushel.
CONTRACT_POINT_VALUE = {
    "CL": 1_000.0,     # 1,000 barrels
    "NG": 10_000.0,    # 10,000 MMBtu
    "GC": 100.0,       # 100 troy ounces
    "HG": 25_000.0,    # 25,000 pounds
    "ZC": 5_000.0,     # 5,000 bushels
    "ZS": 5_000.0,
    "ZW": 5_000.0,
}


def load_panel(path, today=None) -> tuple[pd.DataFrame, dict[int, pd.DataFrame]]:
    """Read the exported month-end panel into closes and per-window volatilities.

    Drops a final row labelled in the future. QuantConnect's month-end resample
    stamps the current, unfinished month with its calendar month-end, so the last
    row of a mid-month export holds a partial month wearing a full month's date.
    It is not future information — the values are as of the last traded bar — but
    treating a three-week stub as a monthly return would quietly corrupt the most
    recent observation, which is the one a reader looks at hardest.
    """
    raw = pd.read_csv(path, index_col=0, comment="#", parse_dates=True)
    raw.index = pd.DatetimeIndex(raw.index).normalize()
    raw = raw.sort_index()

    cutoff = pd.Timestamp(today or pd.Timestamp.today().normalize())
    raw = raw[raw.index <= cutoff]

    close_columns = [c for c in raw.columns
                     if c.endswith("_close") and not c.endswith("_trade_close")]
    closes = raw[close_columns]
    closes.columns = [c[:-6] for c in closes.columns]

    vols: dict[int, pd.DataFrame] = {}
    windows = sorted({int(c.split("_v")[1]) for c in raw.columns if "_v" in c})
    for w in windows:
        v = raw[[f"{s}_v{w}" for s in closes.columns]]
        v.columns = list(closes.columns)
        vols[w] = v.clip(lower=VOL_FLOOR)
    return closes, vols


def load_execution_prices(path, markets, today=None) -> pd.DataFrame | None:
    """Load unadjusted mapped-contract prices needed for integer contract sizing.

    Backwards-ratio continuous levels are valid for percentage returns but not
    for contract notionals: their historical scale has been changed at every
    roll. The account-space calculation therefore refuses to substitute them.
    Older exports without ``*_trade_close`` return ``None`` and keep this part
    of the protocol explicitly data-gated.
    """
    raw = pd.read_csv(path, index_col=0, comment="#", parse_dates=True)
    raw.index = pd.DatetimeIndex(raw.index).normalize()
    raw = raw.sort_index()
    cutoff = pd.Timestamp(today or pd.Timestamp.today().normalize())
    raw = raw[raw.index <= cutoff]
    names = list(markets)
    columns = [f"{name}_trade_close" for name in names]
    if not all(column in raw for column in columns):
        return None
    prices = raw[columns].copy()
    prices.columns = names
    if (prices.dropna() <= 0).any().any():
        raise ValueError("mapped-contract execution prices must be positive")
    return prices


def market_returns(closes: pd.DataFrame) -> pd.DataFrame:
    """Month-over-month returns. Futures price returns are already excess returns."""
    return closes.pct_change(fill_method=None)


def _size(signal: pd.DataFrame, vol: pd.DataFrame) -> pd.DataFrame:
    """Inverse-volatility sizing, shared by the strategy and every benchmark."""
    return (signal * (SIGMA_EACH / vol)).clip(-MAX_POS, MAX_POS)


def tsmom_positions(closes: pd.DataFrame, vol: pd.DataFrame, lookback: int = 12) -> pd.DataFrame:
    """The claim: position sign is the sign of this market's own trailing return."""
    return _size(np.sign(closes.pct_change(lookback, fill_method=None)), vol)


def holding_period_positions(positions: pd.DataFrame, months: int) -> pd.DataFrame:
    """Equal-weight overlapping formation vintages held for ``months`` months.

    A one-month holding period is the registered baseline. Longer periods keep
    each monthly signal alive and average the active vintages, without adding
    leverage. The eventual one-period lag remains owned by ``portfolio_returns``.
    """
    if not isinstance(months, int) or months <= 0:
        raise ValueError("holding period must be a positive integer")
    return positions.rolling(months, min_periods=months).mean()


def most_correlated_pair(rets: pd.DataFrame) -> tuple[str, str, float]:
    """Return the pair with the largest absolute contemporaneous correlation."""
    corr = rets.corr(min_periods=24)
    if corr.shape[0] < 2:
        raise ValueError("at least two markets are required")
    mask = np.triu(np.ones(corr.shape, dtype=bool), k=1)
    pairs = corr.where(mask).stack()
    if pairs.empty:
        raise ValueError("no market pair has 24 overlapping returns")
    left, right = pairs.abs().idxmax()
    return str(left), str(right), float(corr.loc[left, right])


def integer_contract_positions(desired: pd.DataFrame, execution_prices: pd.DataFrame,
                               capital: float, point_values=None) -> pd.DataFrame:
    """Round desired equal-sleeve exposure to tradable standard contracts."""
    if not np.isfinite(capital) or capital <= 0:
        raise ValueError("capital must be positive and finite")
    prices = execution_prices.reindex(index=desired.index, columns=desired.columns)
    values = CONTRACT_POINT_VALUE if point_values is None else point_values
    missing = [column for column in desired if column not in values]
    if missing:
        raise ValueError(f"missing contract point value(s): {', '.join(missing)}")
    if (prices.dropna() <= 0).any().any():
        raise ValueError("execution prices must be positive")
    active = desired.notna() & prices.notna()
    n_active = active.sum(axis=1).replace(0, np.nan)
    target_dollars = desired.mul(capital / n_active, axis=0)
    notionals = prices.mul(pd.Series(values), axis=1)
    contracts = (target_dollars / notionals).round().where(active)
    return contracts


def integer_contract_returns(contracts: pd.DataFrame, execution_prices: pd.DataFrame,
                             adjusted_returns: pd.DataFrame, capital: float,
                             point_values=None) -> pd.Series:
    """Account return from lagged lots, actual notionals and roll-clean returns.

    A raw continuous price difference crosses different contracts at a mapping
    event and contains the calendar-spread gap. Dollar P&L is therefore the
    prior mapped contract notional times the validated BackwardsRatio return,
    never the difference of two raw continuous levels.
    """
    if not np.isfinite(capital) or capital <= 0:
        raise ValueError("capital must be positive and finite")
    prices = execution_prices.reindex(index=contracts.index, columns=contracts.columns)
    values = CONTRACT_POINT_VALUE if point_values is None else point_values
    missing = [column for column in contracts if column not in values]
    if missing:
        raise ValueError(f"missing contract point value(s): {', '.join(missing)}")
    returns = adjusted_returns.reindex(index=contracts.index, columns=contracts.columns)
    pnl = contracts.shift(1) * prices.shift(1) * returns * pd.Series(values)
    return (pnl.sum(axis=1, min_count=1) / capital).dropna()


def integer_contract_turnover(contracts: pd.DataFrame, execution_prices: pd.DataFrame,
                              capital: float, point_values=None) -> pd.Series:
    """Conservative monthly roll + rebalance notional divided by capital.

    Every monthly decision is treated as closing the prior mapped contract and
    opening the new one. This can overcharge quarterly contracts, but cannot
    hide roll turnover when the current export lacks historical mapping IDs.
    """
    if not np.isfinite(capital) or capital <= 0:
        raise ValueError("capital must be positive and finite")
    prices = execution_prices.reindex(index=contracts.index, columns=contracts.columns)
    values = CONTRACT_POINT_VALUE if point_values is None else point_values
    previous = contracts.shift(1).fillna(0.0).abs()
    current = contracts.fillna(0.0).abs()
    traded = (previous + current) * prices * pd.Series(values)
    return (traded.sum(axis=1, min_count=1) / capital).dropna()


def passive_positions(closes: pd.DataFrame, vol: pd.DataFrame, lookback: int = 12) -> pd.DataFrame:
    """Benchmark 1 — always long, identically sized.

    A rule that is long more often than short collects the asset class's risk
    premium without predicting anything. This benchmark charges the strategy for
    that. The lookback argument is unused except to align the start date, so the
    two series cover exactly the same months.
    """
    valid = closes.pct_change(lookback, fill_method=None).notna()
    return _size(valid.astype(float), vol)


def xsmom_positions(closes: pd.DataFrame, vol: pd.DataFrame, lookback: int = 12) -> pd.DataFrame:
    """Benchmark 2 — cross-sectional momentum on the same universe.

    Rank markets by trailing return, demean the ranks, and go long the winners
    against the losers. This is the obvious thing time-series momentum could be
    a repackaging of; it is dollar-neutral in signal space by construction, which
    is exactly what separates it from benchmark 1.
    """
    trailing = closes.pct_change(lookback, fill_method=None)
    ranks = trailing.rank(axis=1, pct=True)
    signal = 2.0 * (ranks.sub(ranks.mean(axis=1), axis=0))
    return _size(signal, vol)


def randomized_sign_positions(closes: pd.DataFrame, vol: pd.DataFrame,
                              lookback: int = 12, seed: int = 0) -> pd.DataFrame:
    """Benchmark 3 — the sizing scheme with the timing decision destroyed.

    Position magnitudes are exactly the strategy's; only the signs are replaced
    by fair coin flips. If this performs as well as the strategy, the inverse
    volatility scaling is doing the work and the momentum signal is decoration.
    """
    base = tsmom_positions(closes, vol, lookback)
    rng = np.random.default_rng(seed)
    signs = pd.DataFrame(rng.choice([-1.0, 1.0], size=base.shape),
                         index=base.index, columns=base.columns)
    return base.abs() * signs


def portfolio_returns(positions: pd.DataFrame, rets: pd.DataFrame) -> pd.Series:
    """Equal-weighted across markets, with the one lag the whole case depends on.

    ``positions`` dated t are shifted forward one month before meeting returns,
    so nothing earns a return in the month that produced its own signal.
    """
    held = positions.shift(1)
    contrib = held * rets
    return contrib.mean(axis=1, skipna=True).dropna()


def per_market_contributions(positions: pd.DataFrame, rets: pd.DataFrame) -> pd.DataFrame:
    """The same arithmetic, kept un-aggregated so one market cannot hide in an average."""
    return (positions.shift(1) * rets).dropna(how="all")


def turnover(positions: pd.DataFrame) -> pd.Series:
    """Gross position change per rebalance, averaged across markets."""
    return positions.diff().abs().mean(axis=1, skipna=True).dropna()


def decompose(positions: pd.DataFrame, rets: pd.DataFrame) -> pd.DataFrame:
    """Split the return into the net tilt and the timing decision.

    At each date the cross-market average position is the net long/short tilt;
    what remains after removing it is the part that depends on which markets the
    rule chose to be long. If the first column carries the result, the claim is
    about exposure rather than prediction.
    """
    tilt_pos = positions.mean(axis=1, skipna=True)
    tilt = positions.mul(0.0).add(tilt_pos, axis=0)
    timing = positions.sub(tilt_pos, axis=0)
    return pd.DataFrame({
        "tilt": portfolio_returns(tilt, rets),
        "timing": portfolio_returns(timing, rets),
    }).dropna()
