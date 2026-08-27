#!/usr/bin/env python3
"""Retrofit case: a live signal that decayed — detecting it, dating it, explaining it.

The claim is not that a strategy works; it is that a *feature* discriminates.
A dealer-gamma reading was used to say when an intraday trading rule (from a
separate intraday-momentum study) would win or lose. It did discriminate — and
then it stopped, and then it partly came back.

Three questions, each a framework component:

  1. **Did it decay, and when?** `diagnose.drift` runs a rolling AUC and a
     one-sided CUSUM over the prediction stream, turning "it looks like it's
     fading" into a dated alarm.
  2. **How big was the swing?** Discrimination and win-rate gap by phase, with
     block-bootstrap bands, on two instruments — because a single-ticker shape
     is an anecdote.
  3. **What caused it?** The obvious suspect (the 0DTE options boom) correlates
     strongly over the full sample. `diagnose.attribution_holds_up` splits the
     sample and asks whether it still does.

Anchors from the original study, which this must reproduce: baseline AUC ~0.60,
trough ~0.44 in 2022-23, first alarm mid-2020, phase gaps +12pp / -15pp / +11pp,
full-sample attribution correlation -0.72 flipping to +0.76 after 2022.

  micromamba run -n verdict python cases/drift/run.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))

from verdict import diagnose as D    # noqa: E402
from verdict import evaluate as E    # noqa: E402

DATA = HERE / "data"
WINDOW = 150
PHASES = [("pre-2022 (2014-21)", None, "2022-01-01"),
          ("0DTE surge (2022-23)", "2022-01-01", "2024-01-01"),
          ("recent (2024-26)", "2024-01-01", None)]


def stream(path: Path) -> pd.DataFrame:
    """The prediction stream under test: traded days carrying a gamma reading.

    The 'model' is deliberately a one-line rule — short gamma (negative reading)
    predicts a win — because the case is about evaluating a deployed predictor,
    not about building a good one. A complicated model would only make the
    decay harder to attribute.
    """
    d = pd.read_csv(path, parse_dates=["date"])
    s = d[(d["traded"] == 1) & d["gex_prev"].notna()].copy()
    s["p"] = (-np.sign(s["gex_prev"]) + 1) / 2
    return s.sort_values("date").reset_index(drop=True)


def anchor_check(rolling: pd.DataFrame) -> dict:
    """Independent re-derivation against the original study's saved series."""
    ref = pd.read_csv(DATA / "rolling_metrics.csv", parse_dates=["date"]).set_index("date")
    j = ref.join(rolling["auc"].rename("ours"), how="inner")
    return {"reference_windows": int(len(ref)), "matched_windows": int(len(j)),
            "corr": float(j["rolling_auc"].corr(j["ours"])),
            "max_abs_diff": float((j["rolling_auc"] - j["ours"]).abs().max())}


def phase_table(s: pd.DataFrame, n_boot: int = 400) -> list[dict]:
    """Discrimination and win-rate gap per phase, with bootstrap bands."""
    out = []
    for name, lo, hi in PHASES:
        sub = s.copy()
        if lo:
            sub = sub[sub["date"] >= pd.Timestamp(lo)]
        if hi:
            sub = sub[sub["date"] < pd.Timestamp(hi)]
        short_g = sub[sub["p"] == 1]["y"]
        long_g = sub[sub["p"] == 0]["y"]
        ci = E.block_bootstrap_auc_ci(sub["y"], sub["p"], n_boot=n_boot, block=10)
        out.append({"phase": name, "n": int(len(sub)),
                    "win_short_gamma": float(short_g.mean()) if len(short_g) else np.nan,
                    "win_long_gamma": float(long_g.mean()) if len(long_g) else np.nan,
                    "gap_pp": float((short_g.mean() - long_g.mean()) * 100)
                    if len(short_g) and len(long_g) else np.nan,
                    "auc": E.auc(sub["y"], sub["p"]),
                    "auc_lo": ci[0], "auc_hi": ci[1]})
    return out


def zdte_daily(index: pd.DatetimeIndex) -> pd.Series:
    """Annual 0DTE share placed mid-year and interpolated onto a daily index.

    Annual granularity with interpolated intermediate years is what the public
    source supports; it is labelled as such rather than presented as a daily
    measurement.
    """
    z = pd.read_csv(DATA / "zdte_share.csv")
    anchor = pd.Series(z["zdte_share_pct"].to_numpy(float),
                       index=pd.to_datetime(z["year"].astype(str) + "-07-01"))
    full = anchor.reindex(anchor.index.union(index)).interpolate("time").ffill().bfill()
    return full.reindex(index)


