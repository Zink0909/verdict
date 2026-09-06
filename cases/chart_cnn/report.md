# Chart-CNN Stock Selection in a Large-Cap Book

**Claim audited.** A convolutional neural network trained on price-chart images
selects stocks with predictive information incremental to momentum, short-term
reversal, size, value, and volatility in a point-in-time large-cap universe.

**Verdict.** **NEGATIVE in the tested setting.** The 2017-2019 validation block
had factor-spanning alpha of +0.68% per month (t=2.41). Under the unchanged
construction, the once-opened 2020-2024 holdout had alpha of -0.29% per month
(t=-0.62). At 184% monthly turnover, the holdout long-short was negative from
gross returns through the tested 20 bps one-way cost level.

## Scope of this Verdict case

This is a retrospective, source-evidence import from the SequoAlpha
Chart-CNN study. It occupies a different evidence mode from an executable case:
Verdict fingerprints the source report and the original split/evaluation/regression
code, exposes the reported figures through the same case contract, and labels
the Agent provider as read-only evidence replay. It does not rerun the original
CNN or re-create its data.

The distinction matters. A source report is evidence of what the original
project concluded; it is not a substitute for the original point-in-time data,
model outputs, or an independently executed computation.

## Evidence imported

| Block | Spanning alpha | t-statistic | Cost result |
|---|---:|---:|---|
| Validation, 2017-2019 | +0.68% per month | +2.41 | Long-short annualized Sharpe: 1.10 gross, 0.53 at 10 bps one-way, approximately zero at 20 bps |
| Sealed holdout, 2020-2024 | -0.29% per month | -0.62 | Long-short annualized Sharpe: -0.23 gross, -0.80 at 20 bps one-way |

The source report attributes the validation result to early-stopping optimism
and a favourable short sample. The holdout reverses both the sign and the
significance under the same construction. That is exactly the kind of false
positive an untouched time block is intended to expose.

The factor comparison is the central test, not the gross Sharpe: a signal that
does not survive momentum, short-term reversal, size, value, and volatility is
not incremental information for the book. High turnover then makes the weaker
economic conclusion more restrictive, rather than rescuing it.

## How it contributes to the shared framework

- `verdict.splits`: chronological train/validation/holdout partitioning and
  an explicit once-opened-holdout concept.
- `verdict.evaluate`: HAC factor-spanning regression and block-bootstrap
  performance intervals.
- `verdict.costs`: turnover identity and one-way transaction-cost sensitivity.
- `verdict.diagnose`: the validation-positive / holdout-null false-positive
  playbook.

## Honest limitations

- This is a source-evidence retrofit. Raw point-in-time QuantConnect data,
  trained-model outputs, and portfolio return files are not available in this
  repository, so no fresh numerical recomputation is claimed.
- The original holdout opening predates Verdict's machine-readable ledger. The
  source report says it was opened once; Verdict preserves that provenance but
  cannot recast it as a newly enforced physical seal.
- The result concerns a value-weighted, large-cap, monthly implementation. It
  does not refute the paper's broader weekly/equal-weighted settings.
- The source uses a simple one-way-cost sensitivity. It is not a complete
  execution, liquidity, or market-impact study.

## Provenance and reproduction

- Source report: `/Users/mmmm/projects/SequoAlpha/chart_cnn/reports/cnn_report.md`,
  SHA-256 `30391f48f6f95d862f0e4babb781ffdf88d52e58e243ee1af763c27829d9430e`.
- Source known-answer suite: `/Users/mmmm/projects/SequoAlpha/chart_cnn/scripts/regress.py`,
  SHA-256 `99e05288ceb659fc007875b8a3f4ac0e6b7ff53393a796dc65d6e7964bbc9f21`.
- The source regression suite was rerun during this integration audit and
  passed 6/6 offline checks. Its command is recorded in `README.md`.
- `results.json` stores the full source-artifact fingerprint list and the
  imported numerical evidence.
