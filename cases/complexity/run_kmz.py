#!/usr/bin/env python3
"""KMZ replication sweep (M2): the 'virtue of complexity' curve on real data.

Setup pinned in M0_PINNED.md: gamma=2, T=12 rolling window, RFF features of the
15 standardized Goyal-Welch predictors, ridge with no intercept and penalty
z*T, timing strategy = forecast x next-month standardized excess return.

For each seed we draw one max-P feature matrix and use nested prefix columns
for smaller P (interleaved sin/cos pairs stay matched), so the P-sweep is
comparable within a seed.

Optional cross-check: an external nkonts metrics.parquet grid at gamma=2, T=12.
The 100 MB grid is not shipped because it is not needed to reproduce our sweep
or the canonical Verdict demo.

Usage:
  micromamba run -n verdict python run_kmz.py --quick     # smoke: 2 seeds, small grid
  micromamba run -n verdict python run_kmz.py             # full: 10 seeds
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
from verdict import features as F   # noqa: E402
from verdict import evaluate as E   # noqa: E402

DATA = HERE / "data"
RESULTS = HERE / "results"

GAMMA = 2.0
T = 12
P_GRID_FULL = [2, 12, 120, 600, 1200, 6000, 12000]
Z_GRID = [0.0, 1e-3, 1e-1, 1e1, 1e3]     # 0 = ridgeless (min-norm)


def run(seeds, p_grid, z_grid):
    proc = pd.read_parquet(DATA / "processed.parquet")
    X = proc.drop(columns=["R"]).to_numpy(dtype=np.float64)
    R = proc["R"].to_numpy(dtype=np.float64)
    n = len(R)
    rows = []
    p_max = max(p_grid)
    for seed in seeds:
        t0 = time.time()
        Phi = F.rff(X, p_max, gamma=GAMMA, seed=seed)
        for P in p_grid:
            S = Phi[:, :P]
            fc = F.rolling_forecasts(S, R, T, z_grid)          # (n_z, n)
            for iz, z in enumerate(z_grid):
                f = fc[iz]
                mask = ~np.isnan(f)
                strat = f[mask] * R[mask]
                mkt = R[mask]
                # market regression (alpha/beta of the timing strategy)
                b = np.polyfit(mkt, strat, 1)
                rows.append(dict(
                    seed=seed, P=P, z=z, c=P / T,
                    sr=E.sharpe(pd.Series(strat)),
                    mean_ann=strat.mean() * 12, vol_ann=strat.std(ddof=1) * np.sqrt(12),
                    beta=float(b[0]), alpha_ann=float(b[1]) * 12,
                    r2_oos=float(1 - ((mkt - f[mask]) ** 2).sum()
                                 / ((mkt - mkt.mean()) ** 2).sum()),
                    n_oos=int(mask.sum()),
                ))
        print(f"  seed {seed}: {time.time()-t0:.0f}s", flush=True)
    return pd.DataFrame(rows)


def anchor_vs_nkonts(df):
    """Compare our sweep with an optional external nkonts grid at gamma=2, T=12."""
    anchor = DATA / "nkonts_metrics_anchor.parquet"
    if not anchor.is_file():
        print("\noptional nkonts metrics cross-check not installed; skipping")
        return
    nk = pd.read_parquet(anchor)
    nk = nk[(nk["gamma"] == 2) & (nk["T"] == 12)]
    if len(nk) == 0:
        print("no nkonts rows at gamma=2, T=12"); return
    nz = sorted(nk["z"].unique())
    print(f"\n=== anchor vs nkonts (gamma=2, T=12; their z values: {nz}) ===")
    for z in [zz for zz in nz if zz in df["z"].unique()]:
        ours = df[df["z"] == z].groupby("P")["sr"].mean()
        theirs = nk[nk["z"] == z].groupby("P")["SR"].mean()
        common = ours.index.intersection(theirs.index)
        if len(common) == 0:
            continue
        tab = pd.DataFrame({"ours_SR": ours[common], "nkonts_SR": theirs[common]})
        print(f"-- z = {z}")
        print(tab.round(3).to_string())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--seeds", type=int, default=10)
    a = ap.parse_args()
    RESULTS.mkdir(exist_ok=True)
    if a.quick:
        seeds, p_grid = range(2), [2, 120, 1200, 12000]
    else:
        seeds, p_grid = range(a.seeds), P_GRID_FULL
    df = run(seeds, p_grid, Z_GRID)
    out = RESULTS / ("kmz_sweep_quick.parquet" if a.quick else "kmz_sweep.parquet")
    df.to_parquet(out)
    print(f"\nsaved {out} ({len(df)} rows)")

    print("\n=== VoC curve: mean annualized SR vs P (across seeds) ===")
    piv = df.groupby(["z", "P"])["sr"].mean().unstack()
    print(piv.round(3).to_string())
    print("\n=== OOS R^2 vs P ===")
    print(df.groupby(["z", "P"])["r2_oos"].mean().unstack().round(3).to_string())
    anchor_vs_nkonts(df)


if __name__ == "__main__":
    main()
