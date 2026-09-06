# Claim Registry

Every audited predictive claim leaves a verdict card here. Over time the registry
becomes a living record of which published claims survive independent scrutiny —
a continuously-run version of the "does academic research destroy predictability"
question.

## Card states

- `verdict-delivered` — audited end-to-end, verdict + honest limitations issued
- `protocol-ready-data-gated` — claim extracted, pre-registered protocol designed,
  but the data to execute it is not (yet) available; the honest "not adjudicable
  here" state
- `in-progress`

## Cards

| id | claim | source | state | verdict |
|----|-------|--------|-------|---------|
| buy-the-dip-long-calls | dips in high-quality names can be bought profitably, with a long call as the defined-risk expression | practitioner thesis (no published paper) | verdict-delivered | NEGATIVE on the expression, not on the thesis — the long call loses $263 mean / $2,428 median per trade (win 0.36) while the same dips in the underlying are ro… |
| chart-cnn-spanning | the chart-CNN delivers positive, cost-robust incremental return beyond the book's existing factors | Jiang, Kelly and Xiu (2023) chart-image CNN claim, tested in a SequoAlpha large-cap implementation | verdict-delivered | NEGATIVE in the tested large-cap monthly setting — validation spanning alpha of +0.68% per month (t=2.41) became -0.29% (t=-0.62) on the once-opened 2020-2024 … |
| complexity-voc | out-of-sample market-timing Sharpe rises with model complexity (P), positive even in T=12 rolling windows with ridgeless regression | Kelly, Malamud, Zhou (2024), 'The Virtue of Complexity in Return Prediction', Journal of Finance | verdict-delivered | MECHANICAL ARTIFACT — Nagel confirmed |
| gamma-signal-drift | the gamma reading discriminates winning from losing days | deployed feature from a separate intraday-momentum study | verdict-delivered | DECAYED AND PARTLY RECOVERED — discrimination 0.597 baseline -> 0.442 trough (below chance) -> 0.548; detectable 2.8 years before the trough; the obvious cause… |
| lazy-prices-10k-changes | firms that materially change their filing language underperform firms that do not, by 34-58 basis points per month (t around 3.6) with factor-adjusted alphas o… | Cohen, Malloy and Nguyen (2020), 'Lazy Prices', Journal of Finance | protocol-ready-data-gated | not adjudicable with available data |
| retail-short-volatility | a real and persistent volatility risk premium can be harvested at retail scale with capped-loss structures | practitioner thesis (no published paper) | verdict-delivered | FALSIFIED — true premise, unreachable conclusion. Real chains with conservative fills: -43.9% net (-6.75% CAGR) on the model's own pick, -14.5% on the earlier … |
| time-series-momentum | A diversified time-series momentum portfolio earns large abnormal returns: a Sharpe ratio around 1.2 for the diversified 12-month strategy, positive predictabi… | Moskowitz, Ooi and Pedersen (2012), 'Time Series Momentum', Journal of Financial Economics | verdict-delivered | DOES NOT SURVIVE — all four kill criteria fired (commodity sleeve, post-publication) |
| volatility-managed-market | inverse-variance volatility management adds risk-adjusted, incremental performance beyond the unscaled market | Moreira and Muir (2017), 'Volatility-Managed Portfolios', Journal of Finance | verdict-delivered | NO CLEAR INCREMENTAL HOLDOUT EVIDENCE |
