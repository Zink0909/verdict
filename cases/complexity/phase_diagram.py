#!/usr/bin/env python3
"""M4: the phase diagram — where is the 'virtue' mechanical vs potentially real?

Nagel's critique bites in the SHORT-window regime (T=12), where the kernel
forecast weights recent returns (momentum). It does not deny that a complex
model can genuinely learn over a LONG training sample. The axis that separates
the two is T (training-window length).

Efficiency: we established (M3) that the RFF ridgeless forecast is numerically
the kernel ridgeless forecast (corr 0.997). The kernel weights depend only on
the predictors, not the returns, so we compute them once per T and reuse them
across the real, reversal, and bootstrap return series — making the whole T-sweep
cheap. We re-confirm kernel≈RFF at a few T points as an anchor.

For each T in {12, 24, 60, 120, 240} we report:
  - kernel strategy Sharpe (the 'virtue' as T grows)
  - momentum signature: recency correlation of the average weight profile
  - volatility-timing signature: scale-vs-predictor-vol correlation
  - reversal-world Sharpe (does injecting reversal still flip it negative?)
and, at T in {12, 60, 120}, the kernel-vs-RFF forecast correlation (anchor).
"""
from __future__ import annotations

import argparse
import json
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
from verdict import diagnose as D      # noqa: E402

DATA = HERE / "data"
RESULTS = HERE / "results"
GAMMA = 2.0


def load():
    proc = pd.read_parquet(DATA / "processed.parquet")
    return proc.drop(columns=["R"]).to_numpy(float), proc["R"].to_numpy(float)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    a = ap.parse_args()
    RESULTS.mkdir(exist_ok=True)
    X, R = load()
    T_grid = [12, 24, 60, 120] if a.quick else [12, 24, 60, 120, 240]
    anchor_T = {12, 60}
    rev_draws = range(3) if a.quick else range(6)

    rows = {}
    for T in T_grid:
        t0 = time.time()
        W = D.kernel_weights(X, T, GAMMA)              # once; reused for all R
        fc = D.apply_weights(W, R)
        m = ~np.isnan(fc)
        strat = fc * R
        # momentum / vol-timing signatures from the average weight profile
        wlag = np.nanmean(W[m][:, ::-1], axis=0)       # index 0 = most recent lag
        recency = np.arange(T, 0, -1, dtype=float)
        recency_corr = float(np.corrcoef(wlag, recency)[0, 1])
        scale = np.nansum(np.abs(W[m]), axis=1)
        dX = np.vstack([np.zeros((1, X.shape[1])), np.diff(X, axis=0)])
        pvol = np.array([np.mean(np.std(dX[t - T:t], axis=0)) for t in np.where(m)[0]])
        scale_vol = float(np.corrcoef(scale, pvol)[0, 1])
        # reversal world (reuse the same X-determined weights on reversal returns)
        rev = []
        for d in rev_draws:
            Rr = S.reversal_world(R, theta1=-0.8, theta2=-0.4, seed=d)
            rev_strat = D.apply_weights(W, Rr) * Rr
            rev.append(E.sharpe(pd.Series(rev_strat[m])))
        # anchor: kernel vs RFF at selected T
        anchor = None
        if T in anchor_T:
            Phi = F.rff(X, 12000, gamma=GAMMA, seed=0)
            rff_fc = F.rolling_forecasts(Phi, R, T, [1e-3])[0]
            mk = ~np.isnan(rff_fc) & ~np.isnan(fc)
            anchor = float(np.corrcoef(rff_fc[mk], fc[mk])[0, 1])
        rows[T] = {
            "kernel_SR": E.sharpe(pd.Series(strat[m])),
            "recency_corr": recency_corr,
            "scale_vs_predvol": scale_vol,
            "reversal_SR": float(np.mean(rev)),
            "reversal_share_neg": float(np.mean(np.array(rev) < 0)),
            "anchor_kernel_vs_rff_corr": anchor,
        }
        print(f"  T={T:3d}: SR={rows[T]['kernel_SR']:.3f} recency={recency_corr:+.2f} "
              f"voltime={scale_vol:+.2f} revSR={rows[T]['reversal_SR']:.3f}"
              f"{'' if anchor is None else f' anchor={anchor:.3f}'} "
              f"({time.time()-t0:.0f}s)", flush=True)

    out = {"T_grid": T_grid, "by_T": rows}
    (RESULTS / "phase_diagram.json").write_text(json.dumps(out, indent=2))
    print("\n=== Phase diagram (mechanism vs T) ===")
    print(pd.DataFrame(rows).T.round(3).to_string())
    print(f"\nsaved {RESULTS / 'phase_diagram.json'}")


if __name__ == "__main__":
    main()
