#!/usr/bin/env python3
"""Figures for the complexity verdict (run after run_kmz / run_nagel / phase_diagram)."""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": "#e9e9e9", "figure.dpi": 150})
B, R_, G, GY = "#2c6fbb", "#c0392b", "#2e7d32", "#888"


def fig_voc_curve():
    df = pd.read_parquet(RES / "kmz_sweep.parquet")
    piv = df.groupby(["z", "P"])["sr"].mean().unstack()
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    for z in piv.index:
        ax.plot(piv.columns, piv.loc[z], "o-", label=f"z={z:g}")
    ax.set_xscale("log"); ax.set_xlabel("model complexity  P (# random features)")
    ax.set_ylabel("out-of-sample timing Sharpe (annualized)")
    ax.set_title("The 'virtue of complexity' curve, reproduced", fontweight="bold")
    ax.legend(frameon=False, fontsize=9, title="ridge shrinkage")
    fig.tight_layout(); fig.savefig(RES / "fig1_voc_curve.png"); plt.close(fig)


def fig_diagnostics():
    d = json.loads((RES / "nagel_diagnostics.json").read_text())
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9.6, 4.0))
    # left: kernel weight profile by lag (momentum signature)
    w = d["d1"]["wlag_profile"]
    a1.bar(range(1, len(w) + 1), w, color=B)
    a1.set_xlabel("lag (months back)"); a1.set_ylabel("avg kernel weight")
    a1.set_title(f"Weights decline with lag = momentum\n(recency corr "
                 f"{d['d1']['weight_recency_corr']:+.2f})", fontweight="bold")
    # right: the three headline SRs
    labels = ["real", "reversal\nworld", "content\ndestroyed"]
    vals = [d["d2"]["real_SR"], d["d2"]["reversal_SR_mean"], d["d3"]["bootstrap_SR_mean"]]
    cols = [G, R_, GY]
    a2.bar(labels, vals, color=cols); a2.axhline(0, color=GY, lw=1)
    for i, v in enumerate(vals):
        a2.annotate(f"{v:+.2f}", (i, v), ha="center",
                    va="bottom" if v >= 0 else "top", fontsize=10, fontweight="bold")
    a2.set_ylabel("timing Sharpe (annualized)")
    a2.set_title("Loses under reversal, survives\ncontent-destruction = mechanical",
                 fontweight="bold")
    fig.tight_layout(); fig.savefig(RES / "fig2_diagnostics.png"); plt.close(fig)


def fig_phase():
    d = json.loads((RES / "phase_diagram.json").read_text())
    T = d["T_grid"]
    by = d["by_T"]
    fig, ax = plt.subplots(figsize=(6.8, 4.2))
    ax.plot(T, [by[str(t)]["recency_corr"] for t in T], "o-", color=R_,
            label="momentum signature (weight recency corr)")
    ax.plot(T, [-by[str(t)]["scale_vs_predvol"] for t in T], "s-", color="#8aa9cc",
            label="volatility-timing signature (−corr)")
    ax.plot(T, [by[str(t)]["kernel_SR"] for t in T], "D-", color=B,
            label="strategy Sharpe")
    ax.plot(T, [by[str(t)]["reversal_SR"] for t in T], "^-", color=G,
            label="reversal-world Sharpe")
    ax.axhline(0, color=GY, lw=1)
    ax.set_xlabel("training window length  T (months)")
    ax.set_title("The momentum mechanism fades with T,\nbut the strategy never learns",
                 fontweight="bold")
    ax.legend(frameon=False, fontsize=8.5)
    fig.tight_layout(); fig.savefig(RES / "fig3_phase.png"); plt.close(fig)


if __name__ == "__main__":
    which = sys.argv[1:] or ["voc", "diag", "phase"]
    if "voc" in which:
        fig_voc_curve(); print("fig1")
    if "diag" in which:
        fig_diagnostics(); print("fig2")
    if "phase" in which:
        fig_phase(); print("fig3")
