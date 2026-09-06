# Bounded audit: volatility-managed U.S. market

**Verdict:** no clear incremental holdout evidence in the public-data,
market-only reconstruction. Registry card:
[`registry/volatility-managed-market.json`](../../registry/volatility-managed-market.json).

Moreira and Muir (2017) argue that scaling returns by inverse prior-month
realized variance materially improves portfolio performance. This case does not
claim a byte-for-byte reproduction. It asks the narrower question that public
daily Fama/French data can answer honestly: after fixing the normalization
before January 2000, does the managed market have incremental post-2000 return
beyond the unscaled market?

## Protocol

- **Input:** daily public `Mkt-RF`, compounded to monthly excess returns.
- **Signal:** previous calendar month's sum of squared daily excess returns.
- **Managed return:** current market excess return multiplied by `c / lagged RV`.
- **Calibration:** `c` is selected only through December 1999 to equalize
  managed and unmanaged calibration variance.
- **Sealed evaluation:** January 2000 through the last downloadable month.
- **Tests:** moving-block bootstrap intervals, HAC(3) spanning on unscaled
  market, and a 0/5/10/20 bps turnover-cost grid.

The result deliberately separates an improved standalone Sharpe from an
incremental spanning alpha: the former does not alone establish a new source of
performance.

## Reproduce

The pinned public French archive is in `source/ff5_daily.zip`; URLs and hashes
are in [`SOURCES.md`](SOURCES.md).

```bash
micromamba run -n verdict python cases/volatility_managed/run.py
micromamba run -n verdict python cases/volatility_managed/make_report.py
```

## Boundary

This is not the paper's complete nine-factor / currency-carry study, and it is
not a reimplementation of the real-time portfolio-combination tests in
Cederburg et al. (2020). `results.json` records those unexecuted clauses rather
than presenting a market-only outcome as a full-paper verdict.
