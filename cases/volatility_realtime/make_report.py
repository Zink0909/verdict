"""Render the Cederburg-inspired real-time result from computed artifacts."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from verdict.report import VerdictReport  # noqa: E402

CASE = Path(__file__).resolve().parent


def execute() -> Path:
    result = json.loads((CASE / "results.json").read_text())
    evaluation = result["evaluation"]
    combo, base = evaluation["combined"], evaluation["baseline"]
    diff = evaluation["difference"]
    outcome = ("NO CLEAR REAL-TIME IMPROVEMENT" if diff["mean_ci_95"][0] <= 0 <= diff["mean_ci_95"][1]
               else "REAL-TIME DIFFERENCE DETECTED")
    report = VerdictReport(
        title="Bounded real-time test: volatility-managed and unscaled market",
        claim=("A real-time investor who can allocate between the volatility-managed market, "
               "the unscaled market, and cash improves on a matched investor limited to market and cash."),
        verdict=(f"{outcome}. The expanding-window combination has annualized Sharpe "
                 f"{combo['sharpe_annualized']:.2f} versus {base['sharpe_annualized']:.2f} for the "
                 f"matched baseline; its annualized mean increment is {diff['mean_annualized']:+.2%}, "
                 f"with 95% block-bootstrap interval [{diff['mean_ci_95'][0] * 12:+.2%}, "
                 f"{diff['mean_ci_95'][1] * 12:+.2%}]."),
        sections=[
            ("Real-time decision rule", "At each month t, weights use only an expanding history ending "
             "at t-1. Both strategies use risk aversion 5 and a gross leverage cap of 5; the only "
             "difference is whether the managed return is available as an extra asset."),
            ("Costs", f"Mean one-way turnover is {evaluation['mean_combined_turnover']:.3f} for the "
             f"combination and {evaluation['mean_baseline_turnover']:.3f} for the baseline. The "
             "result artifact preserves the 0/5/10/20 bps certainty-equivalent and Sharpe grid."),
            ("Evidence boundary", "This is a transparent expanding-window market-only analogue. It "
             "tests the paper's real-time concern, but it does not reproduce its 103-strategy study "
             "or every portfolio-choice robustness setting."),
        ],
        honest_limitations=[
            "The current public French archive is not the paper's historical data vintage.",
            "Only a market-only combination is evaluated, not the paper's 103-strategy cross-section.",
            "The expanding-window and leverage rule is a declared analogue, not a byte-for-byte implementation of every paper setting.",
            "Cash is represented as zero excess return and costs use a linear turnover sensitivity.",
        ],
        what_would_have_changed=("A full confirmation or rejection of Cederburg et al. requires their "
                                 "factor inputs, exact portfolio-choice grid, and historical-data vintage."),
        provenance=["SOURCES.md records the source paper and parent public-data provenance.",
                    "Run `python cases/volatility_realtime/run.py`, then this script."],
    )
    return report.write(CASE / "report.md")


if __name__ == "__main__":
    print(execute())
