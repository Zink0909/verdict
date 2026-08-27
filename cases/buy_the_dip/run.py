#!/usr/bin/env python3
"""Retrofit case: buying dips in wide-moat names, expressed as long calls.

The trade record (2,392 dip-buys on a point-in-time wide-moat universe, each a
long call priced from real daily option chains) was produced in the original
project. This script re-derives the verdict from that record *through the
framework*, which does three things a re-print of the old numbers would not:

  1. **Independent accounting audit.** Contract counts and dollar P&L are
     recomputed from primitives (`costs.budget_position`) rather than trusted.
  2. **Independent universe rebuild.** The point-in-time moat universe is
     rebuilt from raw fundamentals with `pointintime.persistent_quality` and
     compared against the stored membership — the construction does not get to
     vouch for itself.
  3. **A mechanism decomposition the original only asserted.** Every trade's
     P&L is split into delta / vega / theta with `options.pnl_attribution`,
     which tests the prior that implied volatility mean-reverting against the
     position was a major headwind. It was not — see the verdict.

Original headline to reproduce: mean -$263/trade, median -$2,428, win rate 0.36.

  micromamba run -n verdict python cases/buy_the_dip/run.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import brentq

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))

from verdict import costs as C          # noqa: E402
from verdict import diagnose as D       # noqa: E402
from verdict import options as O        # noqa: E402
from verdict import pointintime as PIT  # noqa: E402
from verdict import robust as R         # noqa: E402

DATA = HERE / "data"
BUDGET, MULTIPLIER, RFREE = 10_000.0, 100, 0.02
MOAT_BASE = {"level_min": 0.15, "consistency": 0.70, "window": 8, "max_cv": 0.15}
ASOF_YEARS = range(2014, 2025)


# ---------------------------------------------------------------- loading ----

def load() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    T = pd.read_parquet(DATA / "universe_trades.parquet")
    T["entry_date"] = pd.to_datetime(T["entry_date"])
    T["exit_date"] = pd.to_datetime(T["exit_date"])
    T["held_days"] = (T["exit_date"] - T["entry_date"]).dt.days
    T["dte_in"] = T["dte_out"] + T["held_days"]
    T["entry_year"] = T["entry_date"].dt.year
    F = pd.read_csv(DATA / "fundamentals.csv")
    U = pd.read_parquet(DATA / "moat_universe.parquet")
    return T, F, U


# ------------------------------------------------------------- audit layer ----

def audit_accounting(T: pd.DataFrame) -> dict:
    """Re-derive contracts and dollar P&L from primitives; trust nothing."""
    n_re, pnl_re = [], []
    for cost_in, proceeds in zip(T["cost_in"], T["proceeds"]):
        n, pnl, _ = C.budget_pnl(cost_in, proceeds, BUDGET, MULTIPLIER)
        n_re.append(n); pnl_re.append(pnl)
    n_re = np.array(n_re); pnl_re = np.array(pnl_re)
    return {
        "contracts_mismatch": int((n_re != T["contracts"].to_numpy()).sum()),
        "pnl_max_abs_error": float(np.abs(pnl_re - T["dollar_pnl"].to_numpy()).max()),
        "invested_max": float((T["contracts"] * T["cost_in"] * MULTIPLIER).max()),
    }


def rebuild_universe(F: pd.DataFrame, **screen_kw) -> set[tuple[int, str]]:
    """Point-in-time moat membership rebuilt from raw fundamentals."""
    kw = {**MOAT_BASE, **screen_kw}

    def screen(g: pd.DataFrame) -> bool:
        return PIT.persistent_quality(g["roic"], g["gross_margin"],
                                      level_min=kw["level_min"], window=kw["window"],
                                      consistency=kw["consistency"], max_cv=kw["max_cv"])

    members = set()
    for year in ASOF_YEARS:
        asof = pd.Timestamp(f"{year}-06-30")
        for tk in PIT.universe_asof(F, asof, screen, order_col="year"):
            members.add((year, tk))
    return members


def audit_universe(F: pd.DataFrame, U: pd.DataFrame) -> dict:
    """Rebuild vs stored membership, plus a look-ahead check on the inputs.

    Two comparisons, because they answer different questions. The unrestricted
    one includes names the screen admits but the original universe never held —
    the original also intersected with point-in-time index membership, which is
    not part of the exported data, so those are expected. Restricting to names
    the stored universe contains isolates whether the *screen itself* agrees.
    """
    rebuilt = rebuild_universe(F)
    stored = set(zip(U["year"], U["ticker"]))
    names = set(U["ticker"])
    restricted = {(y, t) for y, t in rebuilt if t in names}
    full = R.membership_stability(stored, rebuilt)
    scr = R.membership_stability(stored, restricted)
    leaks = []
    for year in ASOF_YEARS:
        asof = pd.Timestamp(f"{year}-06-30")
        used = F[pd.to_datetime(F["asof"]) <= asof]
        leaks += PIT.audit_no_future_rows(used, asof, "asof")
    return {"stored_pairs": len(stored), "rebuilt_pairs": len(rebuilt),
            "jaccard_unrestricted": full["jaccard"],
            "added_unrestricted": full["n_added"],
            "added_names": sorted({t for _, t in rebuilt - stored}),
            "screen_pairs_reproduced": len(stored) - scr["n_dropped"],
            "screen_jaccard": scr["jaccard"],
            "screen_extra_pairs": scr["n_added"],
            "screen_unconfirmed": [f"{y} {t}" for y, t in sorted(scr["dropped"])],
            "lookahead_problems": leaks}


def option_clock(T: pd.DataFrame) -> dict:
    """The clock probe: did the dips that 'never recovered' recover after expiry?

    The probe itself needed the vendor platform (daily history for 282 names and
    dates) and its printed output was never saved to disk; it was recovered from
    the original session's transcript. A recovered number is worth exactly as
    much as its link to the data, so the link is checked rather than asserted:
    deduplicating this trade record's never-recovered trades to unique dip events
    must reproduce the probe's denominator exactly.
    """
    probe = json.loads((DATA / "option_clock_probe.json").read_text())
    never = T[T["rec_status"] == "never"]
    events = never.groupby(["ticker", "entry_date"]).ngroups
    ok = events == probe["n_events"]
    return {"n_events_probe": probe["n_events"], "n_events_rederived": int(events),
            "denominator_verified": bool(ok),
            "n_recovered_after_exit": probe["n_recovered_after_exit"],
            "share": probe["share_recovered_after_exit"],
            "horizon_days": probe["horizon_days"],
            "recovery_level": probe["recovery_level"],
            "reproducible_locally": probe["reproducible_locally"],
            "provenance": probe["provenance"]}


def observed_mechanism(T: pd.DataFrame) -> dict:
    """What actually moved, measured — no model in this section.

    The prior under test (the reason both strikes were carried through the
    original study) was a double headwind: implied volatility is elevated when
    the dip is bought and mean-reverts down as the name recovers, so the long
    call pays a rich premium and then gives some back through vega. The test
    needs no model at all: the entry and exit implied volatilities of the very
    contract that was traded are in the record.

    A fixed-strike IV comparison across time also moves along the skew and the
    term structure, and both distort most in the last weeks before expiry, so
    the same table is reported on trades closed at least 30 days from expiry.
    """
    iv = T[T["iv_in"].notna() & T["iv_out"].notna()].copy()
    iv["d_iv"] = iv["iv_out"] - iv["iv_in"]
    far = iv[iv["dte_out"] >= 30]

    def table(df):
        g = df.groupby("rec_status")["d_iv"]
        return {k: {"mean": float(v), "median": float(g.median()[k]),
                    "n": int(g.size()[k]), "share_falling": float(g.apply(lambda s: (s < 0).mean())[k])}
                for k, v in g.mean().items()}

    u = T[T["S_out"].notna()].copy()
    u["ret_S"] = u["S_out"] / u["S_in"] - 1.0
    return {
        "iv_all": {"n": int(len(iv)), "mean": float(iv["d_iv"].mean()),
                   "median": float(iv["d_iv"].median()),
                   "share_falling": float((iv["d_iv"] < 0).mean()),
                   "by_status": table(iv)},
        "iv_far_from_expiry": {"n": int(len(far)), "mean": float(far["d_iv"].mean()),
                               "median": float(far["d_iv"].median()),
                               "share_falling": float((far["d_iv"] < 0).mean()),
                               "by_status": table(far)},
        "underlying_move": {f"{d}|{s}": {"mean": float(v), "n": int(n)} for (d, s), v, n
                            in zip(u.groupby(["depth", "rec_status"])["ret_S"].mean().index,
                                   u.groupby(["depth", "rec_status"])["ret_S"].mean(),
                                   u.groupby(["depth", "rec_status"])["ret_S"].size())},
    }


# ---------------------------------------------------------- mechanism layer ----

def _strike_from_delta(S: float, target_delta: float, T0: float, sigma: float) -> float:
    """Recover the strike implied by the target delta at entry (modelled)."""
    try:
        return float(brentq(
            lambda K: O.bs_greeks(S, K, T0, RFREE, sigma, True)["delta"] - target_delta,
            0.05 * S, 5.0 * S, maxiter=200))
    except (ValueError, RuntimeError):
        return float("nan")


def attribution(T: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Split each trade's P&L into delta / vega / theta, in budget dollars.

    Modelled, and therefore only used to explain a loss the real chains already
    established — never to establish one. Its own validity is checked first:
    the modelled entry price is compared with the price actually paid.
    """
    ok = (T["iv_in"].notna() & T["iv_out"].notna() & T["S_out"].notna()
          & np.array([O.iv_is_trustworthy(iv, d, dl) for iv, d, dl
                      in zip(T["iv_in"], T["dte_in"], T["delta"])]))
    sub = T[ok].copy()
    rows = []
    for _, x in sub.iterrows():
        T0, dt = x["dte_in"] / 365.0, x["held_days"] / 365.0
        K = _strike_from_delta(x["S_in"], x["delta"], T0, x["iv_in"])
        if not np.isfinite(K):
            continue
        a = O.pnl_attribution(x["S_in"], x["S_out"], x["iv_in"], x["iv_out"],
                              K, T0, dt, RFREE)
        scale = x["contracts"] * MULTIPLIER          # per-contract -> per-$10k budget
        rows.append({"depth": x["depth"], "strike": x["strike"],
                     "actual_pnl": x["dollar_pnl"],
                     "model_pnl": a["total"] * scale, "delta_$": a["delta"] * scale,
                     "vega_$": a["vega"] * scale, "theta_$": a["theta"] * scale,
                     "residual_$": a["residual"] * scale,
                     "model_entry_px": a["p0"], "paid_entry_px": x["cost_in"],
                     "d_iv": x["iv_out"] - x["iv_in"]})
    A = pd.DataFrame(rows)
    validity = {
        "n": len(A),
        "entry_price_corr": float(A["model_entry_px"].corr(A["paid_entry_px"])),
        "entry_price_median_ratio": float((A["model_entry_px"] / A["paid_entry_px"]).median()),
        "pnl_corr": float(A["model_pnl"].corr(A["actual_pnl"])),
        "model_minus_actual_mean": float((A["model_pnl"] - A["actual_pnl"]).mean()),
    }
    return A, validity


