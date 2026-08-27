#!/usr/bin/env python3
"""Figures for the drift verdict (run after run.py)."""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np               # noqa: E402
import pandas as pd              # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
RES = HERE / "results"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 11,
                     "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.color": "#e9e9e9", "figure.dpi": 150})
B, R_, G, GY = "#2c6fbb", "#c0392b", "#2e7d32", "#888"

R = json.loads((HERE / "results.json").read_text())


def fig_monitor():
    roll = pd.read_csv(HERE / "results_rolling.csv", parse_dates=["date"]).set_index("date")
    m = R["monitor"]
    fig, ax = plt.subplots(figsize=(9.6, 4.4))
    ax.plot(roll.index, roll["auc"], color=B, lw=1.7, label="rolling AUC (150-day window)")
    ax.axhline(0.5, color=GY, ls=":", lw=1.2)
    ax.annotate("chance", (roll.index[5], 0.503), fontsize=8.5, color=GY)
    ax.axhline(m["baseline_auc"], color="#444", ls="--", lw=0.9,
               label=f"baseline {m['baseline_auc']:.3f}")
    for a in R["alarms"]:
        ax.axvline(pd.Timestamp(a["date"]), color=R_, ls="--", lw=1.3)
    if R["alarms"]:
        ax.annotate(f"drift alarm\n{R['alarms'][0]['date']}",
                    (pd.Timestamp(R["alarms"][0]["date"]), 0.655), color=R_,
                    fontsize=9, ha="left", fontweight="bold")
    wd = pd.Timestamp(m["worst_auc_date"])
    ax.plot([wd], [m["worst_auc"]], "v", color=R_, ms=9)
    ax.annotate(f"trough {m['worst_auc']:.3f}  ({str(wd)[:10]})", (wd, m["worst_auc"]),
                textcoords="offset points", xytext=(12, 4),
                fontsize=9, ha="left", va="bottom", color=R_)
    ax.set_ylabel("discrimination (AUC)")
    ax.set_title(f"The alarm fires {R['alarm_lead_days']/365:.1f} years before the trough",
                 fontweight="bold")
    ax.legend(frameon=False, fontsize=9, loc="lower left")
    fig.tight_layout(); fig.savefig(RES / "fig1_monitor.png"); plt.close(fig)


def fig_phases():
    fig, ax = plt.subplots(figsize=(8.4, 4.4))
    labels = [p["phase"] for p in R["phases_spy"]]
    x = np.arange(len(labels))
    spy = [p["gap_pp"] for p in R["phases_spy"]]
    qqq = [p["gap_pp"] for p in R["phases_qqq"]]
    ax.bar(x - 0.19, spy, 0.38, color=B, label="primary instrument")
    ax.bar(x + 0.19, qqq, 0.38, color="#8aa9cc", label="second instrument (replication)")
    ax.axhline(0, color="black", lw=1)
    for i, (a, b) in enumerate(zip(spy, qqq)):
        for off, v in ((-0.19, a), (0.19, b)):
            ax.annotate(f"{v:+.0f}", (i + off, v), ha="center",
                        va="bottom" if v >= 0 else "top", fontsize=9, fontweight="bold")
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=9.5)
    ax.set_ylabel("win-rate gap, short minus long gamma (pp)")
    ax.set_title("Erosion, inversion, recovery — and it is not one instrument's fluke",
                 fontweight="bold")
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout(); fig.savefig(RES / "fig2_phases.png"); plt.close(fig)


def fig_attribution():
    sys.path.insert(0, str(HERE))
    from run import zdte_daily
    roll = pd.read_csv(HERE / "results_rolling.csv", parse_dates=["date"]).set_index("date")
    auc = roll["auc"].dropna()
    z = zdte_daily(pd.DatetimeIndex(auc.index))
    att = R["attribution"]
    fig, ax = plt.subplots(figsize=(9.8, 4.6))
    ax.plot(auc.index, auc, color=B, lw=1.7, label="rolling AUC (left)")
    ax.axhline(0.5, color=GY, ls=":", lw=1.2)
    ax.set_ylabel("discrimination (AUC)", color=B)
    ax.tick_params(axis="y", labelcolor=B)
    ax.set_ylim(0.40, 0.72)
    ax2 = ax.twinx()
    ax2.plot(auc.index, z, color=R_, lw=1.6, ls="--", label="suspected driver (right)")
    ax2.set_ylabel("0DTE share of index option volume (%)", color=R_)
    ax2.tick_params(axis="y", labelcolor=R_)
    ax2.set_ylim(0, 70); ax2.grid(False)
    if R["alarms"]:
        ax.axvline(pd.Timestamp(R["alarms"][0]["date"]), color="#444", lw=0.9)
        ax.annotate(f"erosion starts here,\ndriver only at {att['driver_at_alarm_pct']:.0f}%",
                    (pd.Timestamp(R["alarms"][0]["date"]), 0.695), fontsize=8.5, color="#444")
    ax.axvline(pd.Timestamp("2022-01-01"), color=GY, lw=0.9, ls="-.")
    ax.set_title(f"Full sample {att['corr_full']:+.2f} — but after 2022 it flips to "
                 f"{att['corr_after']:+.2f}", fontweight="bold")
    h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, frameon=False, fontsize=9, loc="lower left")
    fig.tight_layout(); fig.savefig(RES / "fig3_attribution.png"); plt.close(fig)


if __name__ == "__main__":
    RES.mkdir(exist_ok=True)
    which = sys.argv[1:] or ["monitor", "phases", "attribution"]
    if "monitor" in which:
        fig_monitor(); print("fig1")
    if "phases" in which:
        fig_phases(); print("fig2")
    if "attribution" in which:
        fig_attribution(); print("fig3")
