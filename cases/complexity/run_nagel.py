#!/usr/bin/env python3
"""M3: Nagel's three diagnostics — the actual adjudication.

The claim under audit (KMZ): a massively over-parameterized RFF ridge model
times the market out-of-sample, even in T=12 windows. Nagel's counter: the
strategy is mechanical, not learned — in the P>>T ridgeless limit the RFF
forecast is a kernel-weighted average of the T training returns whose weights
are fixed by predictor similarity (hence recency = momentum) and shrink with
predictor volatility (hence volatility timing). Three experiments test this:

  (1) MECHANICAL SPANNING. Build Nagel's volatility-timed momentum benchmark and
      regress the KMZ strategy's returns on it. If the benchmark absorbs the
      strategy (residual alpha insignificant, high R^2), the "complexity" adds
      nothing beyond a mechanical rule.

  (2) REVERSAL WORLD. Inject an MA(2) component with strong negative
      autocorrelation into the returns, so the data now rewards reversal, not
      momentum. Re-run the FULL RFF pipeline. If the strategy still builds the
      same momentum positions and now LOSES (negative abnormal return), it never
      learned momentum was present — it mechanically manufactures it.

  (3) WILD BOOTSTRAP. Destroy the predictors' predictive content while keeping
      their persistence and heteroskedasticity, then re-run. If performance is
      unchanged, it was never coming from the predictors' information.

All three use the KMZ headline config (P=12000, near-ridgeless z=1e-3, T=12,
gamma=2), averaging the strategy over RFF seeds. Conclusions are read off the
distribution across seeds/draws, never a single run.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
from verdict import features as F      # noqa: E402
from verdict import evaluate as E      # noqa: E402
from verdict import synthetic as S     # noqa: E402

DATA = HERE / "data"
RESULTS = HERE / "results"

P, T, GAMMA, Z = 12000, 12, 2.0, 1e-3


def load():
    proc = pd.read_parquet(DATA / "processed.parquet")
    X = proc.drop(columns=["R"]).to_numpy(float)
    R = proc["R"].to_numpy(float)
    return X, R, proc.index


def kmz_strategy_returns(X, R, seeds):
    """Ensemble KMZ timing-strategy returns (mean over RFF seeds). Returns a
    (n,) array aligned to R, NaN before T."""
    accum = None
    for s in seeds:
        Phi = F.rff(X, P, gamma=GAMMA, seed=s)
        fc = F.rolling_forecasts(Phi, R, T, [Z])[0]
        accum = fc if accum is None else accum + fc
    fc_mean = accum / len(seeds)
    return fc_mean * R, fc_mean


# ----- (1) mechanical volatility-timed momentum benchmark -----

def mechanical_benchmark(X, R):
    """Nagel's benchmark: recency-weighted average of the past T returns
    (linearly declining weights), scaled by inverse predictor-innovation
    volatility over the same window. Returns (strategy_returns, forecast).

    Note: this is a faithful but approximate rendering of Nagel's exact
    construction; the spanning conclusion is robust to the precise weighting
    (any recency-weighted, vol-scaled momentum should span if he is right).
    """
    n = len(R)
    w = np.arange(T, 0, -1, dtype=float)          # T, T-1, ..., 1 (most recent first)
    w /= w.sum()
    dX = np.vstack([np.zeros((1, X.shape[1])), np.diff(X, axis=0)])  # predictor innovations
    fc = np.full(n, np.nan)
    for t in range(T, n):
        past = R[t - T:t][::-1]                    # most recent first: R[t-1], R[t-2], ...
        mom = float(w @ past)
        sig_pred = np.mean(np.std(dX[t - T:t], axis=0)) + 1e-12
        fc[t] = mom / sig_pred
    return fc * R, fc


def kernel_ridgeless_forecast(X, R):
    """Direct Gaussian-kernel ridgeless forecast — the mechanism itself.

    The P->inf limit of RFF ridgeless is kernel ridgeless with the Gaussian
    kernel k(x,x') = exp(-gamma^2/2 ||x-x'||^2). Its forecast is a weighted
    average of the T training returns, weights w = k(x_t, X_train) K^{-1}
    determined ONLY by predictor similarity (not by R). We compute it directly
    on real data and (a) correlate with the RFF forecast (confirms equivalence
    off synthetic data too), (b) profile weights by lag (recency = momentum),
    (c) relate forecast scale to predictor volatility (volatility timing).
    """
    n = len(R)
    fc = np.full(n, np.nan)
    wlag = np.zeros(T)          # index 0 = most recent lag
    scale, pvol = [], []
    for t in range(T, n):
        Xtr, Rtr, xt = X[t - T:t], R[t - T:t], X[t]
        D = ((Xtr[:, None, :] - Xtr[None, :, :]) ** 2).sum(-1)
        Ktr = np.exp(-GAMMA ** 2 / 2 * D)
        d = ((Xtr - xt) ** 2).sum(1)
        k = np.exp(-GAMMA ** 2 / 2 * d)
        w = k @ np.linalg.pinv(Ktr)         # weights on Rtr (depend only on X)
        fc[t] = float(w @ Rtr)
        wlag += w[::-1]                       # w[-1] is most-recent lag -> index 0
        scale.append(float(np.abs(w).sum()))
        pvol.append(float(np.mean(np.std(np.diff(Xtr, axis=0), axis=0))))
    wlag /= (n - T)
    scale, pvol = np.array(scale), np.array(pvol)
    scale_vol_corr = float(np.corrcoef(scale, pvol)[0, 1])
    return fc, wlag, scale_vol_corr


def diagnostic_1(X, R, seeds):
    strat_kmz, fc_kmz = kmz_strategy_returns(X, R, seeds)
    # (a) direct kernel-equivalence on real data — the mechanism itself
    fc_ker, wlag, scale_vol_corr = kernel_ridgeless_forecast(X, R)
    strat_ker = fc_ker * R
    mk = ~np.isnan(fc_kmz) & ~np.isnan(fc_ker)
    ker_fc_corr = float(np.corrcoef(fc_kmz[mk], fc_ker[mk])[0, 1])
    span_ker = E.spanning(pd.Series(strat_kmz[mk]),
                          pd.DataFrame({"kernel": strat_ker[mk]}))
    # weight-profile momentum: correlation of avg weight with recency (index 0 = recent)
    recency = np.arange(T, 0, -1, dtype=float)
    wlag_recency_corr = float(np.corrcoef(wlag, recency)[0, 1])
    # (b) Nagel's simplified momentum proxy (secondary; crude on purpose)
    strat_mech, fc_mech = mechanical_benchmark(X, R)
    mm = ~np.isnan(strat_kmz) & ~np.isnan(strat_mech)
    span_mech = E.spanning(pd.Series(strat_kmz[mm]),
                           pd.DataFrame({"mech": strat_mech[mm]}))
    return {
        "kmz_SR": E.sharpe(pd.Series(strat_kmz[mk])),
        "kernel_SR": E.sharpe(pd.Series(strat_ker[mk])),
        "kernel_forecast_corr": ker_fc_corr,           # RFF forecast vs kernel forecast
        "kernel_spanning_alpha_t": span_ker["alpha_t"],
        "kernel_spanning_r2": span_ker["r2"],
        "weight_recency_corr": wlag_recency_corr,       # >0 = momentum weighting
        "scale_vs_predvol_corr": scale_vol_corr,        # <0 = volatility timing
        "wlag_profile": [round(x, 4) for x in wlag],
        "mom_proxy_forecast_corr": float(np.corrcoef(fc_kmz[mm], fc_mech[mm])[0, 1]),
        "mom_proxy_spanning_alpha_t": span_mech["alpha_t"],
        "mom_proxy_spanning_r2": span_mech["r2"],
    }


# ----- (2) reversal world -----

def diagnostic_2(X, R, seeds, draws, scale=1.0):
    """Inject MA(2) reversal into returns; rerun full pipeline; expect negative."""
    out = []
    for d in draws:
        R_rev = S.reversal_world(R, theta1=-0.8, theta2=-0.4, scale=scale, seed=d)
        strat, _ = kmz_strategy_returns(X, R_rev, seeds)
        mask = ~np.isnan(strat)
        out.append(E.sharpe(pd.Series(strat[mask])))
    # also confirm real-data SR for reference with same seeds
    strat_real, _ = kmz_strategy_returns(X, R, seeds)
    m = ~np.isnan(strat_real)
    return {
        "real_SR": E.sharpe(pd.Series(strat_real[m])),
        "reversal_SR_mean": float(np.mean(out)),
        "reversal_SR_std": float(np.std(out)),
        "reversal_SR_draws": [round(x, 3) for x in out],
        "share_negative": float(np.mean(np.array(out) < 0)),
    }


# ----- (3) wild bootstrap -----

def diagnostic_3(X, R, seeds, draws):
    """Destroy predictive content of X (keep persistence); expect unchanged SR."""
    out = []
    for d in draws:
        Xb = S.wild_bootstrap_predictors(X, seed=d)
        strat, _ = kmz_strategy_returns(Xb, R, seeds)
        mask = ~np.isnan(strat)
        out.append(E.sharpe(pd.Series(strat[mask])))
    strat_real, _ = kmz_strategy_returns(X, R, seeds)
    m = ~np.isnan(strat_real)
    return {
        "real_SR": E.sharpe(pd.Series(strat_real[m])),
        "bootstrap_SR_mean": float(np.mean(out)),
        "bootstrap_SR_std": float(np.std(out)),
        "bootstrap_SR_draws": [round(x, 3) for x in out],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    RESULTS.mkdir(exist_ok=True)
    X, R, idx = load()
    if a.quick:
        seeds, draws = range(3), range(3)
    else:
        seeds, draws = range(5), range(8)

    print("=== Diagnostic 1: mechanism = kernel-weighted momentum ===", flush=True)
    t0 = time.time()
    d1 = diagnostic_1(X, R, seeds)
    for k, v in d1.items():
        if isinstance(v, list):
            print(f"  {k:26s} {v}")
        else:
            print(f"  {k:26s} {v:.4f}")
    print(f"  ({time.time()-t0:.0f}s)", flush=True)

    print("\n=== Diagnostic 2: reversal world (expect negative if mechanical) ===", flush=True)
    t0 = time.time()
    d2 = diagnostic_2(X, R, seeds, draws)
    print(f"  real_SR            {d2['real_SR']:.3f}")
    print(f"  reversal_SR        {d2['reversal_SR_mean']:.3f} +/- {d2['reversal_SR_std']:.3f}")
    print(f"  share_negative     {d2['share_negative']:.2f}")
    print(f"  draws              {d2['reversal_SR_draws']}")
    print(f"  ({time.time()-t0:.0f}s)", flush=True)

    print("\n=== Diagnostic 3: wild bootstrap (expect unchanged if mechanical) ===", flush=True)
    t0 = time.time()
    d3 = diagnostic_3(X, R, seeds, draws)
    print(f"  real_SR            {d3['real_SR']:.3f}")
    print(f"  bootstrap_SR       {d3['bootstrap_SR_mean']:.3f} +/- {d3['bootstrap_SR_std']:.3f}")
    print(f"  draws              {d3['bootstrap_SR_draws']}")
    print(f"  ({time.time()-t0:.0f}s)", flush=True)

    import json
    (RESULTS / "nagel_diagnostics.json").write_text(
        json.dumps({"d1": d1, "d2": d2, "d3": d3}, indent=2))
    print(f"\nsaved {RESULTS / 'nagel_diagnostics.json'}")


if __name__ == "__main__":
    main()
