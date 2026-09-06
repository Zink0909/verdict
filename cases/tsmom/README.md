# Time-series momentum in futures

**Registry card:** `registry/time-series-momentum.json` — state `verdict-delivered`.

The claim is Moskowitz, Ooi and Pedersen (2012): the sign of a market's own
trailing 12-month return predicts its next month, across 58 futures and forwards,
strongly enough to carry a diversified Sharpe around 1.2.

The protocol was registered through the working surface before any of the code in
this directory existed, and nothing here edits it.

## Data provenance and current boundary

The protocol uses a **per-market** panel. Every one of its three benchmarks —
passive long, cross-sectional momentum, sign-randomised — is constructed from
individual market prices, and an aggregate sleeve return series cannot produce
any of them. Seven roll-adjusted commodity contracts were exported from
QuantConnect; this is a post-publication commodity-sleeve test, not the source
paper's full 58-instrument, four-asset-class universe.

The data path continues to bar the obvious shortcut:
front-month series like Yahoo's `CL=F` are not roll-adjusted, and the requirement
says the roll rule must be recorded and validated *before any signal is computed*.
Substituting unadjusted data would be precisely the move this system exists to
prevent.

## Getting the data

1. Open a QuantConnect **research** notebook and run `qc_export.py`.
   It prints a gzip+base64 blob — the free tier cannot download files, so this
   follows the same paste-back pattern the CTA project used.
2. Copy everything between the BEGIN and END markers into a file.
3. `micromamba run -n verdict python cases/tsmom/decode_panel.py paste.txt --md5 <printed md5>`

The export is month-end only and carries closes plus trailing volatility at three
windows, which is a few thousand numbers rather than a few hundred thousand. The
three windows are there so the protocol's robustness clause is executable rather
than aspirational.

## Running the protocol

```
micromamba run -n verdict python cases/tsmom/run.py
```

Each block in `run.py` names the clause it executes. The four kill criteria:

| | fires when |
|---|---|
| K1 | alpha survives neither benchmark — spanned by passive long + cross-sectional momentum |
| K2 | the effect is absent in the sealed post-publication block |
| K3 | net of costs, the interval on the mean contains zero |
| K4 | the result **survives** randomising the signal's sign |

K4 reads backwards on purpose. If coin flips with the strategy's position sizes
do just as well, the inverse-volatility scaling is the strategy and the momentum
signal is decoration.

The sealed block is opened through `verdict.splits.SealedHoldout`, so the opening
is written to `results/holdout_ledger.json` and a second opening under a changed
configuration raises rather than quietly re-running.

The run evaluates all four kill criteria. It does **not** claim that every
pre-registered perturbation is complete: longer holding periods, dropping the
most correlated individual markets, and integer-contract sizing with contract
multipliers remain unexecuted and are stated as limitations in the report.

## Known-answer controls

```
micromamba run -n verdict python cases/tsmom/validate.py     # 4 worlds x 6 seeds
```

Also runs as the `tsmom-controls` gate in `scripts/regress.py`, at two seeds.

| world | what is in it | what must happen |
|---|---|---|
| **COMMON** | one shared regime moves every market together and flips sign | **nothing fires** — positive control |
| **IDIO** | each market trends independently | cross-sectional momentum picks it up and takes a large loading |
| **TILT** | constant positive drift, no trend at all | K1 fires; the passive long beats the strategy |
| **NOISE** | zero-mean independent returns | K4 and K1 fire |

Two things were learned building these, and both are in the code rather than only
here.

**The first positive control was wrong.** It gave each market an independent
trend, the apparatus fired K1, and that looked like a bug. It was not: a
cross-sectional rule ranks markets by trailing return, so in a world of
independent trends it captures the same information and *should* span the
strategy. What time-series momentum can do that cross-sectional momentum
structurally cannot is turn the whole book long or short at once. That common
direction is the claim's specific content, so that is what a positive control
has to contain. Both worlds are kept, because the difference between them is
exactly what the second benchmark exists to detect.

**IDIO has no crisp answer at the criterion level, and is not asserted as if it
did.** With only seven markets, seven independent regimes still average into a
wandering common direction that a time-series rule can trade and a dollar-neutral
one cannot, so alpha may legitimately survive there. The controls therefore
assert what *is* derivable — how benchmark 2 must behave — rather than inventing
a known answer for the verdict.

## Files

| | |
|---|---|
| `qc_export.py` | run in a QC research notebook; prints the panel as a blob |
| `decode_panel.py` | blob → `data/panel.csv`, md5-checked |
| `tsmom.py` | the strategy and its three benchmarks, sharing one construction path |
| `run.py` | executes the registered protocol, writes `results.json` |
| `validate.py` | the four known-answer worlds |
