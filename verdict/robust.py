"""Robustness: parameter sweeps, membership stability, conclusion stability.

A conclusion that depends on the exact cutoff is not a conclusion, it is a
coincidence. Two kinds of stability are checked separately because they answer
different questions:

* **membership** — how much the *sample* moves when a definitional threshold
  moves (and, crucially, whether a looser threshold admits entities that were
  never actually tested — those may be listed, never concluded about);
* **conclusion** — whether the *sign and substance* of the headline findings
  survive on each perturbed sample.

The same sweep machinery drives multi-axis diagnostic scans (the complexity
case's phase diagram), where the discipline is to report the whole grid rather
than the cell that looks best.

Provenance: buy_the_dip/scripts/robustness_sweep.py, generalized.
"""
from __future__ import annotations

import itertools
from typing import Callable, Iterable

import numpy as np
import pandas as pd


def sweep(grid: dict, fn: Callable[..., dict], progress: bool = False) -> pd.DataFrame:
    """Evaluate `fn(**params)` over the full cartesian product of `grid`.

    Returns one tidy row per cell (parameters plus whatever `fn` returns), so
    the entire surface can be reported rather than a chosen point.
    """
    keys = list(grid)
    rows = []
    combos = list(itertools.product(*(grid[k] for k in keys)))
    for i, values in enumerate(combos, 1):
        params = dict(zip(keys, values))
        if progress:
            print(f"  [{i}/{len(combos)}] {params}", flush=True)
        out = fn(**params)
        rows.append({**params, **out})
    return pd.DataFrame(rows)


def membership_stability(base: Iterable, variant: Iterable) -> dict:
    """How far a perturbed definition moves the sample."""
    b, v = set(base), set(variant)
    union = b | v
    return {"n_base": len(b), "n_variant": len(v),
            "added": sorted(v - b, key=str), "dropped": sorted(b - v, key=str),
            "n_added": len(v - b), "n_dropped": len(b - v),
            "jaccard": (len(b & v) / len(union)) if union else 1.0}


def untested_additions(added: Iterable, tested: Iterable) -> list:
    """Entities a looser threshold admits but that were never backtested.

    They belong in the report as an explicit gap. Quietly treating the base
    conclusion as covering them would be claiming evidence that was never
    gathered.
    """
    tested = set(tested)
    return sorted({a[-1] if isinstance(a, tuple) else a for a in added} - tested, key=str)


def conclusion_stability(results: pd.DataFrame, metrics: list[str],
                         base_label, label_col: str = "label") -> pd.DataFrame:
    """Do the headline metrics keep their sign across perturbed samples?

    Returns the metric table with a `sign_agrees_with_base` column per metric
    and an `all_agree` flag per row. Sign, not magnitude: the claim under test
    is "the finding holds", not "the number is identical".
    """
    if label_col not in results.columns:
        raise ValueError(f"results must carry a '{label_col}' column")
    base_rows = results[results[label_col] == base_label]
    if len(base_rows) != 1:
        raise ValueError(f"expected exactly one base row labelled {base_label!r}")
    base = base_rows.iloc[0]
    out = results.copy()
    agree_cols = []
    for m in metrics:
        col = f"{m}_sign_agrees"
        out[col] = [
            bool(np.sign(v) == np.sign(base[m])) if pd.notna(v) and pd.notna(base[m])
            else False for v in out[m]]
        agree_cols.append(col)
    out["all_agree"] = out[agree_cols].all(axis=1)
    return out
