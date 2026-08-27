#!/usr/bin/env python3
"""Generate the volatility-harvesting verdict document and registry card.

  micromamba run -n verdict python cases/vol_harvest/make_report.py
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
P, SEL, W = R["premise"], R["selection"], R["win_rate_vs_profit"]
FEA, DG, FC, MV = R["feasibility"], R["delta_gradient"], R["friction_cliff"], R["model_vs_reality"]
G = R["grids"]
PICK = SEL["selected"]
TRADED = [r for r in MV["rows"] if r["real_chain_cagr_pct"] is not None]
BEST_MODEL = next(r for r in TRADED if "45-delta" in r["config"])
OTHER = next(r for r in TRADED if "25-delta" in r["config"])


def build() -> VerdictReport:
    w15 = next(r for r in FEA["by_width"] if r["width_pct"] == 1.5)
    w30 = next(r for r in FEA["by_width"] if r["width_pct"] == 3.0)
    w10 = next(r for r in FEA["by_width"] if r["width_pct"] == 1.0)

    premise = f"""
Most audits in this library begin with a claim that turns out to rest on nothing. This one
begins with a premise that is true. Implied volatility exceeds subsequently realized
volatility by about {P['vrp_mean_vol_points']} volatility points on average and does so
about {P['vrp_share_positive']:.0%} of the time. Sellers of index options are paid a real
premium for bearing a real risk.

The claim under audit is the step everyone takes next: that a small account can therefore
harvest it, using defined-risk spreads so that a crash costs a capped amount rather than
the account. The claim is not that the premium exists. It is that it is reachable from
here, after costs, at this size.

The evidence is a modelled search over {G['phase1_configs'] + G['phase2_configs']}
configurations — strike, width, stop rule, holding period, entry filters, priced with a
model rather than with real quotes — and then the three configurations that were carried
to real option chains with conservative fills.
""".strip()

    selection = f"""
The source study wrote its selection rule down before inspecting the grid: keep only
configurations that still traded at least {10} times after 2021 and had positive
expectancy, then rank by Sharpe. Re-executing that rule here on the ungated
configurations leaves {SEL['n_eligible']} eligible out of {SEL['n_configs_ungated']}, and
ranks first the **{PICK['delta']:.2f}-delta, {PICK['width_pct']}%-wide** configuration
(Sharpe {PICK['sharpe']:.2f}, ${PICK['expectancy_usd']:.1f} per trade).

The configuration actually carried forward was the {BEST_MODEL['config'].split(' / ')[0]}
at **1.5% width** — the runner-up. The reason is documented in the source study and it is
a good one: the 2.0% width traded only
{next(r['n_trades_post2021'] for r in SEL['ranking'] if r['width_pct'] == 2.0)} times after
2021 against
{next(r['n_trades_post2021'] for r in SEL['ranking'] if r['width_pct'] == 1.5)} for the
1.5%, and its entries had stopped well before the sample ended, so the higher Sharpe was
being earned in an intermittent window that a live account could not rely on. Both were
eventually tested against real chains anyway.

It is still a discretionary override of a pre-registered rule, and this audit records it
as one. The override was conservative, it was disclosed, and it did not change the
verdict — which is the most that can be said for any deviation, and worth saying plainly
rather than leaving the reader to assume the rule ran unaided.
""".strip()

    laws = f"""
Two structural findings come out of the grid, and neither depends on which configuration
was picked.

**A high win rate is not profit.** Across all {W['n_configs']} configurations the
correlation between win rate and expectancy is only {W['corr_pearson']:+.2f}. Of the
{W['n_win_rate_over_85']} configurations that win at least 85% of their trades,
{W['share_of_those_losing']:.0%} lose money. The highest win rate in the entire grid is
{W['best_win_rate']:.1f}% — and it earns ${W['expectancy_at_best_win_rate']:+.1f} per
trade. Selling far out-of-the-money options buys a long run of small wins at the price of
occasional losses that erase them, and the win rate is the number that hides it.

