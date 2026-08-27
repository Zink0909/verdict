#!/usr/bin/env python3
"""Figures for the buy-the-dip verdict (run after run.py)."""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np               # noqa: E402
import pandas as pd              # noqa: E402

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": "#e9e9e9", "figure.dpi": 150})
B, R_, G, GY = "#2c6fbb", "#c0392b", "#2e7d32", "#888"


def fig_stock_vs_call():
    d = json.loads((HERE / "results.json").read_text())["expression"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9.6, 4.0))
    x = np.arange(2)
    a1.bar(x - 0.18, [d["underlying_mean"], d["underlying_median"]], 0.36,
           label="the stock", color=B)
    a1.bar(x + 0.18, [d["deriv_mean"], d["deriv_median"]], 0.36,
           label="the long call", color=R_)
    a1.set_xticks(x); a1.set_xticklabels(["mean", "median"])
    a1.axhline(0, color=GY, lw=1); a1.set_ylabel("P&L per $10,000 trade")
    a1.set_title("Same dips, two instruments\n"
                 f"(the call gives up ${abs(d['expression_drag']):.0f}/trade)",
                 fontweight="bold")
    a1.legend(frameon=False, fontsize=9)
    a2.bar(["stock", "long call"], [d["underlying_win"], d["deriv_win"]], color=[B, R_])
    a2.axhline(0.5, color=GY, lw=1, ls="--")
    a2.set_ylabel("win rate"); a2.set_ylim(0, 0.7)
    a2.set_title("The dip view was fine;\nthe expression was not", fontweight="bold")
    fig.tight_layout(); fig.savefig(RES / "fig1_stock_vs_call.png"); plt.close(fig)


def fig_volatility_test():
    d = json.loads((HERE / "results.json").read_text())["observed_mechanism"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9.6, 4.0))
    order = ["recovered", "missed", "never"]
    for ax, key, title in ((a1, "iv_all", "All trades with usable IV"),
                           (a2, "iv_far_from_expiry", "Exited ≥30 days before expiry")):
        blk = d[key]["by_status"]
        means = [blk[s]["mean"] for s in order if s in blk]
        labs = [f"{s}\n(n={blk[s]['n']})" for s in order if s in blk]
        cols = [G if s == "recovered" else GY for s in order if s in blk]
        ax.bar(labs, means, color=cols)
        ax.axhline(0, color="black", lw=1)
        for i, s in enumerate([s for s in order if s in blk]):
            ax.annotate(f"{blk[s]['share_falling']:.0%} fell", (i, means[i]),
                        ha="center", va="bottom", fontsize=9)
        ax.set_ylabel("mean change in implied volatility")
        ax.set_title(f"{title}\n(n={d[key]['n']})", fontweight="bold")
        ax.set_ylim(-0.02, 0.15)      # shared scale: the right panel really is smaller
    fig.suptitle("The predicted volatility headwind does not appear: IV rose, not fell",
                 fontweight="bold", y=1.02)
    fig.tight_layout(); fig.savefig(RES / "fig2_volatility_test.png",
                                    bbox_inches="tight"); plt.close(fig)


def fig_robustness():
    rob = pd.read_csv(HERE / "results_robustness.csv")
    fig, ax = plt.subplots(figsize=(8.2, 4.4))
    x = np.arange(len(rob))
    ax.bar(x - 0.2, rob["mean_pnl"], 0.4, label="mean P&L", color=B)
    ax.bar(x + 0.2, rob["median_pnl"], 0.4, label="median P&L", color=R_)
    ax.axhline(0, color="black", lw=1)
    ax.set_xticks(x)
    ax.set_xticklabels([lab.replace("roic>=", "").replace("/consist>=", " / ")
                        for lab in rob["label"]], rotation=45, ha="right", fontsize=8.5)
    ax.set_xlabel("moat definition:  ROIC floor / consistency requirement")
    ax.set_ylabel("P&L per $10,000 trade")
    ax.set_title("The median is negative under every definition;\n"
                 "only the tightest screen lifts the mean above zero", fontweight="bold")
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout(); fig.savefig(RES / "fig3_robustness.png"); plt.close(fig)


if __name__ == "__main__":
    RES.mkdir(exist_ok=True)
    which = sys.argv[1:] or ["expr", "vol", "robust"]
    if "expr" in which:
        fig_stock_vs_call(); print("fig1")
    if "vol" in which:
        fig_volatility_test(); print("fig2")
    if "robust" in which:
        fig_robustness(); print("fig3")
