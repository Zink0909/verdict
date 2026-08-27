#!/usr/bin/env python3
"""Retrofit case: harvesting the volatility risk premium at retail scale.

This case is unusual in the library because the *premise is true*. The
volatility risk premium exists and is well measured: implied volatility exceeds
subsequent realized volatility by about 3.4 points on average, and does so about
82% of the time. The claim under audit is the next step, the one everyone takes
for granted — that a small account can therefore harvest it with defined-risk
short-volatility spreads.

The audit runs on the artefacts of a modelled search over 108 configurations,
plus the recorded results of the three configurations that were subsequently
run against real option chains. Four questions:

  1. Does re-executing the pre-registered selection rule pick the same winner?
  2. Do high win rates mean profit? (108 configurations say what they say.)
  3. Where does the edge die as friction rises — and is that inside or outside
     what a real venue charges?
  4. Did the modelled ranking survive contact with real chains?

  micromamba run -n verdict python cases/vol_harvest/run.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))

from verdict import costs as C     # noqa: E402
from verdict import robust as R    # noqa: E402

DATA = HERE / "data"

# Headers in the pinned grids were translated to English when the data was pinned;
# the mapping is recorded in data/README.md. No values were altered.

# The rule as written down before the grid was inspected, per the source project.
PREREG = {"min_trades_post_2021": 10, "require_positive_expectancy": True,
          "rank_by": "sharpe"}


def load() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    g1 = pd.read_csv(DATA / "grid_phase1.csv")
    g2 = pd.read_csv(DATA / "grid_phase2.csv")
    rc = json.loads((DATA / "realchain_results.json").read_text())
    return g1, g2, rc


def rerun_preregistered_rule(g2: pd.DataFrame) -> dict:
    """Re-execute the documented selection rule on the modelled grid."""
    ungated = g2[g2["gate"] == "none"].copy()
    eligible = ungated[(ungated["n_trades_post2021"] >= PREREG["min_trades_post_2021"])
                       & (ungated["expectancy_usd"] > 0)]
    ranked = eligible.sort_values("sharpe", ascending=False)
    top = ranked.iloc[0] if len(ranked) else None
    return {"n_configs_ungated": int(len(ungated)),
            "n_eligible": int(len(eligible)),
            "selected": None if top is None else
            {"delta": float(top["delta"]), "width_pct": float(top["width_pct"]),
             "sharpe": float(top["sharpe"]), "expectancy_usd": float(top["expectancy_usd"]),
             "cagr_pct": float(top["cagr_pct"]),
             "n_trades_post2021": int(top["n_trades_post2021"])},
            "ranking": ranked[["delta", "width_pct", "sharpe", "expectancy_usd",
                               "n_trades_post2021"]].to_dict(orient="records")}


def win_rate_vs_profit(g1: pd.DataFrame, g2: pd.DataFrame) -> dict:
    """Across every configuration, does a high win rate predict making money?"""
    allc = pd.concat([g1[["win_pct", "expectancy_usd"]],
                      g2[["win_pct", "expectancy_usd"]]], ignore_index=True).dropna()
    high = allc[allc["win_pct"] >= 85]
    return {"n_configs": int(len(allc)),
            "corr_pearson": float(allc["win_pct"].corr(allc["expectancy_usd"])),
            "corr_spearman": float(allc["win_pct"].corr(allc["expectancy_usd"],
                                                        method="spearman")),
            "n_win_rate_over_85": int(len(high)),
            "share_of_those_losing": float((high["expectancy_usd"] <= 0).mean()),
            "best_win_rate": float(allc["win_pct"].max()),
            "expectancy_at_best_win_rate": float(
                allc.loc[allc["win_pct"].idxmax(), "expectancy_usd"])}


def feasibility_law(g2: pd.DataFrame) -> dict:
    """Position granularity decides which configurations can trade at all."""
    by_width = g2.groupby("width_pct").agg(
        mean_post2021_trades=("n_trades_post2021", "mean"),
        mean_expectancy=("expectancy_usd", "mean"),
        n_configs=("expectancy_usd", "size")).reset_index()
    dead = by_width[by_width["mean_post2021_trades"] < 1]["width_pct"].tolist()
    return {"by_width": by_width.to_dict(orient="records"),
            "widths_dead_after_2021": dead}


def delta_gradient(g2: pd.DataFrame) -> dict:
    by_delta = g2.groupby("delta").agg(
        mean_expectancy=("expectancy_usd", "mean"),
        mean_sharpe=("sharpe", "mean"), n_configs=("sharpe", "size")).reset_index()
    return {"by_delta": by_delta.to_dict(orient="records")}


def friction_cliff(rc: dict) -> dict:
    """Where does the modelled edge cross zero as friction rises?"""
    fs = rc["friction_sensitivity"]
    be = C.breakeven_friction(fs["levels_points_per_leg"], fs["expectancy_usd"])
    return {"levels": fs["levels_points_per_leg"], "expectancy": fs["expectancy_usd"],
            "breakeven_points_per_leg": be,
            "assumed_in_the_grid": 0.05,
            "headroom_points": float(be - 0.05)}


def model_vs_reality(g2: pd.DataFrame, rc: dict) -> dict:
    """The modelled ranking against the three configurations actually traded."""
    ungated = g2[g2["gate"] == "none"]

    def modelled(delta, width):
        row = ungated[(ungated["delta"] == delta) & (ungated["width_pct"] == width)]
        return None if row.empty else {
            "expectancy_usd": float(row.iloc[0]["expectancy_usd"]),
            "cagr_pct": float(row.iloc[0]["cagr_pct"]),
            "sharpe": float(row.iloc[0]["sharpe"])}

    pairs = [(0.45, 1.5, "45-delta short leg / 1.5% wide / no stop / 35 DTE"),
             (0.25, 2.0, "25-delta short leg / 2.0% wide")]
    rows = []
    for delta, width, label in pairs:
        run = next((r for r in rc["runs"] if r["config"] == label), None)
        rows.append({"config": label, "modelled": modelled(delta, width),
                     "real_chain_cagr_pct": None if run is None else run.get("cagr_pct"),
                     "real_chain_net_pct": None if run is None else run.get("net_return_pct")})
    ranked_model = sorted([r for r in rows if r["modelled"]],
                          key=lambda r: -r["modelled"]["cagr_pct"])
    ranked_real = sorted([r for r in rows if r["real_chain_cagr_pct"] is not None],
                         key=lambda r: -r["real_chain_cagr_pct"])
    inverted = bool(ranked_model and ranked_real
                    and ranked_model[0]["config"] != ranked_real[0]["config"])
    return {"rows": rows, "rank_inverted": inverted,
            "modelled_best": ranked_model[0]["config"] if ranked_model else None,
            "real_chain_best": ranked_real[0]["config"] if ranked_real else None,
            "real_chain_worst": ranked_real[-1]["config"] if ranked_real else None}


def main() -> dict:
    g1, g2, rc = load()
    print(f"modelled grids: phase-1 {len(g1)} configs, phase-2 {len(g2)} configs "
          f"({len(g1)+len(g2)} total)\n")

    print("=== premise ===")
    pc = rc["premise_check"]
    print(f"  the volatility risk premium is real: {pc['vrp_mean_vol_points']} vol points "
          f"on average, positive {pc['vrp_share_positive']:.1%} of the time")

    print("\n=== re-executing the pre-registered selection rule ===")
    sel = rerun_preregistered_rule(g2)
    print(f"  ungated configs {sel['n_configs_ungated']} -> eligible {sel['n_eligible']} "
          f"(>= {PREREG['min_trades_post_2021']} trades after 2021 AND positive expectancy)")
    if sel["selected"]:
        s = sel["selected"]
        print(f"  selected: {s['delta']:.2f}-delta / {s['width_pct']}% wide — "
              f"Sharpe {s['sharpe']:.2f}, ${s['expectancy_usd']:.1f}/trade, "
              f"CAGR {s['cagr_pct']:+.1f}%, {s['n_trades_post2021']} trades after 2021")
    for r in sel["ranking"]:
        print(f"    {r['delta']:.2f} / {r['width_pct']}%  Sharpe {r['sharpe']:+.2f}  "
              f"${r['expectancy_usd']:+.1f}/trade  post-2021 n={r['n_trades_post2021']}")

    print("\n=== does a high win rate mean profit? ===")
    w = win_rate_vs_profit(g1, g2)
    print(f"  across {w['n_configs']} configurations, corr(win rate, expectancy) = "
          f"{w['corr_pearson']:+.2f} (Spearman {w['corr_spearman']:+.2f})")
    print(f"  of the {w['n_win_rate_over_85']} configurations winning >=85% of trades, "
          f"{w['share_of_those_losing']:.0%} lose money")
    print(f"  the highest win rate in the grid is {w['best_win_rate']:.1f}% — it earns "
          f"${w['expectancy_at_best_win_rate']:+.1f}/trade")

    print("\n=== granularity: which configurations can trade at all ===")
    f = feasibility_law(g2)
    for r in f["by_width"]:
        print(f"  width {r['width_pct']:.1f}%: mean {r['mean_post2021_trades']:.0f} trades "
              f"after 2021, mean expectancy ${r['mean_expectancy']:+.1f}")
    print(f"  widths effectively dead after 2021: {f['widths_dead_after_2021'] or 'none'}")

    print("\n=== delta gradient ===")
    dg = delta_gradient(g2)
    for r in dg["by_delta"]:
        print(f"  {r['delta']:.2f}-delta: mean ${r['mean_expectancy']:+.1f}/trade, "
              f"mean Sharpe {r['mean_sharpe']:+.2f}")

    print("\n=== the friction cliff ===")
    fc = friction_cliff(rc)
    for lv, ex in zip(fc["levels"], fc["expectancy"]):
        print(f"  {lv:.2f} pts/leg -> ${ex:+.1f}/trade")
    print(f"  breakeven friction = {fc['breakeven_points_per_leg']:.3f} points per leg; "
          f"the grid assumed {fc['assumed_in_the_grid']:.2f}, leaving "
          f"{fc['headroom_points']:.3f} of headroom")

    print("\n=== modelled ranking vs real chains ===")
    mv = model_vs_reality(g2, rc)
    for r in mv["rows"]:
        m = r["modelled"]
        print(f"  {r['config']}")
        print(f"      modelled: ${m['expectancy_usd']:+.1f}/trade, CAGR {m['cagr_pct']:+.1f}%, "
              f"Sharpe {m['sharpe']:+.2f}")
        print(f"      real chains: net {r['real_chain_net_pct']:+.1f}%, "
              f"CAGR {r['real_chain_cagr_pct']:+.2f}%")
    print(f"  ranking inverted: {mv['rank_inverted']} — the model's best "
          f"({mv['modelled_best'][:24]}...) was the worst on real chains")

    out = {"premise": pc, "selection": sel, "win_rate_vs_profit": w,
           "feasibility": f, "delta_gradient": dg, "friction_cliff": fc,
           "model_vs_reality": mv,
           "grids": {"phase1_configs": int(len(g1)), "phase2_configs": int(len(g2))}}
    (HERE / "results.json").write_text(json.dumps(out, indent=2, default=float))
    print(f"\nsaved {HERE/'results.json'}")
    return out


if __name__ == "__main__":
    main()
