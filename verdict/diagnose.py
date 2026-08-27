"""Mechanism-diagnosis playbooks — the 'why did it fail / what is it really' layer.

A verdict that stops at "it does not work" wastes the experiment. Each playbook
here turns a negative result into a mechanism, and each was distilled from a
case where it was needed:

* `false_positive` — a promising validation result against a sealed holdout.
  Did the out-of-sample block catch an artefact? (chart-cnn)
* `cost_anatomy` — is the edge alive gross and dead net, and at what cost does
  it die? (chart-cnn, vol-harvest)
* `expression_vs_underlying` — is the thesis wrong, or is the instrument used to
  express it what loses? (buy-the-dip)
* `kernel_ridgeless_forecast` — is an ostensibly complex over-parameterized
  model secretly a simple kernel smoother, whose weights read off as momentum
  and volatility timing? (complexity)
* `drift` — is a deployed model's discrimination decaying, and on what date did
  it start? (drift)
* `attribution_holds_up` — does the tempting explanation for a decay survive
  being split in time, or does it only correlate? (drift)
"""
from __future__ import annotations

import numpy as np


def expression_vs_underlying(trades, budget: float = 10000.0):
    """Playbook: does a derivative expression of a bet drag the bet's own edge?

    Given trades with S_in/S_out (the underlying's entry/exit price) and the
    derivative's dollar_pnl on the same entries/exits, compare a same-budget
    underlying position against the derivative. The 'drag' isolates the cost of
    the expression (premium, decay, path) from the merit of the underlying view.
    Distilled from the buy-the-dip case (long calls vs the stock).
    """
    import numpy as np
    v = trades.dropna(subset=["S_in", "S_out", "dollar_pnl"]).copy()
    if len(v) == 0:
        return {"n": 0}
    stock = budget * (v["S_out"].to_numpy() / v["S_in"].to_numpy() - 1.0)
    deriv = v["dollar_pnl"].to_numpy()
    sw = stock > 0
    return {
        "n": int(len(v)),
        "underlying_mean": float(stock.mean()), "underlying_median": float(np.median(stock)),
        "underlying_win": float((stock > 0).mean()),
        "deriv_mean": float(deriv.mean()), "deriv_median": float(np.median(deriv)),
        "deriv_win": float((deriv > 0).mean()),
        "expression_drag": float((deriv - stock).mean()),
        "deriv_win_when_underlying_wins": float((deriv > 0)[sw].mean()) if sw.any() else float("nan"),
    }


def false_positive(validation: dict, holdout: dict, t_threshold: float = 2.0) -> dict:
    """Playbook: did the sealed holdout catch a false positive?

    Both blocks are summarized as {"alpha": per-period alpha, "alpha_t": its
    t-statistic}. The comparison is deliberately blunt — sign and significance,
    not a story about why the holdout period was unusual.

    The reason this diagnosis is worth a name: a validation alpha at t ~ 2.4
    followed by a holdout alpha at t ~ -0.6 is not a disappointment, it is the
    sealed block doing precisely the job it was sealed for.
    """
    va, vt = float(validation["alpha"]), float(validation["alpha_t"])
    ha, ht = float(holdout["alpha"]), float(holdout["alpha_t"])
    v_sig = vt > t_threshold
    h_sig = ht > t_threshold
    sign_flip = bool(np.sign(va) != np.sign(ha))
    if v_sig and h_sig:
        verdict = "survived out of sample"
    elif v_sig and not h_sig:
        verdict = ("false positive caught by the sealed holdout"
                   if sign_flip else "did not replicate out of sample")
    elif not v_sig and h_sig:
        verdict = "no in-sample claim, yet positive out of sample — inspect the pipeline"
    else:
        verdict = "no claim in either block"
    return {"validation_alpha": va, "validation_t": vt,
            "holdout_alpha": ha, "holdout_t": ht,
            "validation_significant": bool(v_sig), "holdout_significant": bool(h_sig),
            "sign_flip": sign_flip, "alpha_decay": ha - va, "verdict": verdict}


def cost_anatomy(gross_mean: float, turn: float, realistic_bps: float,
                 sides: int = 2, periods_per_year: int = 12) -> dict:
    """Playbook: alive gross, dead net — and exactly where it dies.

    Reports the one-way cost at which the average period return reaches zero,
    the net return at a realistic cost, and how much of the gross edge the
    frictions consume. A signal whose breakeven cost sits below what the desk
    actually pays is unusable regardless of how good the predictions look.
    """
    from .costs import breakeven_cost_bps, net_return
    be = breakeven_cost_bps(gross_mean, turn, sides)
    net = net_return(gross_mean, turn, realistic_bps, sides)
    consumed = (gross_mean - net) / abs(gross_mean) if gross_mean else float("nan")
    return {"gross_mean": gross_mean, "turnover": turn,
            "gross_annualized": gross_mean * periods_per_year,
            "breakeven_cost_bps": be, "realistic_bps": realistic_bps,
            "net_mean": net, "net_annualized": net * periods_per_year,
            "cost_share_of_gross": consumed,
            "survives_costs": bool(net > 0 and gross_mean > 0)}


