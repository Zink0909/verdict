# Bounded real-time test: volatility-managed and unscaled market

**Verdict:** no clear real-time improvement in the market-only expanding-window
analogue. Registry card:
[`registry/volatility-managed-realtime.json`](../../registry/volatility-managed-realtime.json).

Cederburg et al. (2020) argue that positive in-sample spanning alphas do not
automatically create a real-time investment opportunity. This case tests that
point in a deliberately narrow setting that reuses the public market-only
reconstruction from `../volatility_managed/`.

## Fixed real-time comparison

At each month, all expected-return and covariance estimates use only data
available through the preceding month. The expanded opportunity set can hold
the managed market, unscaled market and cash; the baseline can hold only
unscaled market and cash. Both use risk aversion 5 and a gross leverage cap of
5. There is no full-sample allocation fitted after the fact.

The case reports the return difference, block-bootstrap interval, spanning
alpha, certainty equivalent, and 0/5/10/20 bps costs. The point is not whether
the raw in-sample optimization can construct an attractive mix; it is whether a
real-time rule carries a detectable increment after the inputs are known.

## Reproduce

The paper URL and local-reading-copy fingerprint are in
[`SOURCES.md`](SOURCES.md). The exact public Fama/French input is inherited
from `../volatility_managed/source/ff5_daily.zip`.

```bash
micromamba run -n verdict python cases/volatility_realtime/run.py
micromamba run -n verdict python cases/volatility_realtime/make_report.py
```

## Boundary

This is not Cederburg et al.'s 103-strategy cross-section and does not claim
their exact portfolio-choice robustness grid or historical vintage. It is a
public-data, market-only test of their real-time decision principle.