**Position granularity decides what is tradable, and it works against the account.** A
small account sizing to a fixed maximum loss per trade can only sell so wide before a
single contract breaches the risk budget. Mean expectancy rises monotonically with
width — {w10['mean_expectancy']:+.1f} dollars at 1.0%, {w15['mean_expectancy']:+.1f} at
1.5%, {w30['mean_expectancy']:+.1f} at 3.0% — while the number of trades the account can
actually take collapses in the opposite direction, from
{w10['mean_post2021_trades']:.0f} after 2021 down to {w30['mean_post2021_trades']:.0f}.
The widths that would pay are the widths this account can no longer trade.

![The granularity tradeoff](results/fig2_granularity.png)
""".strip()

    friction = f"""
The modelled winner earns ${FC['expectancy'][1]:+.1f} per trade at the assumed friction of
{FC['assumed_in_the_grid']:.2f} index points per leg. Sweep that assumption and the number
does not degrade gracefully — it crosses zero at
**{FC['breakeven_points_per_leg']:.3f} points per leg**, which is
{FC['headroom_points']:.3f} points of headroom above what was assumed, and reaches
${FC['expectancy'][2]:+.1f} at a tenth of a point.

The entire edge lives inside the first nickel of transaction cost. That is not a
robustness caveat; it is the finding. A strategy whose profitability is decided by
whether the effective spread is five cents or eight is not a strategy with a thin margin,
it is a strategy whose margin *is* the spread assumption — and no model can settle a
spread assumption. Only quotes can.

![The friction cliff](results/fig1_friction_cliff.png)
""".strip()

    reality = f"""
Three configurations were run against real chains with conservative fills — selling at
the bid and buying at the ask, which is what a small account actually receives.

| configuration | modelled | real chains |
|---|---|---|
| {BEST_MODEL['config']} | {BEST_MODEL['modelled']['cagr_pct']:+.1f}% CAGR, ${BEST_MODEL['modelled']['expectancy_usd']:+.1f}/trade | **{BEST_MODEL['real_chain_net_pct']:+.1f}% net, {BEST_MODEL['real_chain_cagr_pct']:+.2f}% CAGR** |
| {OTHER['config']} | {OTHER['modelled']['cagr_pct']:+.1f}% CAGR, ${OTHER['modelled']['expectancy_usd']:+.1f}/trade | **{OTHER['real_chain_net_pct']:+.1f}% net, {OTHER['real_chain_cagr_pct']:+.2f}% CAGR** |

The ranking inverted. The configuration the model ranked as the only feasible positive
one in the whole search was the *worst* of those traded, by a factor of three. A
single-leg variant with the least friction of any structure in the family reached a
{[r for r in json.loads((HERE/'data'/'realchain_results.json').read_text())['runs'] if 'put-write' in r['config']][0]['cagr_pct']:+.1f}%
CAGR and still underperformed cash — an upper bound on the whole family, established
independently.

![Modelled versus real](results/fig3_model_vs_reality.png)

