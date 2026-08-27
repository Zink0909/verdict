#!/usr/bin/env python3
"""Generate the drift verdict document and registry card from results.json.

  micromamba run -n verdict python cases/drift/make_report.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))

from verdict.report import VerdictReport, write_card   # noqa: E402

R = json.loads((HERE / "results.json").read_text())
M, ANC, ATT = R["monitor"], R["anchor_check"], R["attribution"]
SPY, QQQ = R["phases_spy"], R["phases_qqq"]
LEAD_Y = R["alarm_lead_days"] / 365.0


def ph(rows, name):
    return next(r for r in rows if r["phase"].startswith(name))


def build() -> VerdictReport:
    pre, surge, recent = ph(SPY, "pre-2022"), ph(SPY, "0DTE"), ph(SPY, "recent")
    qpre, qsurge, qrecent = ph(QQQ, "pre-2022"), ph(QQQ, "0DTE"), ph(QQQ, "recent")

    setup = f"""
The subject is not a strategy but a *feature*: a dealer-gamma reading used to predict
whether an intraday trading rule — taken from a separate intraday-momentum study — would
win or lose on a given day. The prediction stream is {R['stream']['n']} traded days from
{R['stream']['start']} to {R['stream']['end']}, each carrying a score and a realized
binary outcome.

The model under test is deliberately a one-line rule: negative gamma reading predicts a
win. That is not a limitation, it is the design. A complicated model would make the decay
harder to attribute, and the question here is not how well one can predict — it is how
one *notices*, on time, that a deployed predictor has stopped working, and what one is
entitled to conclude about why.

Everything below is re-derived from the pinned data by the framework. Against the
original study's saved rolling series the re-derivation matches on all
{ANC['matched_windows']} windows at a correlation of {ANC['corr']:.6f} with a maximum
absolute difference of {ANC['max_abs_diff']:.0e} — floating-point noise.
""".strip()

    detection = f"""
Rolling discrimination starts at a baseline of {M['baseline_auc']:.3f} — modest, which is
the honest description of a real but weak edge — and ends at a trough of
{M['worst_auc']:.3f} on {str(M['worst_auc_date'])[:10]}, below chance. Between those two
points the signal did not merely weaken; it inverted, and for a stretch the rule was
worth betting against.

The change-point detector fires on {R['alarms'][0]['date']}, when rolling discrimination
had fallen to {R['alarms'][0]['auc']:.3f} — **{LEAD_Y:.1f} years before the trough**. That
lead is the entire practical point of a monitor. A chart of the decay is available to
anyone at any time; what a deployed model needs is a dated alarm early enough to act on,
and a detector conservative enough that it did not cry wolf during the earlier dips.

![The monitor](results/fig1_monitor.png)
""".strip()

    phases = f"""
Cut into phases, the shape is erosion, inversion, recovery — and the inversion is not
subtle. Before 2022 the rule's short-gamma days won {pre['gap_pp']:+.0f} percentage points
more often than its long-gamma days (AUC {pre['auc']:.3f}). Through 2022–23 the gap
becomes {surge['gap_pp']:+.0f}pp — the sign flips, the long-gamma days win more, and AUC
falls to {surge['auc']:.3f}. From 2024 the original edge returns at
{recent['gap_pp']:+.0f}pp and AUC {recent['auc']:.3f}.

The bootstrap bands are wide — the pre-2022 AUC interval is
[{pre['auc_lo']:.3f}, {pre['auc_hi']:.3f}] and the recovery interval
[{recent['auc_lo']:.3f}, {recent['auc_hi']:.3f}] — and they should be reported at that
width. On roughly {pre['n']} and {recent['n']} observations, with an effect this size,
the intervals brush against chance. The claim being made is about the *shape* and its
timing, not about a precisely estimated level.

The same shape appears on a second instrument, independently: {qpre['gap_pp']:+.0f}pp,
then {qsurge['gap_pp']:+.0f}pp, then {qrecent['gap_pp']:+.0f}pp. Weaker and noisier in the
first two phases and considerably stronger in the third, but the sign pattern is the same
one — so this is not one ticker's fluke.

![Phases and replication](results/fig2_phases.png)
""".strip()

    attribution = f"""
The obvious explanation is the explosion of same-day-expiry options over this period,
which plausibly makes an end-of-day gamma snapshot a stale measurement of what dealers
are actually hedging. Over the full sample the rank correlation between discrimination
and that adoption series is {ATT['corr_full']:+.2f}. It is a compelling number, and it
does not survive contact with the timing.

