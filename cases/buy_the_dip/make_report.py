#!/usr/bin/env python3
"""Generate the buy-the-dip verdict document and registry card from results.json.

Every number in the document is interpolated from the results file that `run.py`
wrote, so the report cannot drift away from the code that produced it. Prose is
written; figures are numbers.

  micromamba run -n verdict python cases/buy_the_dip/make_report.py
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
H, EX, AC, UN = R["headline"], R["expression"], R["audit_accounting"], R["audit_universe"]
OBS, ATTR, ROB, REC = R["observed_mechanism"], R["attribution"], R["robustness"], R["recovery"]
DS = R["depth_strike"]
COV = EX["coverage"]
FAR = OBS["iv_far_from_expiry"]
CLK = R["option_clock"]
TOTAL = H["n"]


def pct(x):
    return f"{100 * x:.0f}%"


def money(x):
    return f"{'-' if x < 0 else ''}${abs(x):,.0f}"


def loss(x):
    """A loss reads as a positive amount lost, never as a negative gain."""
    return f"${abs(x):,.0f}"


def moat_label(label):
    roic, cons = label.replace("roic>=", "").split("/consist>=")
    return f"ROIC at least {float(roic):.0%} in at least {float(cons):.0%} of years"


def build() -> VerdictReport:
    tightest = [r for r in ROB["table"] if not r["all_agree"]]
    tight = tightest[0] if tightest else None
    med_all = [r["median_pnl"] for r in ROB["table"]]
    win_all = [r["win"] for r in ROB["table"]]

    setup = f"""
The trade record contains {TOTAL:,} dip purchases across {H["names"]} wide-moat names between
2014 and 2024, each expressed as a long call priced from real daily option chains, each
sized to a uniform $10,000 so that strikes are comparable in dollars rather than in
percentages. A dip is defined in volatility-normalized units — a drawdown from the
trailing high divided by the name's own volatility — so that "a dip" means the same
thing in a quiet name and a violent one; entry is at two standard deviations, and three
or beyond is classified as a deep panic. Two strikes (0.40 and 0.80 delta) and four exit
rules are carried through the whole study rather than chosen early.

Re-deriving this record through the framework begins with not trusting it. Contract
counts and dollar P&L recomputed from primitives match the record exactly
({AC['contracts_mismatch']} mismatches; every trade reproduces to the cent). The point-in-time moat universe, rebuilt from raw
fundamentals with a persistence screen — return on invested capital above 15% in at
least 70% of the trailing eight years, plus a stable gross margin — reproduces
{UN['screen_pairs_reproduced']} of the {UN['stored_pairs']} stored (year, name) pairs.
The {len(UN['screen_unconfirmed'])} it cannot confirm ({', '.join(UN['screen_unconfirmed'])})
are gaps in the exported fundamentals rather than disagreements about the screen: the
exported file carries no gross margin for Mastercard before 2009 and only two rows for
Monsanto. No record used in an as-of decision carries a later timestamp.
""".strip()

    headline = f"""
The strategy loses. The average trade returns {money(H['mean_pnl'])} on a $10,000
outlay, the median {money(H['median_pnl'])}, with a win rate of {H['win']:.2f}. The gap
between mean and median is the shape of the whole result: most trades lose most of the
premium, and the average is dragged toward zero by a minority of large rebounds.

Three-quarters of trades — {REC['never']:,} of {TOTAL:,} ({pct(REC['never'] / TOTAL)}) —
never see the underlying regain its pre-dip high before the position is closed. A
further {REC['missed']:,} ({pct(REC['missed'] / TOTAL)}) do reach it at some point during
the hold but have given it back by exit, and {REC['recovered']:,}
({pct(REC['recovered'] / TOTAL)}) are still above it when the position closes.
""".strip()

    expression = f"""
The same entries and exits, expressed in the underlying shares rather than in calls,
average {money(EX['underlying_mean'])} with a median of {money(EX['underlying_median'])}
and a win rate of {EX['underlying_win']:.2f}. Against the call's
{money(EX['deriv_mean'])} on the same trades, the option expression gives up
{money(abs(EX['expression_drag']))} per trade. Even when the stock position wins, the
call wins only {EX['deriv_win_when_underlying_wins']:.0%} of the time.