Why the model ranked it best is also why reality ranked it worst. A near-the-money short
leg collects the most premium, which is what the model rewards; it is also the most often
breached and, in a narrow spread, the one that pays the most bid-ask relative to the
credit collected. The model priced the premium and could not price the execution.
""".strip()

    return VerdictReport(
        title="Harvesting the Volatility Risk Premium at Retail Scale",
        claim=("The volatility risk premium is real and persistent, so a small account can "
               "harvest it by systematically selling defined-risk index option spreads — "
               "capped loss, high win rate, a premium collected for bearing a risk that "
               "usually does not materialize."),
        verdict=(f"Falsified. The premise holds and the conclusion does not follow. On real "
                 f"option chains with conservative fills the model's own chosen "
                 f"configuration returned {BEST_MODEL['real_chain_net_pct']:+.1f}% net "
                 f"({BEST_MODEL['real_chain_cagr_pct']:+.2f}% CAGR) against a modelled "
                 f"{BEST_MODEL['modelled']['cagr_pct']:+.1f}%, and every configuration "
                 f"tested was negative. The mechanism is not bad luck: the modelled edge "
                 f"crosses zero at {FC['breakeven_points_per_leg']:.3f} index points of "
                 f"friction per leg, so the entire result was living inside a spread "
                 f"assumption that only real quotes could settle. A true premise, a real "
                 f"premium, and no way to reach it from here."),
        sections=[("A premise that is actually true", premise),
                  ("Re-executing the selection rule", selection),
                  ("Two structural findings from the grid", laws),
                  ("The friction cliff", friction),
                  ("Modelled prices against real chains", reality)],
        honest_limitations=[
            "The real-chain results are recorded, not recomputed here. They were produced on "
            "the data vendor's backtesting platform and the raw logs were not saved to the "
            "source repository; the figures come from that project's stated authority "
            "documents and are pinned in `data/realchain_results.json`. This case can "
            "re-derive the modelled grid's structure but not the adjudicating runs.",
            "The friction sensitivity curve is likewise a recorded table from the source "
            "study, not re-run here; the breakeven point this case computes is an "
            "interpolation of that table. Its shape is not linear, because friction changes "
            "which trades are taken as well as what they earn, so the interpolation is an "
            "approximation between measured points.",
            "The modelled prices use Black-Scholes with a fixed skew multiplier. That is "
            "adequate for ranking magnitudes and for tail structure and it is not adequate "
            "for a verdict — which is precisely what the real-chain runs demonstrated by "
            "inverting the ranking.",
            "The selection rule was re-executed and it did not pick the configuration that "
            "was carried forward; the override is documented and defensible but it is an "
            "override, and the pre-registration is weaker for it.",
            "Only three configurations were ever tested against real chains. The conclusion "
            "that the family is unharvestable rests on those three plus the friction "
            "argument, not on an exhaustive live test of all 108.",
            "The whole analysis is scaled to one small account with a fixed per-trade risk "
            "budget. The granularity findings are specific to that size and would not "
            "transfer to an account large enough to trade the wider spreads.",
            "Index level matters: the widths that were feasible depend on where the index "
            "traded during the sample, so the feasibility boundary is not a constant.",
        ],
        what_would_have_changed=(
            "The audit could have come out the other way at several points and did not. Had "
            "the premise been false, the volatility premium would not have measured "
            f"{P['vrp_mean_vol_points']} points positive {P['vrp_share_positive']:.0%} of the "
            "time — it does. Had the edge been robust rather than marginal, the friction "
            "sweep would have shown expectancy surviving to a tenth of a point — it turns "
            f"negative at {FC['breakeven_points_per_leg']:.3f}. And had the modelled prices "
            "been good enough to adjudicate, the real-chain ranking would have agreed with "
            "the modelled one instead of inverting it."),
        provenance=[
            "Pinned in `data/`: the two modelled configuration grids from the source study "
            "(72 and 36 configurations), and the recorded real-chain results plus friction "
            "sensitivity table with their provenance.",
            "Reproduce with `micromamba run -n verdict python cases/vol_harvest/run.py`, "
            "then `make_figures.py`, then `make_report.py`. Offline, CPU, seconds.",
            "Every number in this document is interpolated from `results.json`.",
            "Framework components exercised: `costs.breakeven_friction` (the cliff), "
            "`robust`-style grid aggregation for the feasibility and delta gradients, and "
            "the re-execution of the documented selection rule.",
        ])


def card() -> dict:
    return {
        "id": "retail-short-volatility",
        "title": "Harvesting the volatility premium at retail scale",
        "state": "verdict-delivered",
        "claim": {
            "signal": "systematic short defined-risk index option spreads (put credit spreads) "
                      "to harvest the volatility risk premium",
            "universe": "index options, one small account with a fixed per-trade risk budget",
            "frequency": "35-day holding period, rolling entries",
            "claimed_effect": "a real and persistent volatility risk premium can be harvested "
                              "at retail scale with capped-loss structures",
            "sample": "2007-2026 modelled grid of 108 configurations; 3 configurations run "
                      "against real option chains",
            "source": "practitioner thesis (no published paper)",
            "data_needs": "index and volatility history; real option chains for adjudication",
        },
        "protocol": {
            "replication_anchor": "re-execute the pre-registered selection rule on the modelled "
                                  "grid; recompute the friction breakeven",
            "kill_criteria_for_the_claim": "net edge at or below zero on real chains with "
                                           "conservative fills",
            "diagnostics": ["friction sensitivity and breakeven", "granularity feasibility",
                            "win-rate vs expectancy across configurations",
                            "modelled ranking vs real-chain ranking"],
            "preregistered": True,
        },
        "verdict": {
            "outcome": f"FALSIFIED — true premise, unreachable conclusion. Real chains with "
                       f"conservative fills: {BEST_MODEL['real_chain_net_pct']:+.1f}% net "
                       f"({BEST_MODEL['real_chain_cagr_pct']:+.2f}% CAGR) on the model's own "
                       f"pick, {OTHER['real_chain_net_pct']:+.1f}% on the earlier candidate; "
                       "every tested configuration negative",
            "replication": f"selection rule re-executed on the {G['phase2_configs']}-config "
                           f"grid: {SEL['n_eligible']} eligible, top by Sharpe is "
                           f"{PICK['delta']:.2f}-delta/{PICK['width_pct']}% — the runner-up was "
                           "carried forward instead, a documented discretionary override",
            "diagnostics": {
                "friction_cliff": f"modelled expectancy crosses zero at "
                                  f"{FC['breakeven_points_per_leg']:.3f} index points per leg "
                                  f"vs {FC['assumed_in_the_grid']:.2f} assumed — the entire edge "
                                  "lives inside the first nickel",
                "granularity": f"mean expectancy rises with width while tradability collapses: "
                               f"1.0% -> {next(r['mean_post2021_trades'] for r in FEA['by_width'] if r['width_pct']==1.0):.0f} "
                               f"trades after 2021, 3.0% -> "
                               f"{next(r['mean_post2021_trades'] for r in FEA['by_width'] if r['width_pct']==3.0):.0f}",
                "win_rate_vs_profit": f"corr(win rate, expectancy) = {W['corr_pearson']:+.2f}; "
                                      f"{W['share_of_those_losing']:.0%} of the "
                                      f"{W['n_win_rate_over_85']} configurations winning >=85% "
                                      f"of trades lose money; the best win rate "
                                      f"({W['best_win_rate']:.1f}%) earns "
                                      f"${W['expectancy_at_best_win_rate']:+.1f}/trade",
                "model_vs_reality": "ranking inverted — the only configuration the modelled grid "
                                    "rated feasible-and-positive was the worst of those traded",
            },
            "honest_limitations": [
                "real-chain results and the friction sensitivity table are recorded from the "
                "source study, not recomputed here (raw platform logs were not saved)",
                "modelled prices use Black-Scholes with a fixed skew multiplier — adequate for "
                "magnitudes, not for a verdict",
                "the pre-registered selection rule was overridden by a documented judgment call",
                "only 3 of 108 configurations were tested against real chains",
                "findings are specific to one small account's risk budget and the index level "
                "over the sample",
            ],
        },
        "date": "2026-08-26",
    }


if __name__ == "__main__":
    md = build().write(HERE / "report.md")
    path = write_card(card(), ROOT / "registry")
    print(f"wrote {md} (+ .html)")
    print(f"wrote {path} and refreshed the registry index")