# --------------------------------------------------------- robustness layer ----

def robustness(T: pd.DataFrame, F: pd.DataFrame) -> pd.DataFrame:
    """Do the conclusions survive perturbing the universe definition?"""
    tested = set(T["ticker"].unique())
    base_members = rebuild_universe(F)

    def cell(level_min: float, consistency: float) -> dict:
        members = rebuild_universe(F, level_min=level_min, consistency=consistency)
        keep = {(y, t) for (y, t) in members if t in tested}
        sub = T[[(y, t) in keep for y, t in zip(T["entry_year"], T["ticker"])]]
        stab = R.membership_stability(base_members, members)
        untested = R.untested_additions(stab["added"], tested)
        deep = sub[sub["depth"] == "deep"]
        itm = deep[deep["strike"] == "ITM"]["dollar_pnl"].mean()
        otm = deep[deep["strike"] == "OTM"]["dollar_pnl"].mean()
        return {"label": f"roic>={level_min:.2f}/consist>={consistency:.2f}",
                "n_trades": len(sub),
                "mean_pnl": float(sub["dollar_pnl"].mean()) if len(sub) else np.nan,
                "median_pnl": float(sub["dollar_pnl"].median()) if len(sub) else np.nan,
                "win": float((sub["dollar_pnl"] > 0).mean()) if len(sub) else np.nan,
                "never_share": float((sub["rec_status"] == "never").mean()) if len(sub) else np.nan,
                "deep_itm_minus_otm": float(itm - otm) if len(deep) else np.nan,
                "members": len(members), "untested_added": len(untested),
                "untested_names": ",".join(untested)}

    grid = {"level_min": [0.13, 0.15, 0.18], "consistency": [0.60, 0.70, 0.80]}
    out = R.sweep(grid, cell)
    base_label = f"roic>={MOAT_BASE['level_min']:.2f}/consist>={MOAT_BASE['consistency']:.2f}"
    return R.conclusion_stability(
        out, ["mean_pnl", "median_pnl", "deep_itm_minus_otm"], base_label=base_label)


