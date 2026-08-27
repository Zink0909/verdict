"""Point-in-time universe construction and independent leakage audits.

Two ideas, kept separate on purpose:

* **Construction** — screens that see only what was disclosed by a given date,
  and that judge *persistence* rather than a single good year. A screen that can
  be satisfied by one strong year is a screen that hindsight can walk through.
* **Audit** — checks that re-derive timestamps and membership from raw inputs
  and never import the construction code. A pipeline vouching for itself proves
  nothing; the audit exists to disagree with it.

Provenance: buy_the_dip/buythedip/moat.py (persistence screen, as-of universe)
and chart_cnn/chartcnn/audit.py (timing and membership audits).
"""
from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------
# construction
# --------------------------------------------------------------------------

def sustained_above(history, threshold: float, window: int = 8,
                    consistency: float = 0.70) -> bool:
    """Was a quantity above `threshold` in at least `consistency` of `window` periods?

    Consistency rather than every-period: durable advantage is not the same as
    never having a bad year, and an every-year rule quietly excludes textbook
    cases because of one recession. Returns False when history is shorter than
    the window — early history is not guessed at.
    """
    s = pd.Series(history).dropna()
    if len(s) < window:
        return False
    recent = s.iloc[-window:]
    return bool((recent >= threshold).mean() >= consistency)


def stable_series(history, window: int = 8, max_cv: float = 0.15) -> bool:
    """Is a quantity stable (coefficient of variation <= max_cv) over the window?

    Stability, not level: the absolute level of a margin varies enormously by
    industry, while its steadiness is the signal that pricing power is real.
    """
    s = pd.Series(history).dropna()
    if len(s) < window:
        return False
    recent = s.iloc[-window:]
    m = recent.mean()
    return bool(m > 0 and (recent.std(ddof=0) / m) <= max_cv)


def persistent_quality(level_history, stability_history, level_min: float = 0.15,
                       window: int = 8, consistency: float = 0.70,
                       max_cv: float = 0.15) -> bool:
    """Persistence screen: a sustained level plus a stable companion series.

    The fixed threshold is a deliberate defence against hindsight: every knob
    that can be tuned is a place where knowledge of the outcome leaks back into
    the universe definition.
    """
    return (sustained_above(level_history, level_min, window, consistency)
            and stable_series(stability_history, window, max_cv))


def universe_asof(panel: pd.DataFrame, asof, screen: Callable[[pd.DataFrame], bool],
                  entity_col: str = "ticker", disclosure_col: str = "asof",
                  order_col: str | None = None) -> list[str]:
    """Entities passing `screen` using only records disclosed on or before `asof`.

    `panel` is a long table of fundamentals with a disclosure date per row. The
    filter is on the disclosure date, never the fiscal period: a fiscal year
    that had not yet been reported cannot inform a decision made at `asof`.
    """
    asof = pd.Timestamp(asof)
    known = panel[pd.to_datetime(panel[disclosure_col]) <= asof]
    out = []
    for entity, g in known.groupby(entity_col):
        if order_col is not None:
            g = g.sort_values(order_col)
        if screen(g):
            out.append(entity)
    return sorted(out)


# --------------------------------------------------------------------------
# audits — deliberately independent of the construction code above
# --------------------------------------------------------------------------

def audit_signal_timing(panel: pd.DataFrame, feature_col: str = "feature_asof",
                        label_col: str = "label_start") -> list[str]:
    """Every record's label must begin strictly after its last input timestamp."""
    problems = []
    fa = pd.to_datetime(panel[feature_col])
    ls = pd.to_datetime(panel[label_col])
    bad = int((ls <= fa).sum())
    if bad:
        problems.append(f"{bad} record(s) with label_start <= feature_asof "
                        "(future information used as an input)")
    return problems


def audit_universe_membership(holdings: pd.DataFrame, membership: pd.DataFrame,
                              date_col: str = "date", entity_col: str = "ticker",
                              freq: str = "M") -> list[str]:
    """Every held name must have been in the universe in the period it was held."""
    valid = set(zip(pd.to_datetime(membership[date_col]).dt.to_period(freq),
                    membership[entity_col]))
    periods = pd.to_datetime(holdings[date_col]).dt.to_period(freq)
    bad = sum(1 for p, e in zip(periods, holdings[entity_col]) if (p, e) not in valid)
    return [f"{bad} (period, entity) holding(s) outside the point-in-time universe "
            "(survivorship or future membership leaked in)"] if bad else []


def audit_disclosure_lag(panel: pd.DataFrame, period_end_col: str = "period_end",
                         disclosure_col: str = "asof", min_days: int = 0) -> list[str]:
    """Fundamentals must not be usable before they could have been published."""
    pe = pd.to_datetime(panel[period_end_col])
    dis = pd.to_datetime(panel[disclosure_col])
    lag = (dis - pe).dt.days
    bad = int((lag < min_days).sum())
    return [f"{bad} record(s) disclosed less than {min_days} day(s) after period end "
            "(implausible reporting lag — check for restated or back-filled data)"] \
        if bad else []


def audit_no_future_rows(panel: pd.DataFrame, asof, date_col: str = "asof") -> list[str]:
    """No record used in an as-of decision may carry a later timestamp."""
    asof = pd.Timestamp(asof)
    bad = int((pd.to_datetime(panel[date_col]) > asof).sum())
    return [f"{bad} record(s) dated after the as-of date {asof.date()}"] if bad else []