def main() -> dict:
    s = stream(DATA / "dataset.csv")
    print(f"stream: {len(s)} traded days with a gamma reading, "
          f"{s['date'].min().date()} -> {s['date'].max().date()}\n")

    print("=== drift monitor (rolling AUC + CUSUM change-point) ===")
    rep = D.drift(s, "date", "p", "y", window=WINDOW)
    sm = rep["summary"]
    print(f"  windows {sm['n_windows']}  overall AUC {sm['overall_auc']:.3f}  "
          f"baseline {sm['baseline_auc']:.3f}")
    print(f"  worst AUC {sm['worst_auc']:.3f} on {str(sm['worst_auc_date'])[:10]}")
    for a in rep["alarms"]:
        print(f"  ALARM {str(a['date'])[:10]}  AUC {a['auc']:.3f} vs baseline {a['baseline']:.3f}")
    lead_days = ((pd.Timestamp(sm["worst_auc_date"]) - pd.Timestamp(sm["first_alarm"])).days
                 if sm["first_alarm"] is not None else None)
    print(f"  the alarm leads the trough by {lead_days} days "
          f"({lead_days/365:.1f} years)" if lead_days else "")

    print("\n=== audit: independent re-derivation vs the original study's series ===")
    anc = anchor_check(rep["rolling"])
    print(f"  matched {anc['matched_windows']}/{anc['reference_windows']} windows | "
          f"corr {anc['corr']:.6f} | max abs diff {anc['max_abs_diff']:.2e}")

    print("\n=== phases: erosion -> inversion -> recovery ===")
    spy = phase_table(s)
    for r in spy:
        print(f"  {r['phase']:<22} n={r['n']:4d}  short {r['win_short_gamma']:.2f} vs "
              f"long {r['win_long_gamma']:.2f}  gap {r['gap_pp']:+.0f}pp  "
              f"AUC {r['auc']:.3f} [{r['auc_lo']:.3f}, {r['auc_hi']:.3f}]")

    print("\n=== independent replication on a second instrument ===")
    q = stream(DATA / "dataset_qqq.csv")
    qqq = phase_table(q)
    for r in qqq:
        print(f"  {r['phase']:<22} n={r['n']:4d}  gap {r['gap_pp']:+.0f}pp  AUC {r['auc']:.3f}")
    same_shape = ([np.sign(r["gap_pp"]) for r in qqq] == [np.sign(r["gap_pp"]) for r in spy])
    print(f"  same sign pattern across phases: {same_shape}")

    print("\n=== attribution: does the obvious cause survive a split? ===")
    auc_series = rep["rolling"]["auc"].dropna()
    z = zdte_daily(pd.DatetimeIndex(auc_series.index))
    att = D.attribution_holds_up(auc_series, z, split_at="2022-01-01")
    print(f"  Spearman full sample {att['corr_full']:+.2f}  "
          f"(before {att['corr_before']:+.2f}, after {att['corr_after']:+.2f})")
    print(f"  -> {att['verdict']}")
    onset_z = float(z.loc[:pd.Timestamp(sm["first_alarm"])].iloc[-1])
    end_z = float(z.iloc[-1])
    print(f"  at the alarm the driver stood at {onset_z:.0f}%, and it reached {end_z:.0f}% "
          "while discrimination recovered")

    out = {"stream": {"n": int(len(s)), "start": str(s["date"].min().date()),
                      "end": str(s["date"].max().date())},
           "monitor": {k: (str(v) if isinstance(v, pd.Timestamp) else v)
                       for k, v in sm.items()},
           "alarms": [{"date": str(a["date"])[:10], "auc": a["auc"]} for a in rep["alarms"]],
           "alarm_lead_days": lead_days,
           "anchor_check": anc, "phases_spy": spy, "phases_qqq": qqq,
           "replication_same_shape": bool(same_shape),
           "attribution": {**att, "driver_at_alarm_pct": onset_z, "driver_latest_pct": end_z}}
    (HERE / "results.json").write_text(json.dumps(out, indent=2, default=float))
    rep["rolling"].to_csv(HERE / "results_rolling.csv")
    print(f"\nsaved {HERE/'results.json'} and results_rolling.csv")
    return out


if __name__ == "__main__":
    main()
