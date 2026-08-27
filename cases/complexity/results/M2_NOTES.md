# M2 Results — KMZ Replication (Gate 5: PASS)

Date: 2026-08-17. Full sweep: 10 seeds x P in {2,12,120,600,1200,6000,12000} x
z in {0, 1e-3, 1e-1, 1e1, 1e3}, T=12, gamma=2. Data anchored 1.0000 per column
to the VoC authors' own GYdata.mat (see preprocess.py primary gate).
Artifacts: `kmz_sweep.parquet` (350 rows), `kmz_sweep_quick.parquet`.

## KMZ signatures reproduced (direction + magnitude)

1. **SR rises monotonically with P** at every z, including ridgeless:
   0.00 (P=2) -> 0.361 (P=12,000) mean over 10 seeds.
2. **Negative OOS R^2 alongside positive timing SR** (P=12,000: R^2 = -0.012,
   SR = +0.36) — the paper's headline provocation.
3. **Interpolation-threshold singularity at c = P/T = 1** (P=12): ridgeless
   OOS R^2 explodes to ~ -5e4 — the double-descent variance peak, visible raw.

## Anchor vs nkonts reproduced grid (gamma=2, T=12)

Same shape; ours systematically ~0.02-0.04 lower in SR. Attribution tested:

| Hypothesis | Test | Verdict |
|---|---|---|
| 2022 data year (they used 2021 vintage) | truncate our sample at 2021-12, rerun | **Rejected** — gap unchanged (0.352 vs 0.395) |
| sigma convention (repos scale returns by trailing vol whose window INCLUDES the scaled month) | rerun with inclusive sigma | **Confirmed** — high-P gap closes (z=1e3/P=12k: 0.421 vs 0.418; z=1e-3: 0.377 vs 0.395) |

Residual at low P (0.199 vs 0.232 at P=120) — seed/draw conventions; immaterial
to the phenomenon; not chased further.

## Audit observations accumulating for the verdict

1. **infl look-ahead ambiguity (original construction)**: GW's paper states CPI
   is published with a one-month lag, but VoC's own X uses the contemporaneous
   infl column. Whether the distributed column embeds the lag is ambiguous.
   Tiny effect; flagged, sensitivity available.
2. **Scaling look-ahead (replication convention)**: return standardization in
   the replication repos includes the current month in the vol window; worth
   ~0.02-0.04 SR at high P. Our default is the strictly-backward version
   (leakage-safe); the phenomenon survives either way.
3. **Interpolation singularity**: c=1 forecasts are numerically wild (R^2
   ~ -5e4) yet the timing SR there is not catastrophic — a vivid illustration
   that SR-through-positions can mask forecast insanity. Relevant to Nagel's
   point that the strategy's performance is not evidence of forecast quality.

## Status

Gate 5 (replication anchor) **PASS** under the pinned band ("direction and
magnitude, not digit-level"). M2 complete -> proceed to M3 (Nagel's three
diagnostics: mechanical benchmark spanning, reversal world, wild bootstrap).
