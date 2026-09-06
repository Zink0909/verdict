# Bounded audit: volatility-managed U.S. market

**Claim audited.** On public Fama/French daily market excess returns, inverse prior-month realized variance scaling adds incremental holdout performance beyond the unscaled market.

**Verdict.** NO CLEAR INCREMENTAL HOLDOUT EVIDENCE. On the sealed 2000+ holdout, managed annualized Sharpe is 0.50 versus 0.48; HAC spanning alpha is +0.16% per month (t=1.21), with 95% interval [-0.10%, +0.42%].

## Protocol fixed before the holdout

The leverage-normalization constant uses only months through 1999-12. All reported comparison statistics use 2000 onward. Returns are the public Mkt-RF series, compounded monthly; realized variance is computed from the preceding month's daily returns.

## Costs

Mean one-way turnover is 0.394 per month; linear breakeven cost is 49.0 bps. The result table records 0/5/10/20 bps sensitivity rather than selecting a convenient friction.

## Evidence boundary

This is a public-data market-only reconstruction. It asks a narrow incremental question and does not claim to reproduce the paper's full nine-factor/currency study or its historical data vintage.

## Honest limitations

- The French data archive's current CRSP vintage is not the paper's original data vintage.
- Only the market transformation is tested; the paper's other factors and currency carry trade are outside this case.
- The scale constant is fixed before the holdout, but the paper's exact normalization and published sample are not replicated byte-for-byte.
- The cost grid is a transparent linear sensitivity, not a broker-level execution simulation.

## What would have changed the verdict

A full paper-level conclusion would require the other source series, the authors' data vintage, and the real-time combination tests emphasized by Cederburg et al. (2020).

## Provenance and reproduction

- SOURCES.md records paper and public-data URLs plus SHA-256.
- Run `python cases/volatility_managed/run.py`, then this script.
