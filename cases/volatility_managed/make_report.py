"""Render the bounded volatility-managed market audit from computed results only."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
import sys
sys.path.insert(0, str(ROOT))

from verdict.report import VerdictReport  # noqa: E402

CASE = Path(__file__).resolve().parent


def pct(value: float) -> str:
    return f"{value * 100:+.2f}%"


def execute() -> Path:
    results = json.loads((CASE / "results.json").read_text())
    holdout = results["holdout"]
    managed, market = holdout["managed"], holdout["market"]
    span = holdout["spanning_managed_on_market"]
    alpha = span["alpha"]
    outcome = ("INCREMENTAL HOLDOUT EVIDENCE" if span["alpha_ci"][0] > 0
               else "NO CLEAR INCREMENTAL HOLDOUT EVIDENCE")
    report = VerdictReport(
        title="Bounded audit: volatility-managed U.S. market",
        claim=("On public Fama/French daily market excess returns, inverse prior-month realized "
               "variance scaling adds incremental holdout performance beyond the unscaled market."),
        verdict=(f"{outcome}. On the sealed 2000+ holdout, managed annualized Sharpe is "
                 f"{managed['sharpe_annualized']:.2f} versus {market['sharpe_annualized']:.2f}; "
                 f"HAC spanning alpha is {pct(alpha)} per month (t={span['alpha_t']:.2f}), "
                 f"with 95% interval [{pct(span['alpha_ci'][0])}, {pct(span['alpha_ci'][1])}]."),
        sections=[
            ("Protocol fixed before the holdout", "The leverage-normalization constant uses only "
             "months through 1999-12. All reported comparison statistics use 2000 onward. "
             "Returns are the public Mkt-RF series, compounded monthly; realized variance is "
             "computed from the preceding month's daily returns."),
            ("Costs", f"Mean one-way turnover is {holdout['mean_turnover']:.3f} per month; "
             f"linear breakeven cost is {holdout['breakeven_cost_bps']:.1f} bps. The result table "
             "records 0/5/10/20 bps sensitivity rather than selecting a convenient friction."),
            ("Evidence boundary", "This is a public-data market-only reconstruction. It asks a "
             "narrow incremental question and does not claim to reproduce the paper's full "
             "nine-factor/currency study or its historical data vintage."),
        ],
        honest_limitations=[
            "The French data archive's current CRSP vintage is not the paper's original data vintage.",
            "Only the market transformation is tested; the paper's other factors and currency carry trade are outside this case.",
            "The scale constant is fixed before the holdout, but the paper's exact normalization and published sample are not replicated byte-for-byte.",
            "The cost grid is a transparent linear sensitivity, not a broker-level execution simulation.",
        ],
        what_would_have_changed=("A full paper-level conclusion would require the other source "
                                 "series, the authors' data vintage, and the real-time "
                                 "combination tests emphasized by Cederburg et al. (2020)."),
        provenance=["SOURCES.md records paper and public-data URLs plus SHA-256.",
                    "Run `python cases/volatility_managed/run.py`, then this script."],
    )
    return report.write(CASE / "report.md")


if __name__ == "__main__":
    print(execute())
