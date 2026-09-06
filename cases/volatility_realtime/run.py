"""A market-only, expanding-window real-time test inspired by Cederburg et al.

At each month, a risk-aversion-five investor estimates means and covariances
from information available through the preceding month.  The investor can hold
the volatility-managed market, the original market, and cash; the comparator can
hold only the original market and cash.  No post-hoc full-sample allocation is
allowed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from cases.volatility_managed import run as managed_case  # noqa: E402
from verdict import costs, evaluate  # noqa: E402

CASE = Path(__file__).resolve().parent
OUT = CASE / "results.json"
START = pd.Timestamp("2000-01-31")
RISK_AVERSION = 5.0
GROSS_LEVERAGE_CAP = 5.0


def _cap_gross(weights: np.ndarray) -> np.ndarray:
    gross = float(np.abs(weights).sum())
    return weights * min(1.0, GROSS_LEVERAGE_CAP / gross) if gross else weights


def _cer(returns: pd.Series) -> float:
    """Annualized quadratic-utility certainty equivalent, excess-return convention."""
    return float(12 * (returns.mean() - RISK_AVERSION / 2 * returns.var(ddof=1)))


def _summary(returns: pd.Series) -> dict:
    mean_ci = evaluate.block_bootstrap_mean_ci(returns, n_boot=2000, block=6, seed=0)
    sharpe_ci = evaluate.block_bootstrap_sharpe_ci(returns, n_boot=2000, block=6, seed=0,
                                                   periods_per_year=12)
    return {"n_months": int(len(returns)), "mean_annualized": float(returns.mean() * 12),
            "sharpe_annualized": evaluate.sharpe(returns, 12), "cer_annualized": _cer(returns),
            "mean_ci_95": list(mean_ci), "sharpe_ci_95": list(sharpe_ci)}


def execute() -> dict:
    daily = managed_case.load_daily_market()
    monthly, scale = managed_case.make_managed_returns(
        managed_case.monthly_market_with_lagged_variance(daily))
    monthly = monthly.loc[monthly.index >= START].copy()
    if monthly.empty:
        raise ValueError("no real-time evaluation months")

    full = managed_case.make_managed_returns(
        managed_case.monthly_market_with_lagged_variance(daily))[0]
    combo, base, combo_exposure, base_exposure = [], [], [], []
    for timestamp in monthly.index:
        training = full.loc[full.index < timestamp, ["managed_excess", "market_excess"]]
        if len(training) < 120:
            raise ValueError("real-time allocation has fewer than 120 prior months")
        mu = training.mean().to_numpy()
        covariance = training.cov().to_numpy()
        weights = _cap_gross(np.linalg.pinv(covariance) @ mu / RISK_AVERSION)
        base_weight = float(np.clip(mu[1] / (RISK_AVERSION * covariance[1, 1]),
                                    -GROSS_LEVERAGE_CAP, GROSS_LEVERAGE_CAP))
        now = full.loc[timestamp]
        combo.append(float(weights @ now[["managed_excess", "market_excess"]].to_numpy()))
        base.append(float(base_weight * now["market_excess"]))
        combo_exposure.append(float(weights[0] * now["weight"] + weights[1]))
        base_exposure.append(base_weight)
    result = pd.DataFrame({"combined": combo, "baseline": base,
                           "combined_exposure": combo_exposure,
                           "baseline_exposure": base_exposure}, index=monthly.index)
    result["combined_turnover"] = result["combined_exposure"].diff().abs().fillna(0.0)
    result["baseline_turnover"] = result["baseline_exposure"].diff().abs().fillna(0.0)
    difference = result["combined"] - result["baseline"]
    cost_rows = []
    for bps in (0, 5, 10, 20):
        combined_net = result["combined"] - result["combined_turnover"] * bps / 1e4 * 2
        baseline_net = result["baseline"] - result["baseline_turnover"] * bps / 1e4 * 2
        cost_rows.append({"cost_bps": bps, "combined_cer_annualized": _cer(combined_net),
                          "baseline_cer_annualized": _cer(baseline_net),
                          "cer_increment_annualized": _cer(combined_net) - _cer(baseline_net),
                          "combined_sharpe": evaluate.sharpe(combined_net, 12),
                          "baseline_sharpe": evaluate.sharpe(baseline_net, 12)})
    span = evaluate.spanning(result["combined"], result[["baseline"]], hac_lags=3)
    results = {
        "case": "volatility-managed-realtime",
        "source": {
            "paper": "Cederburg et al. (2020), On the Performance of Volatility-Managed Portfolios",
            "paper_local_sha256": "5f82689700a360bed1fd371637d4a62090c6715d0cc9bd85c36fc78bc6129919",
            "public_input_sha256": managed_case._sha256(managed_case.SOURCE),
        },
        "protocol": {
            "decision_time": "every allocation uses an expanding sample ending in t-1",
            "assets": "managed market, unscaled market, and implicit zero-excess-return cash",
            "comparator": "unscaled market and implicit cash only, using the same real-time rule",
            "risk_aversion": RISK_AVERSION,
            "gross_leverage_cap": GROSS_LEVERAGE_CAP,
            "evaluation": "2000-01 through last public-data month; moving-block bootstrap and HAC(3) spanning",
        },
        "normalization_scale_from_parent_case": scale,
        "evaluation": {
            "combined": _summary(result["combined"]), "baseline": _summary(result["baseline"]),
            "difference": {"mean_annualized": float(difference.mean() * 12),
                           "mean_ci_95": list(evaluate.block_bootstrap_mean_ci(
                               difference, n_boot=2000, block=6, seed=0)),
                           "sharpe_annualized": evaluate.sharpe(difference, 12)},
            "spanning_combined_on_baseline": span,
            "mean_combined_turnover": float(result["combined_turnover"].mean()),
            "mean_baseline_turnover": float(result["baseline_turnover"].mean()),
            "cost_sensitivity": cost_rows,
        },
        "protocol_coverage": {
            "complete": False,
            "not_executed": [
                "the paper's 103-strategy cross-section and other factor inputs",
                "the paper's exact rolling-window, leverage, and portfolio-choice robustness grid",
                "a byte-for-byte replication using the paper's historical data vintage",
            ],
        },
    }
    OUT.write_text(json.dumps(results, indent=2, allow_nan=False) + "\n")
    return results


if __name__ == "__main__":
    print(json.dumps(execute()["evaluation"], indent=2))