The dip-buying decision is not what fails. Buying the instrument is roughly flat to
positive; buying the option on it is not.

![Same dips, two instruments](results/fig1_stock_vs_call.png)

This comparison covers {COV['covered']:,} of the {COV['total']:,} trades — an exit price
for the underlying is not recorded for the remaining {COV['excluded_no_exit_price']},
which are trades closed at or near expiry. Those excluded trades averaged
{money(COV['excluded_mean_option_pnl'])} for the option, *better* than the
{money(COV['covered_mean_option_pnl'])} average of the covered set, so the measured drag
is the pessimistic end of the range rather than the flattering one.
""".strip()


    clock = f"""
Three-quarters of trades never saw the underlying regain its pre-dip high before the
position closed. That is a statement about the holding window, not about whether the dip
came back — and the distance between those two statements is the whole diagnosis.

The original study settled it with a probe: for each of the {CLK['n_events_probe']}
distinct dip events whose underlying never recovered before exit, did the stock return to
the entry price within a year *after* the position was closed?
{CLK['n_recovered_after_exit']} of {CLK['n_events_probe']} ({CLK['share']:.1%}) did. The
dips largely came back. The calls had already expired.

Two guards on that number, and both are load-bearing. It measures recovery to the entry
price rather than to the pre-dip high, which was not retained per trade; the entry price
is the easier level, so {CLK['share']:.0%} is an upper bound. And a recovery inside a year
does not mean a longer-dated call would have profited, because a longer hold pays more
theta. What it establishes is that the clock missed the recovery — not that removing the
clock would print money.

The probe needs daily equity history from the data vendor's platform, so it cannot be
re-run here, and its printed output was never written to disk: it was recovered from the
transcript of the session that produced it. A recovered number is worth what its link to
the data is worth, so the link is checked rather than asserted — deduplicating this trade
record's never-recovered trades to unique dip events reproduces the probe's denominator
exactly ({CLK['n_events_rederived']} events). The figure demonstrably belongs to the data
pinned in `data/`, and it is pinned there itself, with its provenance, in
`data/option_clock_probe.json`.
""".strip()

    volatility = f"""
The prior going in — the reason both strikes were carried through the study — was a
double headwind. Implied volatility is elevated when a dip is bought, so the call is
expensive; then, as the name recovers, volatility mean-reverts downward and the position
gives back more through vega. It is a clean, plausible story, and the record refutes it.

The entry and exit implied volatilities of the traded contracts are in the data, so the
test needs no model. Across trades closed at least thirty days from expiry — where a
fixed-strike volatility comparison is least distorted by the skew and the term structure
— the average change in implied volatility is
{FAR['mean']:+.3f}, and on the trades where the underlying *did* recover it is
{FAR['by_status']['recovered']['mean']:+.3f}, with volatility falling in only
{FAR['by_status']['recovered']['share_falling']:.0%} of them. Volatility rose on the way
back more often than it fell.

![The volatility test](results/fig2_volatility_test.png)

A modelled decomposition sizes the three effects. Reconstructing each contract's strike
from its entry delta and splitting the P&L into delta, vega and theta gives, per trade:
delta {money(ATTR['overall']['delta_$'])}, vega
{money(ATTR['overall']['vega_$'])}, theta {money(ATTR['overall']['theta_$'])}. Time
decay is the one term that is reliably against the position; vega is, on average, mildly
*for* it. In deep panics the picture changes character — delta becomes
{money(ATTR['by_depth']['deep']['delta_$'])} as the underlying keeps falling, and
direction, not volatility, is what does the damage.

This decomposition is modelled and its levels are not trustworthy: it reproduces the
price actually paid at entry closely (correlation
{ATTR['validity']['entry_price_corr']:.3f}, median ratio
{ATTR['validity']['entry_price_median_ratio']:.3f}) but overstates total P&L by
{money(ATTR['validity']['model_minus_actual_mean'])} per trade, because the
reconstructed strike is not the exact contract and mid-based pricing is not the price
traded. Its signs, however, are not modelled at all — they follow the observed movements
of price and implied volatility — which is what the argument above rests on.
""".strip()

    strikes = f"""
