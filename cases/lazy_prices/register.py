#!/usr/bin/env python3
"""Register a claim that cannot be adjudicated here — the honest third state.

Not every claim can be settled by the person who wants to settle it. This one is
testable in principle and gated in practice: the protocol below is complete, and
executing it needs a corpus of thirty years of regulatory filings that has not
been built.

The registry has a state for exactly this. Recording the claim and its
pre-registered protocol, and stopping, is a more useful artefact than either
silence or a verdict reached on data that was never assembled — it says what
would settle the question and what it would cost, so the next person starts from
a protocol rather than from scratch.

    micromamba run -n verdict python cases/lazy_prices/register.py
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from verdict.report import write_card   # noqa: E402

CARD = {
    "id": "lazy-prices-10k-changes",
    "title": "Changes in corporate filing language",
    "state": "protocol-ready-data-gated",
    "claim": {
        "signal": "year-over-year textual similarity between a firm's consecutive annual and "
                  "quarterly reports; long the firms that barely changed their language, "
                  "short the firms that changed it most",
        "universe": "US listed firms with regulatory filings; the practical variant is a "
                    "large-cap index universe",
        "frequency": "quarterly signal, monthly rebalanced overlapping portfolios held 3 months",
        "claimed_effect": "firms that materially change their filing language underperform "
                          "firms that do not, by 34-58 basis points per month (t around 3.6) "
                          "with factor-adjusted alphas of 18-45 basis points, concentrated in "
                          "the risk-factor and management-discussion sections",
        "sample": "1995-2014, the window the source paper tested",
        "source": "Cohen, Malloy and Nguyen (2020), 'Lazy Prices', Journal of Finance",
        "data_needs": [
            "full text of every 10-K and 10-Q for the universe, 1994 onward, with the "
            "filing timestamp that defines when the information became public",
            "a point-in-time mapping from filing entity to tradable security",
            "monthly returns and market capitalizations on the same point-in-time universe",
        ],
    },
    "protocol": {
        "replication_anchor": "reproduce the reported quintile spread and its concentration in "
                              "the risk-factor and management-discussion sections on the "
                              "source paper's own window before testing anything else",
        "splits": "the source window is the anchor; 2015 onward is untouched out-of-sample, "
                  "never used for any choice made during replication",
        "benchmarks": "standard factor exposures, and the published decay baseline for "
                      "post-publication anomaly returns",
        "cost_model": "value-weighted returns net of one-way costs swept at 5, 10 and 20 basis "
                      "points; short-leg borrow costs reported separately",
        "kill_criteria_for_the_claim": "if the value-weighted, net-of-cost long-short spread "
                                       "over 2015-2026 has a confidence interval containing "
                                       "zero, and a semantic similarity measure adds no "
                                       "significant increment over the lexical one, the claim "
                                       "is recorded as decayed for this universe",
        "diagnostics": [
            "decay decomposition: is any fall in returns crowding, or faster incorporation? "
            "the shape of the post-filing drift curve separates them",
            "boilerplate quadrant: high lexical change with low semantic change identifies "
            "cosmetic edits that a word-level measure counts as real",
            "section-level attribution rather than whole-document similarity",
        ],
        "timing_discipline": "the signal timestamp is the filing timestamp; positions open on "
                             "the second trading day after filing; restated documents are never "
                             "substituted for the original",
        "preregistered": True,
    },
    "verdict": None,
    "why_not_adjudicated": {
        "blocker": "the corpus has not been built",
        "detail": "executing this protocol needs roughly 60,000-70,000 filings for a large-cap "
                  "universe over three decades, parsed into sections across several eras of "
                  "filing format, plus a point-in-time entity-to-security mapping. The source "
                  "data is public and free; the work is corpus engineering, not access.",
        "what_would_change_it": "a built and audited corpus with per-section parse-success "
                                "rates reported by era, which is the point at which this card "
                                "moves to in-progress",
    },
    "date": "2026-08-27",
}


if __name__ == "__main__":
    path = write_card(CARD, ROOT / "registry")
    print(f"registered {path.name} as protocol-ready-data-gated")
    print("no verdict is issued: the claim is testable in principle and gated in practice")
