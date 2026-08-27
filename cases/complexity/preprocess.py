#!/usr/bin/env python3
"""Build the standardized KMZ dataset from the official Goyal file (pinned spec).

Spec: M0_PINNED.md. Output: data/processed.parquet with 15 predictors + target R,
aligned so that row t holds predictors known at end of month t and R = the
NEXT month's standardized excess return (the convention of both replication
repos: forecast at row t is realized against R at row t).

Cross-checks (run as __main__):
  - raw predictor construction vs zivmi's formatted_goyal_data.csv (corr ~ 1)
  - standardized output vs zivmi's processed_data.csv (corr ~ 1; b/m may be
    slightly lower — Goyal updated its methodology between vintages)

Honest-audit note (return standardization): mirroring the replication repos,
sigma_R at row t is the trailing 12-month uncentered vol of the *aligned* R
column, whose row t already holds month t+1's return — i.e. the scaling window
includes the value being scaled. We flag this order-of-operations subtlety for
the verdict report (M3 checks it against KMZ's matlab); a strictly backward
variant (sigma from rows <= t-1) is provided via STRICT_SIGMA=True.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
STRICT_SIGMA = True    # True = sigma uses rows <= t-1 only (leakage-safe default);
                       # False mirrors the replication repos (rolling incl. current).
                       # The two differ at the 4th decimal; sensitivity in M2.


def build_raw(xlsx: Path = DATA / "PredictorData2022.xlsx") -> pd.DataFrame:
    """Raw (non-standardized) predictors + next-month excess return."""
    m = pd.read_excel(xlsx, sheet_name="Monthly")
    m.index = pd.PeriodIndex(m["yyyymm"].astype(str), freq="M")

    px = m["Index"]
    out = pd.DataFrame(index=m.index)
    out["dp"] = np.log(m["D12"]) - np.log(px)
    out["dy"] = np.log(m["D12"]) - np.log(px.shift(1))
    out["ep"] = np.log(m["E12"]) - np.log(px)
    out["de"] = np.log(m["D12"]) - np.log(m["E12"])
    out["svar"] = m["svar"]
    out["b/m"] = m["b/m"]
    out["ntis"] = m["ntis"]
    out["tbl"] = m["tbl"]
    out["lty"] = m["lty"]
    out["ltr"] = m["ltr"]
    out["tms"] = m["lty"] - m["tbl"]
    out["dfy"] = m["BAA"] - m["AAA"]
    out["dfr"] = m["corpr"] - m["ltr"]
    # infl: used AS-IS to anchor KMZ exactly — VoC's own X (GYdata.mat) applies no
    # extra lag (verified corr 1.0000 without lag, 0.48 with). AUDIT NOTE for the
    # verdict: GW's paper says CPI is released with a one-month delay; whether the
    # distributed column already embeds that lag is ambiguous — flag as a possible
    # (tiny) look-ahead in the original construction; sensitivity available.
    out["infl"] = m["infl"]
    out["mr"] = (m["CRSP_SPvw"] - m["Rfree"]).shift(0)  # this month's excess return, used lagged below

    # Target: NEXT month's excess return aligned to row t
    r_excess = m["CRSP_SPvw"] - m["Rfree"]
    out["R"] = r_excess.shift(-1)
    # mr must be information known at t: the return OF month t (not t+1)
    # (r_excess at row t is month t's return -> already known at end of t)
    out["mr"] = r_excess
    return out


def standardize(raw: pd.DataFrame) -> pd.DataFrame:
    """Backward-looking standardization per the pinned spec.

    The sample is first trimmed to the CRSP era (first valid market return):
    expanding-window sigmas must start where the VoC sample starts, not in
    1871 — otherwise persistent predictors (dp family) get a different scale
    path than the original (diagnosed via zivmi cross-check, 2026-08-17).
    """
    raw = raw.loc[raw["mr"].first_valid_index():]
    df = raw.copy()
    r = df.pop("R")
    if STRICT_SIGMA:
        sigma_r = np.sqrt((r ** 2).rolling(12).mean()).shift(1)
    else:
        sigma_r = np.sqrt((r ** 2).rolling(12).mean())
    r_std = r / sigma_r
    sig_x = df.expanding(min_periods=36).std()
    x_std = df / sig_x
    out = x_std.copy()
    out["R"] = r_std
    return out.dropna()


def voc_anchor_check(raw: pd.DataFrame) -> bool:
    """PRIMARY GATE: raw layer must match the VoC authors' own input data
    (GYdata.mat, distributed with their matlab code) at corr ~ 1.0 per column.
    Known accepted deviation: b/m >= 0.998 (Goyal vintage difference)."""
    from scipy.io import loadmat
    mat = loadmat(DATA / "GYdata.mat")
    cols = ["dfy", "infl", "svar", "de", "lty", "tms", "tbl", "dfr",
            "dp", "dy", "ltr", "ep", "b/m", "ntis"]
    X = pd.DataFrame(mat["X"], columns=cols)
    X.index = pd.PeriodIndex(pd.to_datetime(mat["dates"].flatten(), format="%Y%m"),
                             freq="M") - 1        # their labels run one month later
    X["R"] = mat["Y"].flatten()
    common = raw.index.intersection(X.index)
    print(f"\nPRIMARY ANCHOR vs VoC authors' GYdata.mat ({len(common)} months):")
    ok = True
    for c in cols + ["R"]:
        rho = raw.loc[common, c].corr(X.loc[common, c])
        floor = 0.998 if c == "b/m" else 0.9999
        flag = "" if rho >= floor else "  <-- FAIL"
        ok = ok and rho >= floor
        print(f"  {c:5s} corr = {rho:.4f}{flag}")
    print("ANCHOR:", "PASS" if ok else "FAIL")
    return ok


def main():
    raw = build_raw()
    raw = raw.loc[raw["mr"].first_valid_index():]
    raw.to_parquet(DATA / "raw.parquet")
    voc_anchor_check(raw)
    proc = standardize(raw)
    proc.to_parquet(DATA / "processed.parquet")
    print(f"\nprocessed: {proc.shape[0]} rows x {proc.shape[1]} cols, "
          f"{proc.index[0]} -> {proc.index[-1]}")

    # --- cross-check vs zivmi (their row labels run one month later: shift -1) ---
    z = pd.read_csv(DATA / "zivmi_processed_crosscheck.csv", index_col=0, parse_dates=True)
    z.index = z.index.to_period("M") - 1
    common = proc.index.intersection(z.index)
    print(f"\ncross-check vs zivmi processed ({len(common)} common months, label shift -1):")
    bad = []
    for c in proc.columns:
        zc = "b/m" if c == "b/m" else c
        if zc not in z.columns:
            print(f"  {c:5s}  (absent in zivmi)"); continue
        rho = proc.loc[common, c].corr(z.loc[common, zc])
        flag = "" if rho > 0.99 or (c == "b/m" and rho > 0.95) else "  <-- CHECK"
        if flag:
            bad.append(c)
        print(f"  {c:5s}  corr = {rho:.4f}{flag}")
    print("\nRESULT:", "ALL MATCH" if not bad else f"MISMATCH in {bad}")


if __name__ == "__main__":
    main()
