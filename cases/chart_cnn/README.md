# Chart-CNN stock selection

**Registry card:** `registry/chart-cnn-spanning.json` — state `verdict-delivered`.

This is one of Verdict's four **foundational** studies: it supplied the
validation-versus-holdout, factor-spanning, and high-turnover cost playbooks.
It is a deliberately honest evidence retrofit, not a fresh rerun. The original
study ran inside QuantConnect Research against a point-in-time large-cap
universe; its raw data, trained predictions, and portfolio returns are not
stored in this repository.

## What is preserved

- the original English report and its numerical conclusions;
- the original chronological-split, spanning, and known-answer regression code;
- SHA-256 fingerprints of those source artifacts in `results.json`;
- a normalized case contract, registry card, public case page, and read-only
  Agent evidence provider.

The source regression suite remains runnable in its source environment:

```bash
cd /Users/mmmm/projects/SequoAlpha/chart_cnn
micromamba run -n chart-cnn python scripts/regress.py
```

That suite checks split isolation, image specifications, turnover-and-cost
identities, a spanning known answer, and an independent planted-leak audit. It
does **not** regenerate the reported large-cap CNN result without the original
QuantConnect inputs.

## Verdict boundary

The once-opened 2020-2024 holdout had spanning alpha -0.29% per month
(t=-0.62), after the 2017-2019 validation block had +0.68% (t=2.41). This is
the false-positive playbook that Verdict inherits. The result is specific to a
value-weighted, large-cap, monthly book and does not refute the source paper's
broader weekly/equal-weighted setting.

See `report.md` for the complete imported-evidence boundary and
`results.json` for the pinned source fingerprints and machine-readable figures.