def drift(df, time_col: str, score_col: str, label_col: str, window: int = 150,
          min_class: int = 5, baseline_n: int = 60, cusum_k_sd: float = 1.5,
          cusum_h_sd: float = 5.0, n_boot: int = 0, block: int = 10,
          seed: int = 0) -> dict:
    """Playbook: is a deployed model's discrimination decaying, and when did it start?

    Model-agnostic by construction: it sees a time-ordered stream of
    (timestamp, score, label) and nothing else. Rolling AUC measures whether the
    score still ranks outcomes; a one-sided CUSUM on that series turns "it looks
    like it's fading" into a dated change-point, which is the difference between
    a chart and an alarm.

    The CUSUM re-arms only after the series recovers, so each sustained decline
    yields one change-point rather than an alarm every window.

    Known behaviour, stated rather than hidden: on a noisy in-control stretch the
    detector can fire on an ordinary dip, and because it stays alarmed until the
    series recovers, that early firing is then the only alarm for the episode. It
    is tuned to be early rather than precise — the intended use is a monitor that
    prompts a look, not a test that dates a change-point.

    Provenance: distribution-shift-diagnosis/src/monitor.py, whose interface is
    frozen upstream; this is a port, not a rewrite.
    """
    import pandas as pd
    from .evaluate import auc, block_bootstrap_auc_ci

    d = (df[[time_col, score_col, label_col]].dropna()
         .sort_values(time_col).reset_index(drop=True))
    t = pd.DatetimeIndex(pd.to_datetime(d[time_col]))
    y = d[label_col].to_numpy(int)
    s = d[score_col].to_numpy(float)
    rows = []
    for i in range(window, len(d) + 1):
        a, b = i - window, i
        yy, ss = y[a:b], s[a:b]
        if min(np.bincount(yy, minlength=2)[:2]) < min_class:
            continue
        lo, hi = block_bootstrap_auc_ci(yy, ss, n_boot, block, seed=seed)
        rows.append({"date": t[b - 1], "n": b - a, "auc": auc(yy, ss),
                     "auc_lo": lo, "auc_hi": hi,
                     "calib_err": abs(ss.mean() - yy.mean())})
    rolling = pd.DataFrame(rows).set_index("date")
    series = rolling["auc"].to_numpy(float)

    base = series[:baseline_n]
    base = base[np.isfinite(base)]
    baseline = float(np.mean(base)) if len(base) else float("nan")
    sd = float(np.std(base)) if len(base) > 1 else float("nan")
    sd = sd if (np.isfinite(sd) and sd > 1e-6) else 0.02
    k, h = cusum_k_sd * sd, cusum_h_sd * sd

    hits, S, alarmed = [], 0.0, False
    if np.isfinite(baseline):
        for i, v in enumerate(series):
            if not np.isfinite(v):
                continue
            S = max(0.0, S + (baseline - v - k))
            if not alarmed and S > h:
                hits.append(i); alarmed = True; S = 0.0
            elif alarmed and v >= baseline - k:      # back in control -> re-arm
                alarmed = False; S = 0.0

    alarms = [{"date": rolling.index[i], "auc": float(series[i]), "baseline": baseline}
              for i in hits]
    return {
        "rolling": rolling, "alarms": alarms,
        "summary": {
            "n_obs": int(len(d)), "n_windows": int(len(rolling)), "window": window,
            "overall_auc": auc(y, s), "baseline_auc": baseline,
            "worst_auc": float(np.nanmin(series)) if len(series) else float("nan"),
            "worst_auc_date": (rolling.index[int(np.nanargmin(series))]
                               if len(series) and np.isfinite(np.nanmin(series)) else None),
            "n_alarms": len(alarms),
            "first_alarm": (alarms[0]["date"] if alarms else None),
        }}


