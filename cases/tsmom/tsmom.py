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

    closes = raw[[c for c in raw.columns if c.endswith("_close")]]
    closes.columns = [c[:-6] for c in closes.columns]

    vols: dict[int, pd.DataFrame] = {}
    windows = sorted({int(c.split("_v")[1]) for c in raw.columns if "_v" in c})
    for w in windows:
        v = raw[[f"{s}_v{w}" for s in closes.columns]]
        v.columns = list(closes.columns)
        vols[w] = v.clip(lower=VOL_FLOOR)
    return closes, vols


def market_returns(closes: pd.DataFrame) -> pd.DataFrame:
    """Month-over-month returns. Futures price returns are already excess returns."""
    return closes.pct_change(fill_method=None)


def _size(signal: pd.DataFrame, vol: pd.DataFrame) -> pd.DataFrame:
    """Inverse-volatility sizing, shared by the strategy and every benchmark."""
    return (signal * (SIGMA_EACH / vol)).clip(-MAX_POS, MAX_POS)


def tsmom_positions(closes: pd.DataFrame, vol: pd.DataFrame, lookback: int = 12) -> pd.DataFrame:
    """The claim: position sign is the sign of this market's own trailing return."""
    return _size(np.sign(closes.pct_change(lookback, fill_method=None)), vol)


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
