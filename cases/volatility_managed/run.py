"""Bounded audit of the volatility-managed market transformation.

The paper scales month-t excess market returns by inverse realized variance of
month t-1.  This script makes a narrower, reproducible claim: does that
transformation add incremental performance to the public Fama/French market
series after a normalization fixed in an earlier calibration period?

It is intentionally not a full reproduction of Moreira--Muir's nine-factor
study.  See SOURCES.md and protocol_coverage in results.json.
"""
from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT))

from verdict import costs, evaluate  # noqa: E402

CASE = Path(__file__).resolve().parent
SOURCE = CASE / "source" / "ff5_daily.zip"
OUT = CASE / "results.json"
CALIBRATION_END = pd.Timestamp("1999-12-31")
HOLDOUT_START = pd.Timestamp("2000-01-01")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_daily_market(path: Path = SOURCE) -> pd.DataFrame:
    """Read the official archive, preserving only dated market excess returns."""
    if not path.is_file():
        raise FileNotFoundError(f"missing pinned public input: {path}")
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != 1:
            raise ValueError("French source archive must contain exactly one CSV")
        raw = archive.read(names[0]).decode("utf-8")
    lines = raw.splitlines()
    header = next(i for i, line in enumerate(lines) if line.startswith(",Mkt-RF,"))
    records = []
    for line in lines[header + 1:]:
        fields = [field.strip() for field in line.split(",")]
        if len(fields) != 7 or not fields[0].isdigit() or len(fields[0]) != 8:
            break
        records.append(fields)
    frame = pd.DataFrame(records, columns=["date", "market_excess", "SMB", "HML", "RMW", "CMA", "RF"])
    frame["date"] = pd.to_datetime(frame["date"], format="%Y%m%d")
    for column in frame.columns[1:]:
        frame[column] = pd.to_numeric(frame[column], errors="raise") / 100.0
    if frame.empty or frame["date"].duplicated().any() or not frame["date"].is_monotonic_increasing:
        raise ValueError("official daily market series is empty, duplicated, or not chronological")
    return frame[["date", "market_excess"]]


def monthly_market_with_lagged_variance(daily: pd.DataFrame) -> pd.DataFrame:
    """Compound daily returns within a month and use only the prior month's variance."""
    data = daily.copy()
    data["month"] = data["date"].dt.to_period("M")
    monthly = data.groupby("month", sort=True).agg(
        market_excess=("market_excess", lambda series: float(np.prod(1.0 + series) - 1.0)),
        realized_variance=("market_excess", lambda series: float(np.square(series).sum())),
        n_days=("market_excess", "size"),
    )
    monthly.index = monthly.index.to_timestamp("M")
    monthly["lagged_realized_variance"] = monthly["realized_variance"].shift(1)
    monthly = monthly.dropna().copy()
    if (monthly["lagged_realized_variance"] <= 0).any():
        raise ValueError("lagged realized variance must be positive")
    return monthly


def make_managed_returns(monthly: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    """Fix the leverage scale using pre-2000 data only, then never re-estimate it."""
    data = monthly.copy()
    data["raw_weight"] = 1.0 / data["lagged_realized_variance"]
    calibration = data.loc[data.index <= CALIBRATION_END]
    if len(calibration) < 120:
        raise ValueError("calibration period has too few months")
    raw_return = calibration["raw_weight"] * calibration["market_excess"]
    scale = float(np.sqrt(calibration["market_excess"].var(ddof=1) / raw_return.var(ddof=1)))
    data["weight"] = scale * data["raw_weight"]
    data["managed_excess"] = data["weight"] * data["market_excess"]
    data["turnover"] = data["weight"].diff().abs().fillna(0.0)
    return data, scale


def _summary(returns: pd.Series) -> dict:
    mean_ci = evaluate.block_bootstrap_mean_ci(returns, n_boot=2000, block=6, seed=0)
    sharpe_ci = evaluate.block_bootstrap_sharpe_ci(returns, n_boot=2000, block=6, seed=0,
                                                   periods_per_year=12)
    return {"n_months": int(len(returns)), "mean_per_month": float(returns.mean()),
            "mean_annualized": float(returns.mean() * 12),
            "sharpe_annualized": evaluate.sharpe(returns, 12),
            "mean_ci_95": list(mean_ci), "sharpe_ci_95": list(sharpe_ci)}


def execute(*, write: bool = False) -> dict:
    """Compute the bounded audit; persist only when a caller explicitly requests it."""
    daily = load_daily_market()
    monthly, scale = make_managed_returns(monthly_market_with_lagged_variance(daily))
    calibration = monthly.loc[monthly.index <= CALIBRATION_END]
    holdout = monthly.loc[monthly.index >= HOLDOUT_START]
    if holdout.empty:
        raise ValueError("no months remain in the sealed post-1999 holdout")
    spanning = evaluate.spanning(holdout["managed_excess"],
                                 holdout[["market_excess"]], hac_lags=3)
    cost_grid = costs.cost_sensitivity(holdout["managed_excess"], holdout["turnover"],
                                       bps_grid=(0, 5, 10, 20), periods_per_year=12)
    results = {
        "case": "volatility-managed-market",
        "source": {
            "paper": "Moreira and Muir (2017), Volatility-Managed Portfolios, DOI 10.1111/jofi.12513",
            "public_input": "Kenneth French daily five-factor archive; Mkt-RF only",
            "input_sha256": _sha256(SOURCE),
            "daily_start": str(daily["date"].iloc[0].date()),
            "daily_end": str(daily["date"].iloc[-1].date()),
        },
        "protocol": {
            "transformation": "monthly market excess return multiplied by c / prior-month realized variance",
            "calibration": "c fixes managed and unmanaged variance using months through 1999-12 only",
            "sealed_holdout": "2000-01 through the final available public-data month",
            "inference": "monthly moving-block bootstrap, 2,000 draws, six-month blocks; HAC(3) spanning",
            "costs": "one-way turnover equals absolute change in the risky-asset weight; 0/5/10/20 bps grid",
        },
        "normalization_scale": scale,
        "calibration": {"managed": _summary(calibration["managed_excess"]),
                        "market": _summary(calibration["market_excess"])},
        "holdout": {"managed": _summary(holdout["managed_excess"]),
                    "market": _summary(holdout["market_excess"]),
                    "spanning_managed_on_market": spanning,
                    "mean_turnover": float(holdout["turnover"].mean()),
                    "cost_sensitivity": cost_grid.reset_index().to_dict(orient="records"),
                    "breakeven_cost_bps": costs.breakeven_cost_bps(
                        float(holdout["managed_excess"].mean()), float(holdout["turnover"].mean()))},
        "protocol_coverage": {
            "complete": False,
            "not_executed": [
                "the paper's other equity factors, currency carry trade, and exact historical data vintages",
                "a byte-for-byte replication of the paper's published sample and normalization choices",
                "Cederburg et al.'s real-time portfolio-combination and certainty-equivalent analysis",
            ],
        },
    }
    if write:
        OUT.write_text(json.dumps(results, indent=2, allow_nan=False) + "\n")
    return results


if __name__ == "__main__":
    result = execute(write=True)
    print(json.dumps(result["holdout"], indent=2))
