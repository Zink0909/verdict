# Case: The Virtue of Complexity in Return Prediction

**Verdict: mechanical artifact, not learned signal** (Nagel confirmed, 3/3 diagnostics).
Full write-up: [`report.html`](report.html). Registry card: [`../../registry/complexity-voc.json`](../../registry/complexity-voc.json).

This is the first case audited *through* the verdict framework end to end (the
other cases retrofit completed projects); it is also the framework's first
"fresh" adjudication of a claim it did not grow out of.

## What is audited

Kelly–Malamud–Zhou (2024, *JF*) claim that a 12,000-feature ridgeless RFF model
times the market out-of-sample even in T=12 windows, improving with complexity.
Nagel (2025) argues it is a mechanical volatility-timed momentum rule. We
reproduce and adjudicate.

## Pipeline

```
preprocess.py       official Goyal data -> standardized panel; PRIMARY GATE:
                    anchor to VoC authors' own GYdata.mat (corr 1.0000/column)
run_kmz.py          the virtue-of-complexity curve (SR vs P), anchored to nkonts
run_nagel.py        the three diagnostics (kernel equivalence, reversal, bootstrap)
phase_diagram.py    the boundary in T (momentum mechanism fades, no genuine learning)
make_figures.py     figures for the report
```

Reproduce (data pinned in `data/`, all CPU, offline):

```bash
micromamba run -n verdict python cases/complexity/preprocess.py
micromamba run -n verdict python cases/complexity/run_kmz.py
micromamba run -n verdict python cases/complexity/run_nagel.py
micromamba run -n verdict python cases/complexity/phase_diagram.py
micromamba run -n verdict python cases/complexity/make_figures.py
```

## Provenance & pins

- `M0_PINNED.md` — every construction detail (target, 15 predictors, RFF spec,
  ridge convention, standardization) with sources.
- `results/M2_NOTES.md`, `results/M3_NOTES.md` — result records + audit
  observations accumulated for the verdict.
- Data anchored to the original authors' `GYdata.mat`; cross-checked against two
  independent open-source replications (zivmi, nkonts). The 100 MB nkonts metrics
  grid is an optional cross-check and is not shipped; the compact nkonts input
  cross-check remains in `data/`.

## Headline numbers

| | |
|---|---|
| Replication | SR 0.00 → 0.36 as P 2 → 12,000; negative OOS R² with positive SR; c=P/T=1 singularity |
| Kernel equivalence | RFF vs kernel forecast corr **0.997**; kernel spans strategy R²=**0.995**, residual α t=**−0.85** |
| Reversal world | +0.36 → **−0.09**, negative 8/8 draws |
| Wild bootstrap | +0.36 → **+0.38** unchanged |
| Boundary (T) | momentum signature 0.83 (T=12) → 0.26 (T=240); SR flat; reversal negative throughout |