# ------------------------------------------------------------------- main ----

def main() -> dict:
    T, F, U = load()
    print(f"trades: {len(T)}   names: {T['ticker'].nunique()}   "
          f"{T['entry_date'].min().date()} -> {T['exit_date'].max().date()}\n")

    print("=== audit 1: accounting re-derived from primitives ===")
    acct = audit_accounting(T)
    print(f"  contract-count mismatches: {acct['contracts_mismatch']}")
    print(f"  max |P&L re-derivation error|: ${acct['pnl_max_abs_error']:.6f}")

    print("\n=== audit 2: point-in-time universe rebuilt from raw fundamentals ===")
    uni = audit_universe(F, U)
    print(f"  screen reproduces {uni['screen_pairs_reproduced']}/{uni['stored_pairs']} stored "
          f"(year,name) pairs (jaccard {uni['screen_jaccard']:.3f}); "
          f"unconfirmed: {uni['screen_unconfirmed'] or 'none'}")
    print(f"  unrestricted rebuild admits {uni['added_unrestricted']} extra pairs "
          f"({', '.join(uni['added_names'])}) — the original also required index membership, "
          "which the exported data does not carry")
    print(f"  look-ahead problems in the inputs: {uni['lookahead_problems'] or 'none'}")

    print("\n=== headline (reproduce the original) ===")
    head = {"n": len(T), "names": int(T["ticker"].nunique()),
            "mean_pnl": float(T["dollar_pnl"].mean()),
            "median_pnl": float(T["dollar_pnl"].median()),
            "win": float((T["dollar_pnl"] > 0).mean())}
    print(f"  mean ${head['mean_pnl']:.0f}   median ${head['median_pnl']:.0f}   "
          f"win {head['win']:.3f}")

    print("\n=== playbook: option expression vs the underlying ===")
    ev = D.expression_vs_underlying(T, budget=BUDGET)
    print(f"  n={ev['n']}  stock mean ${ev['underlying_mean']:.0f} (win {ev['underlying_win']:.3f})"
          f"  option mean ${ev['deriv_mean']:.0f} (win {ev['deriv_win']:.3f})")
    print(f"  expression drag ${ev['expression_drag']:.0f}/trade | "
          f"option wins when stock wins: {ev['deriv_win_when_underlying_wins']:.3f}")
    missing = T[T["S_out"].isna()]
    ev["coverage"] = {
        "covered": int(ev["n"]), "total": int(len(T)),
        "excluded_no_exit_price": int(len(missing)),
        "excluded_mean_option_pnl": float(missing["dollar_pnl"].mean()),
        "covered_mean_option_pnl": float(T[T["S_out"].notna()]["dollar_pnl"].mean())}
    print(f"  coverage {ev['n']}/{len(T)}: the {len(missing)} trades without an exit price for "
          f"the underlying averaged ${missing['dollar_pnl'].mean():.0f} for the option "
          "(better than the covered set), so the measured drag is, if anything, the pessimistic end")

    print("\n=== mechanism, observed (no model): did volatility bite on the way back? ===")
    obs = observed_mechanism(T)
    for key, label in (("iv_all", "all trades with usable IV"),
                       ("iv_far_from_expiry", "exited >=30d before expiry")):
        b = obs[key]
        print(f"  {label}: n={b['n']}  mean d_IV {b['mean']:+.3f}  median {b['median']:+.3f}  "
              f"share falling {b['share_falling']:.2f}")
        for st in ("recovered", "missed", "never"):
            if st in b["by_status"]:
                s = b["by_status"][st]
                print(f"      {st:10s} n={s['n']:4d}  mean {s['mean']:+.3f}  "
                      f"share falling {s['share_falling']:.2f}")
    print("  underlying move at exit (mean):", {k: round(v["mean"], 3)
                                                for k, v in obs["underlying_move"].items()})

    print("\n=== recovery status (honest non-recovery accounting) ===")
    rec = {s: int((T["rec_status"] == s).sum()) for s in ["never", "missed", "recovered"]}
    for s, n in rec.items():
        m = T[T["rec_status"] == s]["dollar_pnl"].mean()
        print(f"  {s:10s} n={n:4d} ({n/len(T):.0%})  mean ${m:.0f}")

    print("\n=== the option clock (probe output recovered from the session transcript) ===")
    clk = option_clock(T)
    print(f"  denominator check: probe {clk['n_events_probe']} dip events vs "
          f"{clk['n_events_rederived']} re-derived here -> "
          f"{'VERIFIED' if clk['denominator_verified'] else 'MISMATCH'}")
    print(f"  {clk['n_recovered_after_exit']}/{clk['n_events_probe']} "
          f"({clk['share']:.1%}) of never-recovered dips returned to the entry price "
          f"within {clk['horizon_days']} days AFTER exit")
    print("  not locally reproducible (needs vendor daily history); level = entry price, "
          "so this is an upper bound")

    print("\n=== dip depth x strike ===")
    g = T.groupby(["depth", "strike"])["dollar_pnl"].agg(["mean", "size"]).round(0)
    print(g.to_string())

    print("\n=== mechanism, modelled: delta / vega / theta sizing ===")
    A, validity = attribution(T)
    print(f"  usable trades {validity['n']}; modelled entry price vs paid: "
          f"corr {validity['entry_price_corr']:.3f}, median ratio "
          f"{validity['entry_price_median_ratio']:.3f}")
    print(f"  modelled vs actual P&L corr {validity['pnl_corr']:.3f}; modelled is "
          f"${validity['model_minus_actual_mean']:.0f}/trade optimistic in LEVEL "
          "(reconstructed strike + mid pricing), so read the composition, not the totals")
    attr = A.groupby("depth")[["actual_pnl", "model_pnl", "delta_$", "vega_$",
                               "theta_$", "residual_$", "d_iv"]].mean().round(1)
    print(attr.to_string())
    overall = A[["delta_$", "vega_$", "theta_$"]].mean()
    print(f"  overall: delta ${overall['delta_$']:.0f}  vega ${overall['vega_$']:.0f}  "
          f"theta ${overall['theta_$']:.0f}   (positive vega = IV rose, not fell)")

    print("\n=== robustness: perturbing the moat definition ===")
    rob = robustness(T, F)
    cols = ["label", "members", "n_trades", "mean_pnl", "median_pnl", "win",
            "never_share", "deep_itm_minus_otm", "untested_added", "all_agree"]
    print(rob[cols].round(3).to_string(index=False))
    print(f"  conclusions keep their sign in {int(rob['all_agree'].sum())}/{len(rob)} cells")
    untested = sorted({n for s in rob["untested_names"] for n in s.split(",") if n})
    print(f"  admitted by looser cutoffs but never backtested: {untested or 'none'}")

    out = {"headline": head, "audit_accounting": acct, "audit_universe": uni,
           "expression": ev, "recovery": rec, "option_clock": clk,
           "observed_mechanism": obs,
           "depth_strike": {f"{d}|{s}": float(v) for (d, s), v in
                            T.groupby(["depth", "strike"])["dollar_pnl"].mean().items()},
           "attribution": {"validity": validity,
                           "by_depth": attr.to_dict(orient="index"),
                           "overall": {k: float(v) for k, v in overall.items()}},
           "robustness": {"cells": int(len(rob)), "all_agree": int(rob["all_agree"].sum()),
                          "untested_names": untested,
                          "table": rob[cols].to_dict(orient="records")}}
    (HERE / "results.json").write_text(json.dumps(out, indent=2, default=float))
    A.to_parquet(HERE / "results_attribution.parquet")
    rob.to_csv(HERE / "results_robustness.csv", index=False)
    print(f"\nsaved {HERE/'results.json'}, results_attribution.parquet, results_robustness.csv")
    return out


if __name__ == "__main__":
    main()
