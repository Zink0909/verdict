"""Evaluation: spanning regressions, bootstrap inference, OOS R^2, CW/DM tests.

Extracted from the chart-cnn and buy-the-dip cases (spanning + block bootstrap)
and extended for the complexity case with the formal forecast-comparison tests
used in the Fed FX protocol (Clark-West for nested models, Diebold-Mariano for
non-nested).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm


def sharpe(returns, periods_per_year: int = 12) -> float:
    r = pd.Series(returns).dropna()
    if len(r) < 2 or r.std(ddof=1) == 0:
        return float("nan")
    return float(r.mean() / r.std(ddof=1) * np.sqrt(periods_per_year))


def block_bootstrap_sharpe_ci(returns, n_boot: int = 2000, block: int = 6,
                              ci: float = 0.95, seed: int = 0,
                              periods_per_year: int = 12):
    """Moving-block bootstrap CI for the annualized Sharpe ratio."""
    r = pd.Series(returns).dropna().to_numpy()
    if len(r) < block * 2:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(len(r) / block))
    stats = []
    for _ in range(n_boot):
        starts = rng.integers(0, len(r) - block + 1, size=n_blocks)
        samp = np.concatenate([r[s:s + block] for s in starts])[:len(r)]
        sd = samp.std(ddof=1)
        stats.append(samp.mean() / sd * np.sqrt(periods_per_year) if sd > 0 else np.nan)
    lo = np.nanpercentile(stats, (1 - ci) / 2 * 100)
    hi = np.nanpercentile(stats, (1 + ci) / 2 * 100)
    return (float(lo), float(hi))


def spanning(y, X: pd.DataFrame, hac_lags: int = 3) -> dict:
    """Regress a return series on benchmark factors; the surviving alpha is the
    incremental content beyond what the benchmarks already deliver.

    Returns alpha (per period), its HAC t-stat, betas, R^2, nobs.
    """
    df = pd.concat([pd.Series(y, name="y"), pd.DataFrame(X)], axis=1).dropna()
    if len(df) < df.shape[1] + 3:
        raise ValueError("not enough observations for spanning regression")
    Xc = sm.add_constant(df.iloc[:, 1:])
    res = sm.OLS(df["y"], Xc).fit(cov_type="HAC", cov_kwds={"maxlags": hac_lags})
    return {
        "alpha": float(res.params["const"]),
        "alpha_t": float(res.tvalues["const"]),
        "betas": {c: float(res.params[c]) for c in df.columns[1:]},
        "beta_t": {c: float(res.tvalues[c]) for c in df.columns[1:]},
        "r2": float(res.rsquared),
        "nobs": int(res.nobs),
    }


def oos_r2(actual, forecast, benchmark=None) -> float:
    """Campbell-Thompson out-of-sample R^2 vs a benchmark forecast.

    benchmark defaults to the expanding mean of `actual` (the classic
    prevailing-mean benchmark). All arrays aligned; NaNs dropped pairwise.
    """
    a = pd.Series(actual, dtype=float)
    f = pd.Series(forecast, dtype=float)
    if benchmark is None:
        b = a.expanding().mean().shift(1)
    else:
        b = pd.Series(benchmark, dtype=float)
    df = pd.concat([a, f, b], axis=1).dropna()
    if len(df) == 0:
        return float("nan")
    a, f, b = df.iloc[:, 0], df.iloc[:, 1], df.iloc[:, 2]
    denom = ((a - b) ** 2).sum()
    if denom == 0:
        return float("nan")
    return float(1.0 - ((a - f) ** 2).sum() / denom)


def auc(labels, scores) -> float:
    """Area under the ROC curve, via the Mann-Whitney identity (exact, ties averaged).

    Discrimination rather than accuracy: it asks only whether the score ranks a
    positive above a negative, which is the right question for a weak signal
    whose calibration is not the claim.
    """
    df = pd.concat([pd.Series(labels, name="y"), pd.Series(scores, name="s")],
                   axis=1).dropna()
    if df.empty:
        return float("nan")
    y = df["y"].to_numpy()
    pos, neg = (y == 1), (y == 0)
    n_p, n_n = int(pos.sum()), int(neg.sum())
    if n_p == 0 or n_n == 0:
        return float("nan")
    r = df["s"].rank().to_numpy()
    return float((r[pos].sum() - n_p * (n_p + 1) / 2) / (n_p * n_n))


def block_bootstrap_auc_ci(labels, scores, n_boot: int = 200, block: int = 10,
                           ci: float = 0.90, seed: int = 0):
    """Moving-block bootstrap CI for AUC — blocks respect serial dependence.

    An i.i.d. bootstrap on an autocorrelated prediction stream reports a band
    that is too narrow, which is how a signal indistinguishable from chance ends
    up looking significant.
    """
    df = pd.concat([pd.Series(labels, name="y"), pd.Series(scores, name="s")],
                   axis=1).dropna().reset_index(drop=True)
    n = len(df)
    if n_boot <= 0 or n < 2 * block or df["y"].nunique() < 2:
        return (float("nan"), float("nan"))
    y = df["y"].to_numpy(); s = df["s"].to_numpy()
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(n / block))
    out = []
    for _ in range(n_boot):
        starts = rng.integers(0, n - block + 1, size=n_blocks)
        idx = np.concatenate([np.arange(st, st + block) for st in starts])[:n]
        a = auc(y[idx], s[idx])
        if a == a:
            out.append(a)
    if not out:
        return (float("nan"), float("nan"))
    lo = float(np.percentile(out, (1 - ci) / 2 * 100))
    hi = float(np.percentile(out, (1 + ci) / 2 * 100))
    return (lo, hi)


def _hac_tstat(d: np.ndarray, lags: int) -> float:
    """t-stat of mean(d) with Newey-West HAC standard error."""
    d = np.asarray(d, dtype=float)
    d = d[~np.isnan(d)]
    n = len(d)
    if n < 5:
        return float("nan")
    dbar = d.mean()
    u = d - dbar
    gamma0 = (u @ u) / n
    var = gamma0
    for k in range(1, min(lags, n - 1) + 1):
        w = 1.0 - k / (lags + 1)
        var += 2 * w * (u[k:] @ u[:-k]) / n
    se = np.sqrt(var / n)
    return float(dbar / se) if se > 0 else float("nan")


def clark_west(actual, f_small, f_big, hac_lags: int = 3) -> dict:
    """Clark-West test for nested models (is the big model's forecast better
    than the nested small one, adjusting for estimated-parameter noise?).

    One-sided: t > 1.645 rejects equal MSPE at 5% in favour of the big model.
    """
    a = np.asarray(actual, dtype=float)
    fs = np.asarray(f_small, dtype=float)
    fb = np.asarray(f_big, dtype=float)
    adj = (a - fs) ** 2 - ((a - fb) ** 2 - (fs - fb) ** 2)
    t = _hac_tstat(adj, hac_lags)
    return {"cw_t": t, "reject_5pct": bool(t > 1.645) if t == t else False}


def diebold_mariano(actual, f1, f2, hac_lags: int = 3) -> dict:
    """Diebold-Mariano test (squared-error loss). Positive t favours f2."""
    a = np.asarray(actual, dtype=float)
    d = (a - np.asarray(f1, dtype=float)) ** 2 - (a - np.asarray(f2, dtype=float)) ** 2
    t = _hac_tstat(d, hac_lags)
    return {"dm_t": t}