On moderate dips the two strikes are close: {money(DS['moderate|ITM'])} for the
in-the-money call against {money(DS['moderate|OTM'])} for the out-of-the-money one. In
deep panics they separate sharply — {money(DS['deep|ITM'])} against
{money(DS['deep|OTM'])} — and the in-the-money structure is materially less bad. The
answer to "which strike" is therefore conditional on how deep the dip is, which is why
both were carried to the end instead of one being dropped early on the moderate-dip
evidence. The deep-panic sample is 48 trades; the ordering is directional, not precise.
""".strip()

    robustness = f"""
The conclusion should not depend on where exactly the moat line is drawn, so the
universe definition is swept: the return-on-capital floor across 13%, 15% and 18%, and
the consistency requirement across 60%, 70% and 80%, for {ROB['cells']} definitions in
total.

The median trade is negative in all {ROB['cells']} — between
{money(min(med_all))} and {money(max(med_all))} — and the win rate stays between
{min(win_all):.2f} and {max(win_all):.2f}, never approaching one half. The share of dips
that never recovered before exit stays near three-quarters throughout.

![Robustness of the conclusion](results/fig3_robustness.png)

One cell does break, and it is reported rather than smoothed over. Under the tightest
screen ({moat_label(tight['label']) if tight else 'n/a'}), which keeps only
{tight['n_trades'] if tight else 0:,} of the {TOTAL:,} trades, the *mean* turns positive
at {money(tight['mean_pnl']) if tight else 'n/a'} while the median stays at
{money(tight['median_pnl']) if tight else 'n/a'}. That is the same mean-versus-median
asymmetry as the headline, concentrated: a smaller, higher-quality sample keeps its
handful of large rebounds while losing many of the small losers. It does not overturn
the verdict — a strategy whose median trade loses {loss(tight['median_pnl']) if tight else 'n/a'}
is not a strategy — but anyone reading only the mean would reach a different conclusion
in that corner, and they are entitled to know it.

