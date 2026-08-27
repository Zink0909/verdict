#!/usr/bin/env python3
"""Figures for the volatility-harvesting verdict (run after run.py)."""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np               # noqa: E402

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": "#e9e9e9", "figure.dpi": 150})
B, R_, G, GY = "#2c6fbb", "#c0392b", "#2e7d32", "#888"

R = json.loads((HERE / "results.json").read_text())


def fig_friction():
    fc = R["friction_cliff"]
    fig, ax = plt.subplots(figsize=(7.6, 4.4))
    ax.plot(fc["levels"], fc["expectancy"], "o-", color=B, lw=2)
    ax.axhline(0, color="black", lw=1)
    be = fc["breakeven_points_per_leg"]
    ax.axvline(be, color=R_, ls="--", lw=1.4)
    ax.annotate(f"edge dies at\n{be:.3f} pts/leg", (be, 20), color=R_, fontsize=9.5,
                ha="left", va="bottom", fontweight="bold",
                textcoords="offset points", xytext=(6, 0))
    ax.axvline(fc["assumed_in_the_grid"], color=GY, ls=":", lw=1.4)
    ax.annotate("assumed\nin the model", (fc["assumed_in_the_grid"], -110), color=GY,
                fontsize=9, ha="center", va="top")
    ax.set_xlabel("assumed friction (index points per leg)")
    ax.set_ylabel("expectancy per trade ($)")
    ax.set_title("The whole edge lives inside the first nickel", fontweight="bold")
    fig.tight_layout(); fig.savefig(RES / "fig1_friction_cliff.png"); plt.close(fig)


def fig_granularity():
    rows = R["feasibility"]["by_width"]
    w = [r["width_pct"] for r in rows]
    x = np.arange(len(w))
    fig, ax = plt.subplots(figsize=(7.8, 4.4))
    ax.bar(x, [r["mean_expectancy"] for r in rows], 0.5, color=B,
           label="mean expectancy per trade (left)")
    ax.axhline(0, color="black", lw=1)
    ax.set_ylabel("expectancy per trade ($)", color=B)
    ax.tick_params(axis="y", labelcolor=B)
    ax.set_xticks(x); ax.set_xticklabels([f"{v:.1f}%" for v in w])
    ax.set_xlabel("spread width")
    ax2 = ax.twinx()
    ax2.plot(x, [r["mean_post2021_trades"] for r in rows], "o--", color=R_, lw=2,
             label="trades available after 2021 (right)")
    ax2.set_ylabel("mean trades after 2021", color=R_)
    ax2.tick_params(axis="y", labelcolor=R_); ax2.grid(False)
    ax2.set_ylim(bottom=0)
    ax.set_title("The widths that would pay are the widths a small account\n"
                 "can no longer trade", fontweight="bold")
    h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, frameon=False, fontsize=9, loc="lower center")
    fig.tight_layout(); fig.savefig(RES / "fig2_granularity.png"); plt.close(fig)


def fig_model_vs_reality():
    rows = [r for r in R["model_vs_reality"]["rows"] if r["real_chain_cagr_pct"] is not None]
    labels = ["45Δ / 1.5%\n(model's pick)", "25Δ / 2.0%\n(earlier candidate)"]
    x = np.arange(len(rows))
    fig, ax = plt.subplots(figsize=(7.6, 4.4))
    ax.bar(x - 0.19, [r["modelled"]["cagr_pct"] for r in rows], 0.38, color=B,
           label="modelled prices")
    ax.bar(x + 0.19, [r["real_chain_cagr_pct"] for r in rows], 0.38, color=R_,
           label="real option chains")
    ax.axhline(0, color="black", lw=1)
    for i, r in enumerate(rows):
        ax.annotate(f"{r['modelled']['cagr_pct']:+.1f}%", (i - 0.19, r["modelled"]["cagr_pct"]),
                    ha="center", va="bottom", fontsize=9, fontweight="bold")
        ax.annotate(f"{r['real_chain_cagr_pct']:+.1f}%", (i + 0.19, r["real_chain_cagr_pct"]),
                    ha="center", va="top", fontsize=9, fontweight="bold")
    ax.set_xticks(x); ax.set_xticklabels(labels[:len(rows)], fontsize=9.5)
    ax.set_ylabel("CAGR (%)")
    ax.set_title("The configuration the model ranked best\nwas the worst one traded",
                 fontweight="bold")
    ax.legend(frameon=False, fontsize=9, loc="lower left")
    fig.tight_layout(); fig.savefig(RES / "fig3_model_vs_reality.png"); plt.close(fig)


if __name__ == "__main__":
    RES.mkdir(exist_ok=True)
    which = sys.argv[1:] or ["friction", "granularity", "reality"]
    if "friction" in which:
        fig_friction(); print("fig1")
    if "granularity" in which:
        fig_granularity(); print("fig2")
    if "reality" in which:
        fig_model_vs_reality(); print("fig3")