def attribution_holds_up(metric, driver, split_at, min_n: int = 8,
                         method: str = "spearman") -> dict:
    """Playbook: does a tempting correlation survive being split in time?

    A candidate cause that correlates with a decay over the full sample has said
    very little. The question is whether it also explains the *onset* and the
    *recovery*. Splitting the sample is the cheapest way to find out, and a sign
    flip after the split is the signature of coincidence rather than cause.

    Provenance: the 0DTE attribution in the drift case, generalized.
    """
    import pandas as pd
    m = pd.Series(metric).dropna()
    dvr = pd.Series(driver).reindex(m.index).dropna()
    m = m.reindex(dvr.index)
    split_at = pd.Timestamp(split_at)
    pre, post = m.index < split_at, m.index >= split_at
    full_r = float(m.corr(dvr, method=method))
    pre_r = float(m[pre].corr(dvr[pre], method=method)) if pre.sum() >= min_n else float("nan")
    post_r = float(m[post].corr(dvr[post], method=method)) if post.sum() >= min_n else float("nan")
    flips = bool(np.isfinite(post_r) and np.isfinite(full_r)
                 and np.sign(post_r) != np.sign(full_r))
    return {"method": method,
            "corr_full": full_r, "corr_before": pre_r, "corr_after": post_r,
            "n_before": int(pre.sum()), "n_after": int(post.sum()),
            "sign_flips_after_split": flips,
            "verdict": ("coincides but does not explain — the relationship reverses "
                        "after the split" if flips else
                        "relationship is stable across the split")}


def kernel_weights(X: np.ndarray, T: int, gamma: float) -> np.ndarray:
    """Per-window Gaussian-kernel ridgeless weights on the T training returns.

    Returns W with shape (n, T); row t holds the weights on R[t-T:t] that the
    kernel forecast would apply, so forecast(R)[t] = W[t] @ R[t-T:t]. Rows
    before T are NaN. Weights depend ONLY on X — the whole point — so they can
    be reused to forecast any return series (real, reversal, bootstrap) cheaply.
    """
    n = len(X)
    W = np.full((n, T), np.nan)
    for t in range(T, n):
        Xtr, xt = X[t - T:t], X[t]
        D = ((Xtr[:, None, :] - Xtr[None, :, :]) ** 2).sum(-1)
        Ktr = np.exp(-gamma ** 2 / 2 * D)
        k = np.exp(-gamma ** 2 / 2 * ((Xtr - xt) ** 2).sum(1))
        W[t] = k @ np.linalg.pinv(Ktr)
    return W


def apply_weights(W: np.ndarray, R: np.ndarray) -> np.ndarray:
    """forecast[t] = W[t] @ R[t-T:t]; NaN where W is NaN."""
    n, T = W.shape
    fc = np.full(n, np.nan)
    for t in range(T, n):
        fc[t] = float(W[t] @ R[t - T:t])
    return fc


def kernel_ridgeless_forecast(X: np.ndarray, R: np.ndarray, T: int, gamma: float):
    """Rolling Gaussian-kernel ridgeless one-step forecast + weight structure.

    The P->inf limit of RFF ridgeless regression is kernel ridgeless with the
    Gaussian kernel k(x, x') = exp(-gamma^2/2 ||x - x'||^2). The forecast is a
    weighted average of the T training returns, with weights determined ONLY by
    predictor similarity (never by R) -- which is exactly why it is mechanical.

    Returns dict with:
      forecast          : (n,) kernel forecast aligned to R (NaN before T)
      weight_by_lag     : (T,) average weight, index 0 = most recent lag
      recency_corr      : corr(weight_by_lag, recency)  > 0 => momentum weighting
      scale_vs_predvol  : corr(|weights|.sum(), predictor innovation vol) < 0 => vol timing
    """
    n = len(R)
    fc = np.full(n, np.nan)
    wlag = np.zeros(T)
    scale, pvol = [], []
    for t in range(T, n):
        Xtr, Rtr, xt = X[t - T:t], R[t - T:t], X[t]
        D = ((Xtr[:, None, :] - Xtr[None, :, :]) ** 2).sum(-1)
        Ktr = np.exp(-gamma ** 2 / 2 * D)
        k = np.exp(-gamma ** 2 / 2 * ((Xtr - xt) ** 2).sum(1))
        w = k @ np.linalg.pinv(Ktr)          # weights on Rtr; depend only on X
        fc[t] = float(w @ Rtr)
        wlag += w[::-1]                        # w[-1] = most-recent lag -> index 0
        scale.append(float(np.abs(w).sum()))
        pvol.append(float(np.mean(np.std(np.diff(Xtr, axis=0), axis=0))))
    wlag /= (n - T)
    recency = np.arange(T, 0, -1, dtype=float)
    return {
        "forecast": fc,
        "weight_by_lag": wlag,
        "recency_corr": float(np.corrcoef(wlag, recency)[0, 1]),
        "scale_vs_predvol": float(np.corrcoef(np.array(scale), np.array(pvol))[0, 1]),
    }
