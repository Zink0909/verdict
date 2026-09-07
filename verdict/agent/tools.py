"""The A layer, exposed as tools — the only source of numbers in the system.

Every quantity that can reach a verdict enters through this module, computed by
the deterministic framework. The model chooses which tool to call and with what
arguments; it never supplies a result. That division is what makes the agent
layer auditable: the transcript records each call and each returned value, and
`guardrails.audit_numbers` later checks the written verdict against exactly
these numbers.

Tool definitions are strict (`additionalProperties: false`, everything
required), so an argument the model invents is rejected by the API rather than
silently defaulted.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd

from .. import diagnose as D
from .. import evaluate as E
from .. import features as F
from .. import synthetic as S

CASE_DATA = Path(__file__).resolve().parents[2] / "cases" / "complexity" / "data" / "processed.parquet"
GAMMA = 2.0
_CACHE: dict[str, tuple] = {}
_REAL_STRATEGY_CACHE: dict[tuple[int, int, float, int], tuple[np.ndarray, np.ndarray]] = {}


def _load() -> tuple[np.ndarray, np.ndarray, pd.Index]:
    if "panel" not in _CACHE:
        proc = pd.read_parquet(CASE_DATA)
        _CACHE["panel"] = (proc.drop(columns=["R"]).to_numpy(float),
                           proc["R"].to_numpy(float), proc.index)
    return _CACHE["panel"]


def _strategy(X, R, P: int, T: int, z: float, seeds: int):
    """Ensemble the timing strategy over RFF seeds; return returns and forecast."""
    total = None
    for s in range(seeds):
        Phi = F.rff(X, P, gamma=GAMMA, seed=s)
        fc = F.rolling_forecasts(Phi, R, T, [z])[0]
        total = fc if total is None else total + fc
    fc = total / seeds
    return fc * R, fc


def _real_strategy(P: int, T: int, z: float, seeds: int):
    """Reuse an identical real-data fit across tools in one process."""
    key = (P, T, float(z), seeds)
    if key not in _REAL_STRATEGY_CACHE:
        X, R, _ = _load()
        _REAL_STRATEGY_CACHE[key] = _strategy(X, R, P, T, z, seeds)
    return _REAL_STRATEGY_CACHE[key]


# --------------------------------------------------------------- the tools ----

def describe_dataset() -> dict:
    """What is actually in the pinned panel."""
    X, R, idx = _load()
    return {"observations": int(len(R)), "predictors": int(X.shape[1]),
            "start": str(idx[0]), "end": str(idx[-1]),
            "target": "standardized excess market return, next period",
            "note": "predictors are standardized with backward-looking windows only"}


def run_complex_model(n_features: int, window: int, shrinkage: float, seeds: int = 3) -> dict:
    """Fit the over-parameterized model in rolling windows and time the market with it."""
    X, R, _ = _load()
    strat, fc = _real_strategy(n_features, window, shrinkage, seeds)
    m = ~np.isnan(strat)
    return {"n_features": n_features, "window": window, "shrinkage": shrinkage, "seeds": seeds,
            "sharpe_annualized": round(E.sharpe(pd.Series(strat[m])), 4),
            "oos_r2": round(E.oos_r2(R[m], fc[m], benchmark=np.zeros(m.sum())), 4),
            "n_out_of_sample": int(m.sum())}


def kernel_equivalence_check(window: int, n_features: int = 2000, seeds: int = 2) -> dict:
    """Test whether the complex model is a kernel smoother, and read off its weights."""
    X, R, _ = _load()
    ker = D.kernel_ridgeless_forecast(X, R, T=window, gamma=GAMMA)
    strat_k = ker["forecast"] * R
    strat_m, fc_m = _real_strategy(n_features, window, 1e-3, seeds)
    m = ~np.isnan(fc_m) & ~np.isnan(ker["forecast"])
    span = E.spanning(pd.Series(strat_m[m]), pd.DataFrame({"kernel": strat_k[m]}))
    return {"window": window, "n_features_compared": n_features,
            "forecast_correlation": round(float(np.corrcoef(fc_m[m], ker["forecast"][m])[0, 1]), 4),
            "kernel_spans_r2": round(span["r2"], 4),
            "residual_alpha_t": round(span["alpha_t"], 4),
            "weight_recency_correlation": round(ker["recency_corr"], 4),
            "scale_vs_predictor_volatility": round(ker["scale_vs_predvol"], 4),
            "reading": "recency correlation > 0 means the weights are momentum; a negative "
                       "scale-vs-volatility correlation means volatility timing"}


def counterfactual_world(kind: str, n_features: int, window: int, draws: int = 4,
                         seeds: int = 2) -> dict:
    """Re-run the whole pipeline on data where the answer should change, or should not.

    'reversal' injects negative autocorrelation into the returns: a model that
    learned momentum from the data should stop building it. 'destroy_information'
    destroys the predictors' predictive content while keeping their persistence
    and heteroskedasticity: a model using that information should collapse.
    """
    X, R, _ = _load()
    base, _ = _real_strategy(n_features, window, 1e-3, seeds)
    bm = ~np.isnan(base)
    out = []
    for d in range(draws):
        if kind == "reversal":
            strat, _ = _strategy(X, S.reversal_world(R, seed=d), n_features, window, 1e-3, seeds)
        elif kind == "destroy_information":
            strat, _ = _strategy(S.wild_bootstrap_predictors(X, seed=d), R,
                                 n_features, window, 1e-3, seeds)
        else:
            raise ValueError("kind must be 'reversal' or 'destroy_information'")
        mm = ~np.isnan(strat)
        out.append(E.sharpe(pd.Series(strat[mm])))
    return {"kind": kind, "n_features": n_features, "window": window, "draws": draws,
            "sharpe_real_data": round(E.sharpe(pd.Series(base[bm])), 4),
            "sharpe_counterfactual_mean": round(float(np.mean(out)), 4),
            "sharpe_counterfactual_draws": [round(x, 4) for x in out],
            "share_negative": round(float(np.mean(np.array(out) < 0)), 4)}


def forecast_comparison_test(n_features: int, window: int, seeds: int = 2) -> dict:
    """Formal test of whether the complex forecast beats the no-predictability benchmark."""
    X, R, _ = _load()
    _, fc = _real_strategy(n_features, window, 1e-3, seeds)
    m = ~np.isnan(fc)
    cw = E.clark_west(R[m], np.zeros(m.sum()), fc[m])
    return {"n_features": n_features, "window": window,
            "clark_west_t": round(cw["cw_t"], 4),
            "rejects_equal_accuracy_5pct": bool(cw["reject_5pct"]),
            "reading": "a t below 1.645 means the complex forecast does not beat the "
                       "benchmark by a formal test, whatever the strategy's Sharpe"}


# ------------------------------------------------------------- definitions ----

def _tool(name: str, description: str, props: dict, required: list[str]) -> dict:
    return {"name": name, "description": description, "strict": True,
            "input_schema": {"type": "object", "properties": props,
                             "required": required, "additionalProperties": False}}


_INT = {"type": "integer"}
_NUM = {"type": "number"}

REGISTRY: dict[str, tuple[dict, Callable]] = {
    "describe_dataset": (
        _tool("describe_dataset",
              "Report what is in the pinned dataset: number of observations, number of "
              "predictors, date range, and what the target variable is. Call this first.",
              {}, []),
        describe_dataset),
    "run_complex_model": (
        _tool("run_complex_model",
              "Fit the over-parameterized random-feature model in rolling windows and time "
              "the market with its forecast. Returns the annualized Sharpe ratio and the "
              "out-of-sample R-squared. Use this to reproduce the claimed effect and to "
              "trace how it varies with complexity.",
              {"n_features": {**_INT, "description": "Number of random features, 2 to 12000"},
               "window": {**_INT, "description": "Rolling training window in months"},
               "shrinkage": {**_NUM, "description": "Ridge penalty; 0 is the ridgeless limit"},
               "seeds": {**_INT, "description": "Random-feature draws to average over"}},
              ["n_features", "window", "shrinkage", "seeds"]),
        run_complex_model),
    "kernel_equivalence_check": (
        _tool("kernel_equivalence_check",
              "Test whether the complex model is numerically a kernel smoother, and read off "
              "the weights it places on past returns. Reports the correlation between the two "
              "forecasts, how much of the strategy the kernel spans, the residual alpha "
              "t-statistic, and whether the weights look like momentum and volatility timing.",
              {"window": _INT,
               "n_features": {**_INT, "description": "Feature count for the comparison"},
               "seeds": _INT},
              ["window", "n_features", "seeds"]),
        kernel_equivalence_check),
    "counterfactual_world": (
        _tool("counterfactual_world",
              "Re-run the pipeline on altered data. 'reversal' injects negative "
              "autocorrelation into returns, so a model that learned from the data should "
              "change behaviour. 'destroy_information' destroys the predictors' predictive "
              "content while keeping their persistence, so a model using that information "
              "should collapse. Unchanged performance is evidence the result is mechanical.",
              {"kind": {"type": "string", "enum": ["reversal", "destroy_information"]},
               "n_features": _INT, "window": _INT, "draws": _INT, "seeds": _INT},
              ["kind", "n_features", "window", "draws", "seeds"]),
        counterfactual_world),
    "forecast_comparison_test": (
        _tool("forecast_comparison_test",
              "Run the Clark-West test of whether the complex forecast is more accurate than "
              "the nested no-predictability benchmark. A strategy can have a positive Sharpe "
              "while its forecasts fail this test.",
              {"n_features": _INT, "window": _INT, "seeds": _INT},
              ["n_features", "window", "seeds"]),
        forecast_comparison_test),
}


def definitions() -> list[dict]:
    return [d for d, _ in REGISTRY.values()]


def run_tool(name: str, arguments: dict) -> dict:
    """Execute one tool. Unknown names and bad arguments raise rather than default."""
    if name not in REGISTRY:
        raise KeyError(f"unknown tool {name!r}; available: {', '.join(REGISTRY)}")
    definition, fn = REGISTRY[name]
    allowed = set(definition["input_schema"]["properties"])
    unknown = set(arguments) - allowed
    if unknown:
        raise TypeError(f"{name} got unexpected argument(s): {', '.join(sorted(unknown))}")
    return fn(**arguments)


def collect_numbers(results: list[dict]) -> list[float]:
    """Every numeric value the tools returned — the allow-list for the number audit."""
    out: list[float] = []

    def walk(v):
        if isinstance(v, bool):
            return
        if isinstance(v, (int, float)):
            out.append(float(v))
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, (list, tuple)):
            for x in v:
                walk(x)

    walk(results)
    return out
