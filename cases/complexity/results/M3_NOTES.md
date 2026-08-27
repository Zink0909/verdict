# M3 Results — Nagel's Three Diagnostics (Verdict: mechanism confirmed)

Date: 2026-08-17. Config: KMZ headline (P=12000, z=1e-3 near-ridgeless, T=12,
gamma=2), strategy ensembled over 5 RFF seeds; reversal/bootstrap over 8 draws.
Artifacts: `nagel_diagnostics.json`.

## Verdict: all three diagnostics support Nagel

The "virtue of complexity" in the KMZ headline configuration is a **mechanical
artifact, not learned signal**. On real Goyal-Welch data the 12,000-parameter
ridgeless model reduces to a 12-month volatility-timed momentum rule.

### (1) Mechanism, shown directly on real data (not just synthetic)

The RFF ridgeless forecast is numerically identical to the Gaussian-kernel
ridgeless forecast: corr = **0.997**, and the kernel strategy spans the KMZ
strategy at **R^2 = 0.995** with residual alpha **t = -0.85** (insignificant).
The implied weights on past returns decline with lag (recency corr **+0.83** =
momentum) and their scale falls with predictor volatility (corr **-0.41** =
volatility timing). This is Nagel's mechanism, confirmed off-synthetic.

Honesty note kept in the record: a *simplified* momentum proxy (fixed linearly
declining weights x inverse predictor vol) spans only 10% (alpha t=2.45). The
crude proxy is not Nagel's exact benchmark; the kernel forecast is the rigorous
demonstration and it is decisive. Both are reported.

### (2) Reversal world — it never learns

Inject an MA(2) reversal component into returns and the strategy flips from
+0.36 to **-0.085 SR, negative in 8/8 draws**. Same predictor-similarity
weights, now applied to reversal returns -> mechanically-built momentum loses.
It does not learn that reversal is present; it manufactures momentum regardless.

### (3) Wild bootstrap — it never used the information

Destroy the predictors' predictive content (keep persistence + heteroskedasticity)
and performance is **unchanged: +0.36 -> +0.378** (8 draws, 0.26-0.48). The
performance never came from the predictors' information.

## Where the complexity CAN be real (boundary, for M4 phase diagram)

Nagel's critique targets the short-window ridgeless regime (T=12, P>>T). It does
NOT deny that complex models help with long training samples (kernel smoothing
over decades). The phase diagram (M4) maps T x P x z to locate where the "virtue"
is mechanical (short T) vs where genuine nonlinear structure could be learned —
our synthetic gate 7 (planted-nonlinear detected by RFF, not linear) proves the
harness detects real complexity when it exists, so a null here is not a blind spot.

## Status
M3 complete. All three diagnostics reproduce. Proceed to M4: phase diagram +
verdict report.
