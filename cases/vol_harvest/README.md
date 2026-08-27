# Case: Harvesting the Volatility Risk Premium at Retail Scale

**Verdict: falsified — a true premise whose conclusion does not follow.**
Full write-up: [`report.html`](report.html). Registry card:
[`../../registry/retail-short-volatility.json`](../../registry/retail-short-volatility.json).

The library's only case where the premise is *not* in doubt. Implied volatility really
does exceed realized volatility, by about 3.4 points, about 82% of the time. The claim
under audit is the step after that: that a small account can therefore harvest it.

## Pipeline

```
run.py            re-executes the pre-registered selection rule on the modelled grid,
                  measures the win-rate/profit relation across 108 configurations, the
                  granularity feasibility law and the delta gradient, computes the
                  breakeven friction, and compares the modelled ranking with the
                  recorded real-chain results
make_figures.py   three figures from results.json
make_report.py    the verdict document and the registry card
```

Reproduce (data pinned in `data/`, offline, CPU, seconds):

```bash
micromamba run -n verdict python cases/vol_harvest/run.py
micromamba run -n verdict python cases/vol_harvest/make_figures.py
micromamba run -n verdict python cases/vol_harvest/make_report.py
```

## Headline numbers

| | |
|---|---|
| The premise | volatility premium +3.4 vol points, positive 82.5% of the time — **true** |
| Modelled winner | 45Δ / 1.5% wide: +$17.1/trade, CAGR +0.7%, Sharpe 0.25 |
| Real chains | same configuration: **−43.9% net, −6.75% CAGR**; earlier candidate −14.5% |
| Friction cliff | modelled edge crosses zero at **0.082 index points per leg** vs 0.05 assumed |
| Win rate ≠ profit | corr(win rate, expectancy) = +0.48; **57%** of configurations winning ≥85% of trades lose money; the best win rate (92.9%) earns **−$1.7/trade** |
| Granularity | mean expectancy rises with width (−$12.8 → +$14.9) while tradability collapses (80 → 0 trades after 2021) |

## Audit results

- **The selection rule, re-executed, picks a different configuration** than the one
  carried forward (45Δ/2.0% rather than 45Δ/1.5%). The override is documented in the
  source study and defensible — the 2.0% width had stopped trading well before the sample
  ended — but it is an override of a pre-registered rule and the report says so.
- **Recorded, not recomputed**: the real-chain runs and the friction sensitivity table
  come from the source project's authority documents; the raw platform logs were never
  saved. Pinned with provenance in `data/realchain_results.json`.
- **The ranking inverted**: the only configuration the modelled grid rated
  feasible-and-positive was the worst of those actually traded. The model priced the
  premium and could not price the execution.
