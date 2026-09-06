"""Canonical inventory of the evidence cases integrated by Verdict.

The first four cases are the studies from which the reusable validation
patterns were extracted.  Later cases exercise the same contracts without
being allowed to blur that provenance.  Interfaces import this module instead
of maintaining their own case lists.
"""
from __future__ import annotations

from .case_contract import CaseSpec


PYTHON = ("python",)

CASES: tuple[CaseSpec, ...] = (
    CaseSpec(
        "complexity-voc", "complexity", "foundation", "mechanism / counterfactual",
        run_steps=(
            PYTHON + ("cases/complexity/preprocess.py",),
            PYTHON + ("cases/complexity/run_kmz.py",),
            PYTHON + ("cases/complexity/run_nagel.py",),
            PYTHON + ("cases/complexity/phase_diagram.py",),
        ),
        report_steps=(PYTHON + ("cases/complexity/make_figures.py",),),
        result_files=("results/kmz_sweep.parquet", "results/nagel_diagnostics.json",
                      "results/phase_diagram.json"),
        protocol_gaps=("the final narrative report is maintained rather than generated",),
        agent_mode="executable",
    ),
    CaseSpec(
        "buy-the-dip-long-calls", "buy_the_dip", "foundation", "point-in-time / expression",
        run_steps=(PYTHON + ("cases/buy_the_dip/run.py",),),
        report_steps=(PYTHON + ("cases/buy_the_dip/make_figures.py",),
                      PYTHON + ("cases/buy_the_dip/make_report.py",)),
        result_files=("results.json", "results_attribution.parquet", "results_robustness.csv"),
        protocol_gaps=("option-clock recovery needs vendor-platform re-derivation",),
    ),
    CaseSpec(
        "retail-short-volatility", "vol_harvest", "foundation",
        "friction / implementability",
        run_steps=(PYTHON + ("cases/vol_harvest/run.py",),),
        report_steps=(PYTHON + ("cases/vol_harvest/make_figures.py",),
                      PYTHON + ("cases/vol_harvest/make_report.py",)),
        result_files=("results.json",),
        protocol_gaps=("raw real-chain platform logs are unavailable for recomputation",),
    ),
    CaseSpec(
        "gamma-signal-drift", "drift", "foundation", "deployment / distribution shift",
        run_steps=(PYTHON + ("cases/drift/run.py",),),
        report_steps=(PYTHON + ("cases/drift/make_figures.py",),
                      PYTHON + ("cases/drift/make_report.py",)),
        result_files=("results.json", "results_rolling.csv"),
    ),
    CaseSpec(
        "time-series-momentum", "tsmom", "extension", "benchmark / sealed holdout",
        run_steps=(PYTHON + ("cases/tsmom/run.py",),),
        report_steps=(PYTHON + ("cases/tsmom/make_figures.py",),
                      PYTHON + ("cases/tsmom/make_report.py",)),
        result_files=("results.json", "results_series.csv", "results/holdout_ledger.json"),
        protocol_gaps=("integer-contract and multiplier-aware sizing",),
    ),
    CaseSpec("lazy-prices-10k-changes", "lazy_prices", "data-gated", "protocol only"),
)

CASE_BY_ID = {case.card_id: case for case in CASES}
CASE_DIRS = {case.card_id: case.folder for case in CASES}
FOUNDATIONAL_CASES = tuple(case for case in CASES if case.role == "foundation")


def validate_catalog() -> None:
    """Fail if identifiers or folders are duplicated or the foundation drifts."""
    ids = [case.card_id for case in CASES]
    folders = [case.folder for case in CASES]
    if len(ids) != len(set(ids)):
        raise ValueError("case catalog contains duplicate registry ids")
    if len(folders) != len(set(folders)):
        raise ValueError("case catalog contains duplicate folders")
    if len(FOUNDATIONAL_CASES) != 4:
        raise ValueError("Verdict must identify exactly four foundational studies")
    if any(case.agent_mode not in {"executable", "evidence-readonly"} for case in CASES):
        raise ValueError("case catalog contains an invalid agent mode")
    if any(case.role != "data-gated" and not case.result_files for case in CASES):
        raise ValueError("every executable/evidence case must declare result files")


validate_catalog()
