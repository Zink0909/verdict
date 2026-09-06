#!/usr/bin/env python3
"""Figures for the time-series momentum verdict (run after run.py).

Drawn from `results_series.csv` and `results.json`, which `run.py` wrote, so the
pictures and the quoted numbers cannot disagree.
"""
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
B, R_, G, GY, O = "#2c6fbb", "#c0392b", "#2e7d32", "#888", "#e08214"

D = json.loads((HERE / "results.json").read_text())
S = pd.read_csv(HERE / "results_series.csv", index_col=0, parse_dates=True)
DRAWS = np.loadtxt(RES / "sign_draws.csv")


def fig1_claim_vs_benchmarks():
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10.4, 4.2))

    for col, c, lab in (("strategy", B, "time-series momentum"),
                        ("passive_long", GY, "passive long, same sizing"),
                        ("xs_momentum", O, "cross-sectional momentum")):
        a1.plot(S.index, (1 + S[col]).cumprod(), color=c, lw=1.9 if col == "strategy" else 1.3,
                label=lab)
    a1.axhline(1.0, color="#bbb", lw=0.8)
    a1.set_title("Growth of 1, gross of costs")
    a1.legend(fontsize=8.5, frameon=False, loc="upper left")

    a2.hist(DRAWS, bins=28, color="#d6d6d6", edgecolor="white")
    a2.axvline(D["K4_sign_randomisation"]["strategy_sharpe"], color=R_, lw=2.2)
    a2.axvline(float(np.median(DRAWS)), color=GY, lw=1.0, ls="--")
    pct = D["K4_sign_randomisation"]["strategy_percentile_vs_random"]
    a2.set_title(f"K4: {len(DRAWS)} coin-flip sign draws, same position sizes")
    a2.set_xlabel("Sharpe")
    a2.annotate(f"the strategy\n{pct:.0%} of draws below it",
                xy=(D["K4_sign_randomisation"]["strategy_sharpe"], a2.get_ylim()[1] * 0.72),
                xytext=(8, 0), textcoords="offset points", color=R_, fontsize=9)
    fig.tight_layout()
    fig.savefig(RES / "fig1_claim_vs_benchmarks.png", bbox_inches="tight")
    plt.close(fig)


def fig2_where_the_return_comes_from():
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10.4, 4.2))

    a1.plot(S.index, (1 + S["tilt"]).cumprod(), color=B, lw=1.8,
            label="common direction (net long/short)")
    a1.plot(S.index, (1 + S["timing"]).cumprod(), color=R_, lw=1.8,
            label="which markets (cross-market selection)")
    a1.axhline(1.0, color="#bbb", lw=0.8)
    a1.set_title("Decomposing the rule's own return")
    a1.legend(fontsize=8.5, frameon=False, loc="upper left")

    pm = D["diagnostic_per_market_ann"]
    ks = list(pm)
    vals = [pm[k] * 100 for k in ks]
    a2.bar(ks, vals, color=[G if v > 0 else R_ for v in vals])
    a2.axhline(0, color="#555", lw=0.9)
    a2.set_title("Annualised contribution by market (pp)")
    fig.tight_layout()
    fig.savefig(RES / "fig2_where_the_return_comes_from.png", bbox_inches="tight")
    plt.close(fig)


def fig3_robustness():
    rob = D["robustness"]
    order = ["lookback_months", "vol_window_days", "drop_sector", "sample"]
    rows = [r for a in order for r in rob if r["axis"] == a]
    labels = [f"{r['axis'].replace('_', ' ')} = {r['value']}" for r in rows]
    vals = [r["sharpe"] for r in rows]
    base = D["strategy"]["sharpe"]

    fig, ax = plt.subplots(figsize=(7.6, 0.34 * len(rows) + 1.5))
    y = np.arange(len(rows))[::-1]
    ax.scatter(vals, y, s=42, color=[B if v > 0 else R_ for v in vals], zorder=3)
    ax.axvline(0, color="#555", lw=1.0)
    ax.axvline(base, color=GY, lw=1.0, ls="--")
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=8.6)
    ax.set_xlabel("Sharpe")
    ax.set_title("Every perturbation the protocol pre-registered\n"
                 f"(dashed = the registered configuration, {base:+.2f})", fontsize=10)
    fig.tight_layout()
    fig.savefig(RES / "fig3_robustness.png", bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    RES.mkdir(exist_ok=True)
    fig1_claim_vs_benchmarks()
    fig2_where_the_return_comes_from()
    fig3_robustness()
    print("wrote", *(p.name for p in sorted(RES.glob("fig*.png"))))
