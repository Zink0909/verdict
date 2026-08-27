# M0 Pinned Decisions — Complexity Case (KMZ Replication Spec)

> Every construction detail below is pinned from primary/replication sources on 2026-08-17.
> Do not change without a deviation note. Sources: nkonts repo (includes KMZ paper PDF),
> zivmi repo (includes official Goyal data + preprocessing notes verified against VoC matlab output).

## Data (pinned files in `data/`)

| File | Provenance | Role |
|---|---|---|
| `PredictorData2022.xlsx` | Amit Goyal's official dataset (2022 vintage), via zivmi/voc_reproduction `data/raw/` | **Canonical input** |
| `zivmi_processed_crosscheck.csv` | zivmi's processed output (verified by them against VoC matlab `Y` variable) | Cross-check for our preprocessing |
| `nkonts_2021_crosscheck.csv` | nkonts repo (2021 vintage monthly) | Second cross-check |

## Target variable

- `R = CRSP_SPvw − Rfree` (monthly excess return of CRSP value-weighted index).
- **Use the `Rfree` column, not `tbl`** — zivmi verified near-perfect match with VoC's matlab `Y` only with `Rfree`.

## 15 predictors (Welch–Goyal 2008 set + lagged market return)

`dp, dy, ep, de, svar, bm, ntis, tbl, lty, ltr, tms, dfy, dfr, infl` + `mr` (one-lag CRSP_SPvw).
- **`infl` is used with an extra one-month lag** (CPI released the following month — GW convention).

## Standardization (backward-looking only — preserves OOS nature)

- **Returns**: divide by trailing 12-month volatility from the *uncentered* second moment:
  σ_t = sqrt(mean(R²) over past 12m).
- **Predictors**: divide by *expanding-window* std, min 36 months of history.

## RFF construction

- ω ~ N(0, 1), shape (K, P/2); A = γ·G·Ω; features = interleaved [sin(A), cos(A)] → P total.
- γ = 2 (KMZ default; γ grid {0.5, 1, 2} for sensitivity).
- No 1/√P scaling in features — the scale is absorbed by the ridge penalty convention below.
- Seeds: ≥10 draws of Ω; report distributions.

## Ridge / ridgeless

- **No intercept** (`fit_intercept=False`) — note: this is exactly Buncic's switch (i); our
  implementation makes it an explicit boolean so the switch can be tested.
- Penalty convention: effective alpha = **z · T** (nkonts, matches paper's scaling).
- Full z path via one SVD per window (z log-grid 1e-6 → 1e3 + ridgeless limit via pinv).

## Timing strategy & metrics

- Rolling window T ∈ {12, 60, 120}; forecast at t uses window [t−T, t−1]; position ∝ forecast μ̂_t
  (unscaled); strategy return = μ̂_t × R_{t+1}.
- Metrics: annualized mean/vol/SR; market-regression alpha & beta; OOS R²; CW/DM tests (our addition,
  per Fed FX protocol); spanning vs Nagel mechanical benchmark.
- Buncic switch (ii): performance aggregation — KMZ's scheme vs conventional; both implemented.

## Known deviation risks

- zivmi note: `bm` differs slightly from VoC's vintage (Goyal updated methodology) — accept, document.
- 2022 vintage vs KMZ's older sample: anchor on direction/magnitude, not digit-level equality.