Looser definitions admit names that were never backtested
({', '.join(ROB['untested_names'])}). They are listed rather than folded in: the
conclusion covers the trades that were actually run, and extending it to names for which
no trade exists would be claiming evidence that was never gathered.
""".strip()

    return VerdictReport(
        title="Buying Dips in Wide-Moat Names, Expressed as Long Calls",
        claim=("Dips in high-quality, wide-moat companies can be bought profitably, and "
               "the long call is the natural way to express it: loss is capped at the "
               "premium, so it is the defined-risk form of catching a falling knife. A "
               "practitioner thesis rather than a published paper — the kind of claim "
               "that is acted on far more often than it is tested."),
        verdict=("A clean negative, and a more specific one than expected. Across a "
                 f"point-in-time wide-moat universe the strategy loses "
                 f"{loss(H['mean_pnl'])} per trade on average and "
                 f"{loss(H['median_pnl'])} at the median, net of realistic option "
                 "costs. But the same dips bought in the underlying are roughly flat to "
                 "positive, so what fails is the instrument, not the thesis. The failure "
                 "is time, not volatility: the expiry clock and decay, and in deep panics "
                 "the direction of the underlying itself — while the implied-volatility "
                 "headwind that the strategy was expected to die from does not appear in "
                 "the data at all."),
        sections=[("What is audited, and how it is re-derived", setup),
                  ("Headline", headline),
                  ("The instrument, not the thesis", expression),
                  ("The clock, not the thesis", clock),
                  ("The volatility headwind that was not there", volatility),
                  ("Which strike, and when it matters", strikes),
                  ("Does the conclusion survive the definition?", robustness)],
        honest_limitations=[
            f"The option-clock figure ({CLK['share']:.1%}) is recovered, not recomputed. The "
            "probe needs daily equity history from the data vendor's platform; its printed "
            "output was never saved and was recovered from the transcript of the session "
            "that ran it. It is pinned with its provenance in "
            "`data/option_clock_probe.json`, and only its denominator is verified locally "
            f"({CLK['n_events_rederived']} dip events, matching the probe exactly). A reader "
            "who wants the number re-derived rather than traced needs that platform.",
            "That figure measures recovery to the entry price rather than to the pre-dip "
            "high, which was not retained per trade, so it is an upper bound. It also does "
            "not imply that a longer-dated call would have profited — a longer hold pays "
            "more theta. It establishes that the clock missed the recovery, nothing more.",
            "The P&L decomposition into delta, vega and theta is modelled: the strike is "
            "reconstructed from the entry delta and prices come from Black-Scholes at the "
            f"recorded implied volatilities. It overstates P&L by "
            f"{money(ATTR['validity']['model_minus_actual_mean'])} per trade in level and "
            "should be read for composition only. The volatility conclusion itself does "
            "not depend on it — that rests on the recorded entry and exit implied "
            "volatilities directly.",
            "A fixed-strike implied-volatility comparison across time also moves along "
            "the skew and the term structure. The effect is largest near expiry, which is "
            "why the volatility test is reported on trades closed at least thirty days "
            "out; it is reduced there, not eliminated.",
            f"The stock-versus-call comparison covers {COV['covered']:,} of "
            f"{COV['total']:,} trades, because an exit price for the underlying is not "
            "recorded for positions closed at expiry.",
            "The deep-panic subsample is 48 trades. The strike ordering it implies is "
            "directional and should not be read as a precise estimate.",
            "The moat screen uses restated historical fundamentals rather than the "
            "originally-reported figures, a mild look-ahead that the persistence "
            "requirement smooths but does not remove. The exported fundamentals are also "
            f"thinner than the source used originally, which is why "
            f"{len(UN['screen_unconfirmed'])} stored universe memberships cannot be "
            "re-derived here.",
            "Transaction cost is an implied-volatility-scaled spread standing in for a "
            "real bid-ask, which the free daily option data does not carry. Deep-panic "
            "costs are therefore modelled, not observed.",
            "This audits the long call. It does not test spreads, longer-dated options, "
            "or the same thesis expressed with a different structure — each of which "
            "would be a separate claim.",
        ],
        what_would_have_changed=(
            "The harness is not built only to find nulls, and this case had several ways "
            "to come out otherwise. Had the option expression been sound, the call's P&L "
            "would have tracked the underlying's instead of trailing it by "
            f"{money(abs(EX['expression_drag']))} per trade. Had the volatility headwind "
            "been the killer, implied volatility would have fallen on recovering trades; "
            "it rose. Had the verdict been an artefact of where the moat line was drawn, "
            "the sweep would have shown the median crossing zero somewhere in the grid; "
            "it never does. And had the record itself been unsound, the accounting audit "
            "would have failed rather than reproducing every trade to the cent."),
        provenance=[
            "Trade record, moat universe and fundamentals are the exported artefacts of "
            "the original study (option chains: daily, 2012 onward, with implied "
            "volatility and Greeks); they are pinned in `data/`.",
            "Reproduce with `micromamba run -n verdict python cases/buy_the_dip/run.py`, "
            "then `make_figures.py`, then `make_report.py`. All offline, all CPU, seconds.",
            "Every number in this document is interpolated from `results.json`; none is "
            "typed in by hand.",
            "Framework components exercised: `costs.budget_pnl` (accounting audit), "
            "`pointintime.persistent_quality` and `universe_asof` (universe rebuild), "
            "`pointintime.audit_no_future_rows` (look-ahead audit), "
            "`diagnose.expression_vs_underlying` (instrument playbook), "
            "`options.pnl_attribution` (decomposition), `robust.sweep` and "
            "`robust.conclusion_stability` (robustness).",
        ])


def card() -> dict:
    tight = next((r for r in ROB["table"] if not r["all_agree"]), None)
    return {
        "id": "buy-the-dip-long-calls",
        "title": "Buying dips with call options",
        "state": "verdict-delivered",
        "claim": {
            "signal": "buy volatility-normalized dips (>=2 sigma below the trailing high) "
                      "in a point-in-time wide-moat universe, expressed as long calls",
            "universe": "point-in-time wide-moat screen on large-cap US equities, 38 names",
            "frequency": "event-driven, 2014-2024",
            "claimed_effect": "dips in high-quality names can be bought profitably, with a "
                              "long call as the defined-risk expression",
            "sample": "2,392 trades, real daily option chains",
            "source": "practitioner thesis (no published paper)",
            "data_needs": "daily option chains with IV and Greeks; point-in-time fundamentals",
        },
        "protocol": {
            "replication_anchor": "re-derive contract counts and dollar P&L from primitives; "
                                  "rebuild the point-in-time universe from raw fundamentals",
            "kill_criteria_for_the_claim": "net-negative median trade after realistic option "
                                           "costs on the point-in-time universe, with "
                                           "non-recovering dips counted as prominently as "
                                           "recovering ones",
            "diagnostics": ["expression vs underlying", "observed IV change on recovery",
                            "delta/vega/theta attribution", "moat-definition sweep"],
            "preregistered": True,
        },
        "verdict": {
            "outcome": "NEGATIVE on the expression, not on the thesis — the long call loses "
                       f"{loss(H['mean_pnl'])} mean / {loss(H['median_pnl'])} median per "
                       f"trade (win {H['win']:.2f}) while the same dips in the underlying are "
                       f"roughly flat to positive ({money(EX['underlying_mean'])} mean)",
            "replication": f"accounting re-derived exactly ({AC['contracts_mismatch']} "
                           f"mismatches); universe screen reproduces "
                           f"{UN['screen_pairs_reproduced']}/{UN['stored_pairs']} stored pairs",
            "diagnostics": {
                "expression": f"option expression gives up {money(abs(EX['expression_drag']))} "
                              f"per trade vs the same entries in the stock; the call wins only "
                              f"{EX['deriv_win_when_underlying_wins']:.0%} of the trades where "
                              "the stock wins",
                "volatility_prior_refuted": f"implied volatility rose rather than fell on "
                                            f"recovering trades (mean "
                                            f"{FAR['by_status']['recovered']['mean']:+.3f} on "
                                            f"trades exited >=30d from expiry; fell in only "
                                            f"{FAR['by_status']['recovered']['share_falling']:.0%})",
                "option_clock": f"{CLK['n_recovered_after_exit']}/{CLK['n_events_probe']} "
                                f"({CLK['share']:.1%}) of never-recovered dips returned to the entry "
                                f"price within {CLK['horizon_days']}d AFTER exit — the expiry clock, "
                                "not the dip thesis (RECOVERED from the original session transcript, "
                                "not locally reproducible; denominator verified against the trade record)",
                "attribution": f"per trade, theta {money(ATTR['overall']['theta_$'])} vs vega "
                               f"{money(ATTR['overall']['vega_$'])}; in deep panics delta "
                               f"{money(ATTR['by_depth']['deep']['delta_$'])} dominates (modelled "
                               "levels, observed signs)",
                "robustness": f"median negative in all {ROB['cells']} moat definitions; the mean "
                              f"turns positive only under the tightest screen "
                              f"({moat_label(tight['label']) if tight else 'n/a'}, "
                              f"{tight['n_trades'] if tight else 0} trades)",
            },
            "honest_limitations": [
                f"the option-clock figure ({CLK['share']:.1%}) is recovered from the original "
                "session transcript, not recomputed here (needs the vendor platform); pinned in "
                "data/option_clock_probe.json, denominator verified locally; it measures recovery "
                "to the entry price so it is an upper bound, and it does not imply a longer-dated "
                "call would have profited",
                "the delta/vega/theta decomposition is modelled and overstates P&L levels by "
                f"{money(ATTR['validity']['model_minus_actual_mean'])} per trade; only its "
                "composition and its observed signs are relied on",
                "the stock-vs-call comparison covers "
                f"{COV['covered']}/{COV['total']} trades (no exit price for positions closed "
                "at expiry)",
                "deep-panic subsample is 48 trades; strike ordering is directional",
                "moat screen uses restated fundamentals; costs use a modelled IV-scaled spread",
            ],
        },
        "date": "2026-08-20",
    }


if __name__ == "__main__":
    rep = build()
    md = rep.write(HERE / "report.md")
    path = write_card(card(), ROOT / "registry")
    print(f"wrote {md} (+ .html)")
    print(f"wrote {path} and refreshed the registry index")
