# Case: Buying Dips in Wide-Moat Names via Long Calls

**Verdict: negative on the instrument, not on the thesis.**
Full write-up: [`report.html`](report.html). Registry card:
[`../../registry/buy-the-dip-long-calls.json`](../../registry/buy-the-dip-long-calls.json).

This is a retrofit: the trade record was produced by a completed study, and the case
re-derives the verdict *through the framework*. The point of a retrofit is not to reprint
old numbers — it is to check them without trusting them, and to ask the questions the
original could not.

## What is audited

The claim is a practitioner one rather than a paper: dips in high-quality, wide-moat
companies can be bought profitably, and the long call is the natural expression because
loss is capped at the premium. 2,392 dip purchases across 38 names, 2014–2024, priced
from real daily option chains.

## Pipeline

```
run.py            audits the record (accounting re-derived from primitives; universe
                  rebuilt from raw fundamentals; look-ahead scan), then reproduces the
                  headline, the expression playbook, the observed volatility test, the
                  modelled delta/vega/theta attribution, and the robustness sweep
make_figures.py   three figures from results.json
make_report.py    the verdict document and the registry card — every number interpolated
                  from results.json, none typed by hand
```

Reproduce (data pinned in `data/`, offline, CPU, seconds):

```bash
micromamba run -n verdict python cases/buy_the_dip/run.py
micromamba run -n verdict python cases/buy_the_dip/make_figures.py
micromamba run -n verdict python cases/buy_the_dip/make_report.py
```

## Headline numbers

| | |
|---|---|
| The strategy | mean −$263/trade, median −$2,428, win rate 0.36 (per $10,000, net of costs) |
| The same dips in the stock | mean +$263, median +$150, win rate 0.55 — the expression gives up $649/trade |
| Recovery before exit | never 1,785 (75%) · reached and gave back 228 (10%) · held 379 (16%) |
| The option clock | 247 of 282 never-recovered dip events (87.6%) returned to the entry price within a year **after** exit — recovered figure, denominator verified locally, upper bound |
| The volatility prior | **refuted**: on recovering trades implied volatility *rose* (+0.039 mean, fell in only 23%) |
| Attribution per trade | theta −$2,615 · vega +$1,825 · delta +$1,656; in deep panics delta −$4,536 dominates |
| Robustness | median negative in all 9 moat definitions; the mean turns positive only in the tightest cell, and that is reported |

## Audit results

- **Accounting**: contract counts and dollar P&L re-derived from `costs.budget_pnl` match
  the record exactly — 0 mismatches.
- **Universe**: the persistence screen rebuilt from raw fundamentals reproduces 211 of
  216 stored (year, name) memberships. The five it cannot confirm are gaps in the
  exported fundamentals, not disagreements about the screen.
- **Look-ahead**: no record used in an as-of decision carries a later timestamp.
- **Recovered, not recomputed**: the 87.6% option-clock figure (247 of 282 dip events)
  came from a probe on the vendor's platform whose printed output was never saved; it was
  recovered from the transcript of the session that ran it and is pinned with its
  provenance in `data/option_clock_probe.json`. `run.py` verifies its **denominator**
  against this trade record — deduplicating the never-recovered trades to unique dip
  events yields exactly 282 — so the number demonstrably belongs to this data. Re-deriving
  it rather than tracing it needs the vendor platform.
