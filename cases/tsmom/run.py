#!/usr/bin/env python3
"""Execute the pre-registered protocol for `time-series-momentum`.

The protocol was registered before this file existed and is not edited by it.
Every clause below names the clause it executes, so a reader can check that the
test performed is the test promised rather than a more convenient one.

    micromamba run -n verdict python cases/tsmom/run.py
    micromamba run -n verdict python cases/tsmom/run.py --panel data/panel.csv

The four kill criteria, restated from the registry card:

  K1  returns are spanned by passive long + cross-sectional momentum, leaving
      an alpha whose confidence interval contains zero
  K2  the effect is absent at conventional significance in the sealed
      post-publication block
  K3  net of costs at plausible levels, the interval on the mean contains zero
  K4  the result SURVIVES randomising the signal's sign — which would mean the
      volatility scaling, not the momentum, is doing the work

K4 is the one that reads backwards: there, survival is the death sentence.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
sys.path.insert(0, str(HERE))

from verdict import costs as C          # noqa: E402
from verdict import evaluate as E       # noqa: E402
from verdict.splits import SealedHoldout, HoldoutAlreadyUnsealed   # noqa: E402

import tsmom as T                       # noqa: E402

VOL_WINDOW = 60
LOOKBACK = 12
SIGN_DRAWS = 200
SEAL_FROM = "2021-01-01"
COST_GRID = (0, 5, 10, 20, 40)
PLAUSIBLE_BPS = 10.0     # generous for liquid futures; a harder bar for K3 to clear
MONTHS = 12


def _stats(r: pd.Series) -> dict:
    lo, hi = E.block_bootstrap_sharpe_ci(r, periods_per_year=MONTHS)
    mean_lo, mean_hi = E.block_bootstrap_mean_ci(r)
    return {
        "n_months": int(len(r)),
        "mean_monthly": float(r.mean()),
        "ann_return": float(r.mean() * MONTHS),
        "ann_vol": float(r.std(ddof=1) * np.sqrt(MONTHS)),
        "sharpe": float(E.sharpe(r, periods_per_year=MONTHS)),
        "sharpe_ci": [float(lo), float(hi)],
        "sharpe_ci_excludes_zero": bool(lo > 0 or hi < 0),
        "mean_ci_monthly": [float(mean_lo), float(mean_hi)],
        "mean_ci_excludes_zero": bool(mean_lo > 0 or mean_hi < 0),
    }


def execute(closes: pd.DataFrame, vols: dict[int, pd.DataFrame], *,
            vol_window: int = VOL_WINDOW, lookback: int = LOOKBACK,
            sign_draws: int = SIGN_DRAWS, seal_from: str | None = SEAL_FROM,
            ledger: Path | None = None, label: str = "panel") -> dict:
    rets = T.market_returns(closes)
    vol = vols[vol_window]

    pos = T.tsmom_positions(closes, vol, lookback)
    strat = T.portfolio_returns(pos, rets)
    passive = T.portfolio_returns(T.passive_positions(closes, vol, lookback), rets)
    xsmom = T.portfolio_returns(T.xsmom_positions(closes, vol, lookback), rets)

    idx = strat.index.intersection(passive.index).intersection(xsmom.index)
    strat, passive, xsmom = strat[idx], passive[idx], xsmom[idx]

    out: dict = {
        "label": label,
        "config": {"vol_window": vol_window, "lookback_months": lookback,
                   "sigma_each": T.SIGMA_EACH, "max_pos": T.MAX_POS,
                   "markets": list(closes.columns), "sign_draws": sign_draws},
        "span": [str(idx[0].date()), str(idx[-1].date())],
        "strategy": _stats(strat),
        "benchmarks": {"passive_long": _stats(passive), "xs_momentum": _stats(xsmom)},
    }

    # --- K1: spanning ------------------------------------------------------
    sp = E.spanning(strat, pd.DataFrame({"passive_long": passive, "xs_momentum": xsmom}))
    alpha_ann = sp["alpha"] * MONTHS
    out["K1_spanning"] = {
        "alpha_monthly": float(sp["alpha"]),
        "alpha_annualized": float(alpha_ann),
        "t_stat_hac": float(sp["alpha_t"]),
        "alpha_ci_monthly": [float(x) for x in sp["alpha_ci"]],
        "alpha_ci_annualized": [float(x * MONTHS) for x in sp["alpha_ci"]],
        "betas": {k: float(v) for k, v in sp["betas"].items()},
        "beta_t": {k: float(v) for k, v in sp["beta_t"].items()},
        "r_squared": float(sp["r2"]),
        "nobs": int(sp["nobs"]),
        "alpha_indistinguishable_from_zero": bool(sp["alpha_ci"][0] <= 0 <= sp["alpha_ci"][1]),
    }
    out["K1_fires"] = out["K1_spanning"]["alpha_indistinguishable_from_zero"]

    # --- K4: sign randomisation -------------------------------------------
    # Every draw keeps the strategy's position magnitudes and destroys only the
    # timing decision, so the spread below is what the sizing scheme alone earns.
    draws = [E.sharpe(T.portfolio_returns(
        T.randomized_sign_positions(closes, vol, lookback, seed=s), rets)[idx],
        periods_per_year=MONTHS) for s in range(sign_draws)]
    draws = np.asarray(draws, float)
    pct = float((draws < out["strategy"]["sharpe"]).mean())
    out["K4_sign_randomisation"] = {
        "draws": sign_draws,
        "random_sharpe_mean": float(draws.mean()),
        "random_sharpe_p05": float(np.percentile(draws, 5)),
        "random_sharpe_p95": float(np.percentile(draws, 95)),
        "strategy_sharpe": out["strategy"]["sharpe"],
        "strategy_percentile_vs_random": pct,
        "signal_not_distinguishable_from_random": bool(pct < 0.95),
    }
    out["K4_fires"] = out["K4_sign_randomisation"]["signal_not_distinguishable_from_random"]

    # --- K3: costs ---------------------------------------------------------
    turn = T.turnover(pos).reindex(idx).fillna(0.0)
    grid = C.cost_sensitivity(strat, turn, bps_grid=COST_GRID,
                              periods_per_year=MONTHS, sides=1)
    be = C.breakeven_cost_bps(float(strat.mean()), float(turn.mean()), sides=1)
    # The clause says "net of roll and transaction costs at plausible levels",
    # so the interval is taken on the net series rather than the gross one.
    # PLAUSIBLE_BPS is generous for liquid futures, where a round turn plus roll
    # is usually a low single-digit number of basis points; being generous here
    # only makes the criterion harder to fire.
    net = strat - turn * (PLAUSIBLE_BPS / 1e4)
    net_stats = _stats(net)
    out["K3_costs"] = {
        "mean_turnover_per_rebalance": float(turn.mean()),
        "breakeven_cost_bps": float(be),
        "plausible_cost_bps": PLAUSIBLE_BPS,
        "net_at_plausible": net_stats,
        "cost_convention": "bps per unit of absolute position change (round turn already counted)",
        "grid": grid.reset_index().to_dict(orient="records"),
    }
    out["K3_fires"] = not net_stats["mean_ci_excludes_zero"]

    # --- diagnostics -------------------------------------------------------
    dec = T.decompose(pos, rets).reindex(idx).dropna()
    total = float(dec.sum(axis=1).mean())
    out["diagnostic_tilt_vs_timing"] = {
        "tilt_ann": float(dec["tilt"].mean() * MONTHS),
        "timing_ann": float(dec["timing"].mean() * MONTHS),
        "tilt_share_of_total": float(dec["tilt"].mean() / total) if total else None,
        "timing_sharpe": float(E.sharpe(dec["timing"], periods_per_year=MONTHS)),
    }
    contrib = T.per_market_contributions(pos, rets).reindex(idx)
    out["diagnostic_per_market_ann"] = {
        c: float(contrib[c].mean() * MONTHS / len(contrib.columns))
        for c in contrib.columns
    }
    eq = T.portfolio_returns(np.sign(closes.pct_change(lookback, fill_method=None)), rets)[idx]
    out["diagnostic_equal_weight_no_vol_scaling"] = _stats(eq)

    # --- robustness --------------------------------------------------------
    rob = []
    # The lookback rows carry intervals as well as point estimates. Without them
    # the report could only say a variant "looks better", and a variant that
    # looks better is exactly the thing a reader needs to see tested rather than
    # asserted — it is the number a free hand would have reported.
    for lb in (3, 6, 9, 12, 18, 24):
        r = T.portfolio_returns(T.tsmom_positions(closes, vol, lb), rets).dropna()
        lo, hi = E.block_bootstrap_sharpe_ci(r, periods_per_year=MONTHS)
        rob.append({"axis": "lookback_months", "value": lb,
                    "sharpe": float(E.sharpe(r, periods_per_year=MONTHS)),
                    "sharpe_ci": [float(lo), float(hi)],
                    "ci_excludes_zero": bool(lo > 0 or hi < 0)})
    for w in sorted(vols):
        r = T.portfolio_returns(T.tsmom_positions(closes, vols[w], lookback), rets)
        rob.append({"axis": "vol_window_days", "value": w,
                    "sharpe": float(E.sharpe(r.dropna(), periods_per_year=MONTHS))})
    for sec, names in T.SECTORS.items():
        keep = [c for c in closes.columns if c not in names]
        if len(keep) >= 2:
            r = T.portfolio_returns(T.tsmom_positions(closes[keep], vol[keep], lookback),
                                    rets[keep])
            rob.append({"axis": "drop_sector", "value": sec,
                        "sharpe": float(E.sharpe(r.dropna(), periods_per_year=MONTHS))})
    # Sensitivity to the tail of the sample. One move in the panel — CL in March
    # 2026, +54% in a month — could not be corroborated against a second source,
    # so the conclusion is checked with the last year removed as well as with the
    # balanced-panel period only.
    for sample_name, cut in (("drop_last_12m", strat.index[-12]),
                             ("full_7_markets_only", pd.Timestamp("2013-04-30"))):
        s = strat[strat.index < cut] if sample_name == "drop_last_12m" else strat[strat.index >= cut]
        if len(s) >= 24:
            rob.append({"axis": "sample", "value": sample_name,
                        "n_months": int(len(s)),
                        "sharpe": float(E.sharpe(s, periods_per_year=MONTHS))})
    out["robustness"] = rob
    out["protocol_coverage"] = {
        "executed": ["lookback horizons", "volatility estimation window", "drop sectors"],
        "not_executed": [
            "holding periods beyond one month",
            "drop the most correlated markets",
            "integer-contract and multiplier-aware sizing",
        ],
        "complete": False,
    }
    signs = {np.sign(r["sharpe"]) for r in rob}
    out["conclusion_stable_across_perturbations"] = bool(len(signs) == 1)

    # --- K2: the sealed block ---------------------------------------------
    if seal_from and ledger is not None:
        held = strat[strat.index >= seal_from]
        if len(held) >= 12:
            cfg = {"vol_window": vol_window, "lookback": lookback,
                   "markets": list(closes.columns), "seal_from": seal_from,
                   "sizing": [T.SIGMA_EACH, T.MAX_POS]}
            box = SealedHoldout(f"tsmom-{label}-post-publication", ledger)
            try:
                rec = box.unseal("final evaluation of the pre-registered protocol", cfg)
                st = _stats(held)
                out["K2_sealed_block"] = {
                    "seal_from": seal_from, "unsealed": True,
                    "opening": {k: rec[k] for k in ("reason", "fingerprint") if k in rec},
                    **st,
                }
                out["K2_fires"] = not st["sharpe_ci_excludes_zero"]
            except HoldoutAlreadyUnsealed as exc:
                out["K2_sealed_block"] = {"unsealed": False, "refused": str(exc)}
                out["K2_fires"] = None

    out["_series"] = pd.DataFrame({"strategy": strat, "passive_long": passive,
                                   "xs_momentum": xsmom, "net": net,
                                   "tilt": dec["tilt"], "timing": dec["timing"]})
    out["_sign_draws"] = draws

    fired = [k for k in ("K1_fires", "K2_fires", "K3_fires", "K4_fires")
             if out.get(k) is True]
    out["kill_criteria_fired"] = fired
    out["claim_survives"] = bool(not fired)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", default=str(HERE / "data" / "panel.csv"))
    ap.add_argument("--out", default=str(HERE / "results.json"))
    args = ap.parse_args()

    panel = Path(args.panel)
    if not panel.exists():
        print(f"No panel at {panel}.\n"
              f"Run cases/tsmom/qc_export.py in a QuantConnect research notebook and\n"
              f"paste the blob back; decode it with cases/tsmom/decode_panel.py.\n"
              f"The card stays protocol-ready-data-gated until then.")
        return 2

    closes, vols = T.load_panel(panel)
    (HERE / "results").mkdir(exist_ok=True)
    res = execute(closes, vols, ledger=HERE / "results" / "holdout_ledger.json",
                  label="qc-7-market")

    # The series come out separately so the figures are drawn from exactly the
    # numbers the verdict quotes, not from a second computation of them.
    res.pop("_series").to_csv(HERE / "results_series.csv")
    np.savetxt(HERE / "results" / "sign_draws.csv", res.pop("_sign_draws"), fmt="%.6f")
    Path(args.out).write_text(json.dumps(res, indent=2))

    print(f"{res['span'][0]} .. {res['span'][1]}   {len(res['config']['markets'])} markets")
    print(f"  strategy      Sharpe {res['strategy']['sharpe']:+.2f}  "
          f"CI [{res['strategy']['sharpe_ci'][0]:+.2f}, {res['strategy']['sharpe_ci'][1]:+.2f}]")
    print(f"  passive long  Sharpe {res['benchmarks']['passive_long']['sharpe']:+.2f}")
    print(f"  xs momentum   Sharpe {res['benchmarks']['xs_momentum']['sharpe']:+.2f}")
    print(f"  K1 spanning   alpha {res['K1_spanning']['alpha_annualized']:+.2%} "
          f"t={res['K1_spanning']['t_stat_hac']:+.2f}")
    print(f"  K3 breakeven  {res['K3_costs']['breakeven_cost_bps']:.1f} bps")
    print(f"  K4 random     strategy at {res['K4_sign_randomisation']['strategy_percentile_vs_random']:.0%} "
          f"of {res['K4_sign_randomisation']['draws']} sign draws")
    print(f"\n  fired: {res['kill_criteria_fired'] or 'none'}   "
          f"claim survives: {res['claim_survives']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