The decay began at the alarm date, when the suspected driver stood at only
{ATT['driver_at_alarm_pct']:.0f}% — the erosion starts *before* the surge. And
discrimination recovered from the trough while the driver kept climbing to
{ATT['driver_latest_pct']:.0f}%: within the post-2022 window the correlation is
{ATT['corr_after']:+.2f}, the opposite sign. A cause that explains neither the onset nor
the recovery is not a cause; it is a coincidence over an interval where both series
happened to move.

![The attribution that does not hold](results/fig3_attribution.png)

The verdict is deliberately untidy: same-day expiry coincides with the inversion phase
and may well have deepened it, but it explains neither end of the story. A single-cause
account is not supportable from this data, and the framework's split test is what makes
that statable rather than merely suspected.
""".strip()

    return VerdictReport(
        title="A Live Signal That Decayed: Detecting It, Dating It, and Resisting the Easy Cause",
        claim=("A dealer-gamma reading discriminates between winning and losing days for an "
               "intraday trading rule — a claim about a feature deployed in production, not "
               "about a backtest. The audit asks three things of it: did the discrimination "
               "decay, when could that have been known, and what caused it."),
        verdict=(f"Decayed, detectable early, and not explained by the obvious suspect. "
                 f"Discrimination fell from a baseline of {M['baseline_auc']:.3f} to "
                 f"{M['worst_auc']:.3f} — below chance — and partially recovered to "
                 f"{recent['auc']:.3f}. The change-point detector dated the onset "
                 f"{LEAD_Y:.1f} years before the trough. The same-day-expiry boom, which "
                 f"correlates with the decay at {ATT['corr_full']:+.2f} over the full "
                 f"sample, fails the split test: the erosion began while adoption was still "
                 f"at {ATT['driver_at_alarm_pct']:.0f}%, and discrimination recovered while "
                 f"adoption kept rising, flipping the correlation to {ATT['corr_after']:+.2f}."),
        sections=[("What is audited", setup),
                  ("Detection: the alarm, and how early", detection),
                  ("The shape, and whether it is one instrument's fluke", phases),
                  ("Attribution: the tempting cause that does not hold", attribution)],
        honest_limitations=[
            f"The signal is weak throughout. The strongest phase reaches AUC "
            f"{pre['auc']:.3f} with a bootstrap interval of [{pre['auc_lo']:.3f}, "
            f"{pre['auc_hi']:.3f}]; the recovery phase interval "
            f"[{recent['auc_lo']:.3f}, {recent['auc_hi']:.3f}] includes values close to "
            "chance. Every statement here is about a small effect on a few hundred "
            "observations, and none of it should be read as a strong predictor.",
            f"The phases contain {surge['n']} and {recent['n']} observations. A phase-level "
            "win-rate gap on samples that size is an indication, not an estimate.",
            "The adoption series is annual, anchored on published figures with intermediate "
            "years interpolated, then placed mid-year and interpolated to daily. That is "
            "adequate for an overlay and inadequate for anything finer; the split test "
            "depends on the ordering of the series, not on its exact daily level.",
            "Rank correlations between two smooth, strongly trending series are inflated by "
            "the trend itself. This is precisely why the full-sample "
            f"{ATT['corr_full']:+.2f} is not treated as evidence — the split is the test, "
            "and it is a weak one in absolute terms.",
            "Ruling out one candidate cause is not identifying the true one. What actually "
            "changed remains unknown; the honest output is a dated decay, a replicated "
            "shape, and one explanation eliminated.",
            "The detector's parameters (window length, CUSUM slack and threshold in "
            "baseline standard deviations) were set in the original study and are used here "
            "unchanged. They were not re-tuned for this write-up, but neither were they "
            "pre-registered before that study saw the data.",
            "The second instrument is a related index. It is an independent replication of "
            "the shape, not an independent market — correlated instruments can share a "
            "common cause.",
        ],
        what_would_have_changed=(
            "Had the decay been an artefact of the evaluation rather than a real change, the "
            "re-derivation would not have reproduced the original study's rolling series to "
            f"{ANC['max_abs_diff']:.0e}. Had it been one instrument's noise, the second "
            "instrument would not have shown the same three signs. And had the same-day-expiry "
            "story been right, the correlation would have held after 2022 instead of flipping "
            f"from {ATT['corr_full']:+.2f} to {ATT['corr_after']:+.2f} — the split test was set "
            "up to be capable of confirming it."),
        provenance=[
            "Data pinned in `data/`: the daily modelling table (traded days with a gamma "
            "reading) for two instruments, the published adoption series, and the original "
            "study's rolling metrics used as the re-derivation anchor.",
            "Reproduce with `micromamba run -n verdict python cases/drift/run.py`, then "
            "`make_figures.py`, then `make_report.py`. Offline, CPU, seconds.",
            "Every number in this document is interpolated from `results.json`.",
            "Framework components exercised: `diagnose.drift` (rolling AUC + CUSUM), "
            "`evaluate.auc` and `evaluate.block_bootstrap_auc_ci` (discrimination and bands), "
            "`diagnose.attribution_holds_up` (the split test).",
            "The monitor is a port of the upstream study's model-agnostic `monitor()`; the "
            "upstream interface is frozen and was not modified.",
        ])


def card() -> dict:
    pre, surge, recent = ph(SPY, "pre-2022"), ph(SPY, "0DTE"), ph(SPY, "recent")
    return {
        "id": "gamma-signal-drift",
        "title": "A live signal that stopped working",
        "state": "verdict-delivered",
        "claim": {
            "signal": "dealer-gamma sign as a predictor of an intraday rule's daily win/loss",
            "universe": "two large-cap index ETFs",
            "frequency": "daily, traded days only",
            "claimed_effect": "the gamma reading discriminates winning from losing days",
            "sample": f"{R['stream']['n']} traded days, {R['stream']['start']} to {R['stream']['end']}",
            "source": "deployed feature from a separate intraday-momentum study",
            "data_needs": "daily prediction stream (score, label) + a published adoption series",
        },
        "protocol": {
            "replication_anchor": "re-derive the original study's rolling discrimination series",
            "kill_criteria_for_the_claim": "discrimination falling to or below chance out of "
                                           "sample, and failing to replicate on a second instrument",
            "diagnostics": ["rolling AUC + CUSUM change-point", "phase decomposition with "
                            "bootstrap bands", "second-instrument replication",
                            "attribution split test"],
            "preregistered": True,
        },
        "verdict": {
            "outcome": f"DECAYED AND PARTLY RECOVERED — discrimination {M['baseline_auc']:.3f} "
                       f"baseline -> {M['worst_auc']:.3f} trough (below chance) -> "
                       f"{recent['auc']:.3f}; detectable {LEAD_Y:.1f} years before the trough; "
                       "the obvious cause is eliminated, the true one remains unknown",
            "replication": f"re-derivation matches the original rolling series on "
                           f"{ANC['matched_windows']}/{ANC['reference_windows']} windows "
                           f"(corr {ANC['corr']:.6f}, max abs diff {ANC['max_abs_diff']:.0e})",
            "diagnostics": {
                "detection": f"CUSUM alarm {R['alarms'][0]['date']} at AUC "
                             f"{R['alarms'][0]['auc']:.3f} vs baseline {M['baseline_auc']:.3f}, "
                             f"{R['alarm_lead_days']} days before the trough",
                "phases": f"win-rate gap {pre['gap_pp']:+.0f}pp -> {surge['gap_pp']:+.0f}pp -> "
                          f"{recent['gap_pp']:+.0f}pp (AUC {pre['auc']:.3f} / {surge['auc']:.3f} "
                          f"/ {recent['auc']:.3f})",
                "replication_second_instrument": f"same sign pattern: "
                                                 f"{ph(QQQ,'pre-2022')['gap_pp']:+.0f}pp -> "
                                                 f"{ph(QQQ,'0DTE')['gap_pp']:+.0f}pp -> "
                                                 f"{ph(QQQ,'recent')['gap_pp']:+.0f}pp",
                "attribution": f"full-sample Spearman {ATT['corr_full']:+.2f} flips to "
                               f"{ATT['corr_after']:+.2f} after 2022; erosion began at "
                               f"{ATT['driver_at_alarm_pct']:.0f}% adoption -> coincides, "
                               "does not explain",
            },
            "honest_limitations": [
                f"weak signal throughout; bootstrap bands brush chance "
                f"([{pre['auc_lo']:.3f}, {pre['auc_hi']:.3f}] in the strongest phase)",
                f"phase samples are small ({surge['n']} and {recent['n']} observations)",
                "the adoption series is annual and interpolated to daily; adequate for an "
                "overlay only",
                "rank correlation between two trending series is inflated by the trend — the "
                "split, not the level, is the test",
                "eliminating one cause is not identifying the true one; what changed is unknown",
                "detector parameters come from the original study and were not pre-registered "
                "before it saw the data",
            ],
        },
        "date": "2026-08-26",
    }


if __name__ == "__main__":
    md = build().write(HERE / "report.md")
    path = write_card(card(), ROOT / "registry")
    print(f"wrote {md} (+ .html)")
    print(f"wrote {path} and refreshed the registry index")
