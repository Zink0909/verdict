#!/usr/bin/env python3
"""Known-answer controls for the time-series momentum machinery.

The protocol is registered and the execution code is written, but the panel it
needs is still on the vendor platform. That is the right moment to check the
apparatus, because it can be checked without the data it will eventually judge:
build panels whose answer is known by construction and require the code to
return that answer.

Four worlds, simulated daily and sampled month-end exactly as the real export
will be, so this exercises the real code path rather than a parallel one.

The first design of this file got the positive control wrong in a way worth
recording. It gave each market its own independent trend — and the apparatus
fired K1, which looked like a failure and was not. Cross-sectional momentum
ranks markets by trailing return, so in a world of independent trends it
captures the same information and *should* span the strategy. What time-series
momentum can do and cross-sectional momentum structurally cannot is turn the
whole book long or short at once. That common, sign-flipping direction is the
claim's specific content, so that is what the positive control must contain.
Both worlds are kept below, because the difference between them is the thing
the protocol's second benchmark exists to detect.

  A  COMMON    one shared regime moves every market together and flips sign.
              Cross-sectional dispersion is pure noise, so no benchmark can
              reach this: only a rule that times the common direction earns.
              Required: NOTHING fires — in a world where the claim is true the
              apparatus must let it live. Without this control a null from
              this apparatus would mean nothing.

  B  IDIO      each market trends independently. Real predictability, but not
              the kind that is specific to this claim.
              Required: K1 FIRES, and cross-sectional momentum is the benchmark
              that does the spanning.

  C  TILT      independent returns with a constant positive drift and no trend
              whatsoever. The rule ends up long almost always and looks
              profitable on its own — the exact illusion benchmark 1 exists
              to catch. Required: K1 FIRES.

  D  NOISE     zero-mean independent returns. Nothing to find.
              Required: K4 FIRES — the strategy sits inside the distribution
              of random-sign strategies with identical position sizes.

    micromamba run -n verdict python cases/tsmom/validate.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
sys.path.insert(0, str(HERE))

import tsmom as T          # noqa: E402
from run import execute    # noqa: E402

MARKETS = ["CL", "NG", "GC", "HG", "ZC", "ZS", "ZW"]
VOL_WINDOWS = (20, 60, 120)
TD = 252
DAYS_PER_MONTH = 21


def synth(kind: str, n_months: int = 400, seed: int = 0):
    """Build a month-end panel in the exact shape `qc_export.py` will produce."""
    rng = np.random.default_rng(seed)
    n_days = n_months * DAYS_PER_MONTH
    sigma = 0.012                      # ~19% annualised, typical for these markets

    def regime(strength: float) -> np.ndarray:
        """A two-state drift that persists for roughly eighteen months.

        Two design choices, both learned the hard way. The regime is longer than
        the signal's lookback, because a twelve-month rule cannot be expected to
        track a six-month regime and a control it cannot pass is a broken
        control, not a broken apparatus. And the realised path is demeaned, so
        the world contains exactly zero unconditional drift: a passive long
        position earns nothing here by construction, which is what makes any
        return the strategy shows attributable to timing rather than luck in
        how many months happened to be up.
        """
        mu = np.empty(n_days)
        state = 1.0 if rng.random() < 0.5 else -1.0
        for i in range(n_days):
            if rng.random() < 1.0 / 378.0:
                state = -state
            mu[i] = state * strength
        return mu - mu.mean()

    shared = regime(0.0011) if kind == "common" else None

    daily = {}
    for sym in MARKETS:
        eps = rng.normal(0.0, sigma, n_days)
        if kind == "common":
            r = shared + eps
        elif kind == "idio":
            r = regime(0.0011) + eps
        elif kind == "tilt":
            r = 0.0006 + eps           # ~15% a year of pure drift, no persistence
        elif kind == "noise":
            r = eps
        else:
            raise ValueError(kind)
        daily[sym] = pd.Series(r)

    dr = pd.DataFrame(daily)
    closes_d = 100.0 * (1.0 + dr).cumprod()
    idx = pd.date_range("2009-01-31", periods=n_days, freq="B")
    closes_d.index = idx
    dr.index = idx

    ends = closes_d.index[DAYS_PER_MONTH - 1::DAYS_PER_MONTH]
    closes = closes_d.loc[ends]
    vols = {w: (dr.rolling(w).std() * np.sqrt(TD)).loc[ends].clip(lower=T.VOL_FLOOR)
            for w in VOL_WINDOWS}
    keep = vols[max(VOL_WINDOWS)].dropna().index
    return closes.loc[keep], {w: v.loc[keep] for w, v in vols.items()}


def _fired(r, k):
    return r.get(k) is True


def _xs(r):
    return r["benchmarks"]["xs_momentum"]["sharpe"]


def _passive(r):
    return r["benchmarks"]["passive_long"]["sharpe"]


# Each check is asserted per seed. They deliberately test different organs: two
# check that a kill criterion fires when it should, two that nothing fires when
# the claim is true, and two check a *benchmark* rather than a criterion.
#
# The benchmark checks exist because the IDIO world has no crisp answer at the
# criterion level, and pretending otherwise would be inventing a known answer.
# With only seven markets, seven independent regimes still average into a
# wandering common direction that time-series momentum can trade and a
# dollar-neutral cross-sectional rule cannot, so alpha may legitimately survive
# there. What *is* derivable is how benchmark 2 must behave: cross-sectional
# momentum must see independent trends and must be blind to a common one. That
# is the claim the IDIO and COMMON pair is allowed to make.
CONTROLS = [
    ("common", "the claim is true and specific to it", [
        ("no kill criterion fires", lambda r: not r["kill_criteria_fired"]),
        ("cross-sectional momentum is blind to a common direction", lambda r: _xs(r) < 0.5),
        ("a passive long earns nothing", lambda r: abs(_passive(r)) < 0.5),
    ]),
    ("idio", "real trends, but not the kind specific to this claim", [
        ("cross-sectional momentum picks up independent trends", lambda r: _xs(r) > 0.8),
        ("it takes a large positive loading in the spanning regression",
         lambda r: r["K1_spanning"]["betas"]["xs_momentum"] > 0.3),
    ]),
    ("tilt", "drift masquerading as timing", [
        ("K1 fires", lambda r: _fired(r, "K1_fires")),
        ("the passive long beats the strategy it is supposed to explain",
         lambda r: _passive(r) > r["strategy"]["sharpe"]),
    ]),
    ("noise", "nothing to find", [
        ("K4 fires", lambda r: _fired(r, "K4_fires")),
        ("K1 fires", lambda r: _fired(r, "K1_fires")),
    ]),
]

SEEDS = range(6)


def main() -> int:
    failures = []
    print(f"known-answer controls  ({len(SEEDS)} seeds each)\n")
    for kind, blurb, checks in CONTROLS:
        rows = []
        for s in SEEDS:
            closes, vols = synth(kind, seed=s)
            res = execute(closes, vols, sign_draws=60, seal_from=None, label=f"{kind}-{s}")
            rows.append(res)
            for name, fn in checks:
                if not fn(res):
                    failures.append(f"{kind} seed {s}: {name}")

        print(f"  {kind.upper():6}  {blurb}")
        print(f"          strat Sh {np.mean([r['strategy']['sharpe'] for r in rows]):+.2f}   "
              f"passive Sh {np.mean([_passive(r) for r in rows]):+.2f}   "
              f"xs Sh {np.mean([_xs(r) for r in rows]):+.2f}   "
              f"alpha t {np.mean([r['K1_spanning']['t_stat_hac'] for r in rows]):+.2f}   "
              f"pct-vs-random {np.mean([r['K4_sign_randomisation']['strategy_percentile_vs_random'] for r in rows]):.0%}")
        print(f"          fired: {[sorted(r['kill_criteria_fired']) for r in rows]}")
        for name, _ in checks:
            bad = sum(1 for f in failures if f.startswith(kind) and f.endswith(name))
            print(f"          {'FAIL' if bad else 'ok  '}  {name}")
        print()

    if failures:
        print("FAIL")
        for f in failures:
            print("  ", f)
        return 1
    print("all controls passed — the apparatus separates a claim-specific effect,\n"
          "a cross-sectional effect, a pure tilt and noise")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
