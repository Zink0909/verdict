# Case: A Live Signal That Decayed

**Verdict: decayed, detectable 2.8 years early, and not explained by the obvious cause.**
Full write-up: [`report.html`](report.html). Registry card:
[`../../registry/gamma-signal-drift.json`](../../registry/gamma-signal-drift.json).

The only case in the library whose subject is a *deployed feature* rather than a
backtest, and the only one where the framework re-derives the original study's results
exactly rather than partially.

## What is audited

A dealer-gamma reading used to predict whether an intraday trading rule — from a separate
intraday-momentum study — would win or lose on a given day. 700 traded days, 2014–2026.
The "model" is a one-line rule on purpose: the case is about noticing that a deployed
predictor has stopped working, not about building a better one.

## Pipeline

```
run.py            builds the prediction stream, runs the drift monitor, checks the
                  re-derivation against the original study's saved series, decomposes
                  by phase on two instruments, and runs the attribution split test
make_figures.py   three figures from results.json
make_report.py    the verdict document and the registry card
```

Reproduce (data pinned in `data/`, offline, CPU, seconds):

```bash
micromamba run -n verdict python cases/drift/run.py
micromamba run -n verdict python cases/drift/make_figures.py
micromamba run -n verdict python cases/drift/make_report.py
```

## Headline numbers

| | |
|---|---|
| Re-derivation | matches the original study on **551/551** windows, corr **1.000000**, max abs diff 1.7e-16 |
| Discrimination | baseline AUC **0.597** → trough **0.442** (below chance, 2023-05) → recovery **0.548** |
| Detection | CUSUM alarm **2020-07-30**, **1,028 days (2.8 years)** before the trough |
| Phases | win-rate gap **+12pp → −15pp → +11pp** |
| Replication | second instrument, same signs: **+5pp → −6pp → +29pp** |
| Attribution | full-sample Spearman **−0.72**, flips to **+0.76** after 2022 → coincides, does not explain |

## Why the attribution matters more than the decay

The decay is easy to see once plotted. The temptation is the explanation: the same-day-expiry
options boom correlates with it at −0.72, which is the kind of number that ends an
investigation. It does not survive a split — the erosion began when adoption was at 19%,
and discrimination recovered while adoption kept climbing to 55%. Eliminating a plausible
cause without being able to name the true one is the honest outcome, and the framework's
split test is what makes it statable rather than merely suspected.
