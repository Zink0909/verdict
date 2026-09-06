# Bounded real-time test: volatility-managed and unscaled market

**Claim audited.** A real-time investor who can allocate between the volatility-managed market, the unscaled market, and cash improves on a matched investor limited to market and cash.

**Verdict.** NO CLEAR REAL-TIME IMPROVEMENT. The expanding-window combination has annualized Sharpe 0.50 versus 0.45 for the matched baseline; its annualized mean increment is +0.09%, with 95% block-bootstrap interval [-1.75%, +2.13%].

## Real-time decision rule

At each month t, weights use only an expanding history ending at t-1. Both strategies use risk aversion 5 and a gross leverage cap of 5; the only difference is whether the managed return is available as an extra asset.

## Costs

Mean one-way turnover is 0.199 for the combination and 0.006 for the baseline. The result artifact preserves the 0/5/10/20 bps certainty-equivalent and Sharpe grid.

## Evidence boundary

This is a transparent expanding-window market-only analogue. It tests the paper's real-time concern, but it does not reproduce its 103-strategy study or every portfolio-choice robustness setting.

## Honest limitations

- The current public French archive is not the paper's historical data vintage.
- Only a market-only combination is evaluated, not the paper's 103-strategy cross-section.
- The expanding-window and leverage rule is a declared analogue, not a byte-for-byte implementation of every paper setting.
- Cash is represented as zero excess return and costs use a linear turnover sensitivity.

## What would have changed the verdict

A full confirmation or rejection of Cederburg et al. requires their factor inputs, exact portfolio-choice grid, and historical-data vintage.

## Provenance and reproduction

- SOURCES.md records the source paper and parent public-data provenance.
- Run `python cases/volatility_realtime/run.py`, then this script.
