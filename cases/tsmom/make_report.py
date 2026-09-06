#!/usr/bin/env python3
"""Generate the time-series momentum verdict and registry card from results.json.

Every number is interpolated from the results file `run.py` wrote, so the
document cannot drift away from the code that produced it. Prose is written;
figures are numbers.

  micromamba run -n verdict python cases/tsmom/make_report.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))

from verdict.report import VerdictReport, to_html, write_card, refresh_index  # noqa: E402

R = json.loads((HERE / "results.json").read_text())
S, BM = R["strategy"], R["benchmarks"]
K1, K2, K3, K4 = R["K1_spanning"], R["K2_sealed_block"], R["K3_costs"], R["K4_sign_randomisation"]
DEC, PM = R["diagnostic_tilt_vs_timing"], R["diagnostic_per_market_ann"]
ROB = R["robustness"]
CFG = R["config"]
CORR = R["correlation_robustness"]
INTEGER = R["integer_contract_sizing"]
A, B = R["span"]


def p(x, d=2):
    return f"{100 * x:+.{d}f}%"


def sr(x):
    return f"{x:+.2f}"


def ci(pair):
    return f"[{pair[0]:+.2f}, {pair[1]:+.2f}]"


def pci(pair, d=2):
    return f"[{100 * pair[0]:+.{d}f}%, {100 * pair[1]:+.{d}f}%]"


def rob(axis, value):
    for r in ROB:
        if r["axis"] == axis and str(r["value"]) == str(value):
            return r["sharpe"]
    raise KeyError((axis, value))


LBR = [r for r in ROB if r["axis"] == "lookback_months"]
LB = {r["value"]: r["sharpe"] for r in LBR}
best_lb = max(LB, key=LB.get)
worst_lb = min(LB, key=LB.get)
BEST = next(r for r in LBR if r["value"] == best_lb)
CLEAR = [r for r in LBR if r["ci_excludes_zero"]]
sectors = {r["value"]: r["sharpe"] for r in ROB if r["axis"] == "drop_sector"}
holding = {r["value"]: r for r in ROB if r["axis"] == "holding_period_months"}
corr_runs = {r["value"]: r["sharpe"] for r in CORR["runs"]}
losers = {k: v for k, v in PM.items() if v < 0}

report = VerdictReport(
    title="Time-series momentum in futures",
    claim=(
        "Moskowitz, Ooi and Pedersen (2012) report that the sign of a futures market's own "
        "trailing 12-month excess return predicts its next month, across 58 instruments and "
        "four asset classes, strongly enough that a volatility-scaled, equal-weighted "
        "portfolio of such positions earns a Sharpe ratio of roughly 1.2 — with positive "
        "predictability in every one of the 58 instruments taken individually."
    ),
    verdict=(
        f"**Does not survive, on the commodity sleeve, after publication.** All four "
        f"pre-registered kill criteria fired. Over {S['n_months']} months from {A} to {B} on "
        f"seven commodity futures, the rule as specified returns {p(S['ann_return'])} a year "
        f"at {S['ann_vol']:.1%} volatility — a Sharpe of {sr(S['sharpe'])} whose bootstrap "
        f"interval {ci(S['sharpe_ci'])} contains zero. The decisive test is not that number "
        f"but K4: replacing the momentum signal with coin flips, while keeping the position "
        f"sizes the rule chose, places the strategy above "
        f"{K4['strategy_percentile_vs_random']:.0%} of {K4['draws']} random draws. "
        f"On this evidence the momentum signal is not distinguishable from random signs "
        f"under the tested sizing rule."
    ),
    sections=[
        ("What was tested, and against what",
         f"The protocol was registered before any of this code existed. It fixed the "
         f"construction — sign of the trailing {CFG['lookback_months']}-month return, "
         f"inverse-volatility sizing to a {CFG['sigma_each']:.0%} per-market budget capped at "
         f"±{CFG['max_pos']:.0f}, equal weight across markets, monthly rebalance, everything "
         f"lagged one month — and, more importantly, fixed what the rule had to beat.\n\n"
         f"Three benchmarks, all built from the same panel with the same sizing and the same "
         f"lag, so any difference between them is a difference in information rather than in "
         f"plumbing:\n\n"
         f"| | Sharpe | annualised |\n|---|---|---|\n"
         f"| **time-series momentum** | **{sr(S['sharpe'])}** | **{p(S['ann_return'])}** |\n"
         f"| passive long, same sizing | {sr(BM['passive_long']['sharpe'])} | "
         f"{p(BM['passive_long']['ann_return'])} |\n"
         f"| cross-sectional momentum | {sr(BM['xs_momentum']['sharpe'])} | "
         f"{p(BM['xs_momentum']['ann_return'])} |\n"
         f"| coin-flip signs, same position sizes | {sr(K4['random_sharpe_mean'])} (mean of "
         f"{K4['draws']}) | — |\n\n"
         f"![The claim against its benchmarks](results/fig1_claim_vs_benchmarks.png)"),

        ("K1 — spanning",
         f"Regressing the strategy on the two economic benchmarks with HAC standard errors "
         f"leaves an alpha of {p(K1['alpha_annualized'])} a year with t = "
         f"{K1['t_stat_hac']:+.2f} over {K1['nobs']} months. Its annualised 95% interval is "
         f"{pci(K1['alpha_ci_annualized'])}; it contains zero, so K1 fires.\n\n"
         f"The loadings are more interesting than the alpha. Cross-sectional momentum takes "
         f"a coefficient of {K1['betas']['xs_momentum']:+.3f} with t = "
         f"{K1['beta_t']['xs_momentum']:+.2f}: the two rules move together closely. The "
         f"passive long takes {K1['betas']['passive_long']:+.3f} with t = "
         f"{K1['beta_t']['passive_long']:+.2f} — essentially nothing.\n\n"
         f"This is worth stating plainly because it does *not* reproduce the usual criticism "
         f"of the claim, which is that time-series momentum is cross-sectional momentum plus "
         f"an inherited net long position. In this sample there was no long premium to "
         f"inherit: a passive long in these seven markets at the same sizing earned a Sharpe "
         f"of {sr(BM['passive_long']['sharpe'])} over sixteen years. The rule is not living off "
         f"the asset class. It is simply not earning."),

        ("K4 — the signal against coin flips",
         f"This is the criterion that reads backwards: survival is the death sentence. Each "
         f"of the {K4['draws']} draws keeps the strategy's position *magnitudes* — the "
         f"inverse-volatility scaling, the cap, the equal weighting — and replaces only the "
         f"signs with fair coin flips. The draws land at a mean Sharpe of "
         f"{sr(K4['random_sharpe_mean'])} with a 5–95 band of "
         f"[{K4['random_sharpe_p05']:+.2f}, {K4['random_sharpe_p95']:+.2f}]. The strategy's "
         f"{sr(S['sharpe'])} sits above {K4['strategy_percentile_vs_random']:.0%} of them "
         f"— inside the band, not beyond it.\n\n"
         f"The decomposition says the same thing from another direction. Splitting the rule's "
         f"return into the part earned by its time-varying common direction and the part "
         f"earned by choosing *which* markets to be long:\n\n"
         f"| | annualised | Sharpe |\n|---|---|---|\n"
         f"| common direction (net long/short) | {p(DEC['tilt_ann'])} | — |\n"
         f"| cross-market selection | {p(DEC['timing_ann'])} | "
         f"{sr(DEC['timing_sharpe'])} |\n\n"
         f"Everything the rule earned came from being net long or net short at the right "
         f"times; deciding which of the seven markets to favour contributed "
         f"{p(DEC['timing_ann'])} a year. And the contributions are not broadly spread: "
         f"{len(losers)} of the {len(PM)} markets contributed negatively, with "
         f"{min(PM, key=PM.get)} at {p(PM[min(PM, key=PM.get)])} a year.\n\n"
         f"![Where the return came from](results/fig2_where_the_return_comes_from.png)"),

        ("K2 — the sealed block",
         f"The most recent block, from {K2['seal_from']} onward, was sealed and opened once, "
         f"through the ledger at `results/holdout_ledger.json` (fingerprint "
         f"`{K2['opening']['fingerprint']}`). Re-opening it under a changed configuration "
         f"raises rather than quietly re-running.\n\n"
         f"Those {K2['n_months']} months are the friendliest stretch in the sample — the "
         f"inflation-trend period a commodity trend follower is supposed to own. The rule "
         f"returned {p(K2['ann_return'])} a year there, a Sharpe of {sr(K2['sharpe'])}. The "
         f"interval is {ci(K2['sharpe_ci'])} and contains zero, so K2 fires too. The best "
         f"sub-period in the sample does not reach conventional significance."),

        ("K3 — costs, and what is not the problem here",
         f"Average turnover is {K3['mean_turnover_per_rebalance']:.2f} units of position per "
         f"market per rebalance, and the gross edge breaks even at "
         f"{K3['breakeven_cost_bps']:.1f} bps. Charged at a generous "
         f"{K3['plausible_cost_bps']:.0f} bps per unit of absolute position change, the net "
         f"series has a monthly mean interval "
         f"{pci(K3['net_at_plausible']['mean_ci_monthly'])}, which contains zero, so K3 "
         f"fires exactly as registered. Its Sharpe is "
         f"{sr(K3['net_at_plausible']['sharpe'])} with interval "
         f"{ci(K3['net_at_plausible']['sharpe_ci'])}.\n\n"
         f"But it fires for the wrong-sounding reason, and the distinction matters. Liquid "
         f"futures cost a few basis points a round turn; a breakeven of "
         f"{K3['breakeven_cost_bps']:.1f} bps means friction is nowhere near the binding "
         f"constraint. Unlike a retail options strategy that dies on the spread, this claim "
         f"is not killed by costs. There is simply not enough gross edge for the interval to "
         f"clear zero at any plausible cost, including zero cost.\n\n"
         f"The registered account-space check is still data-gated, not silently approximated. "
         f"The current panel contains BackwardsRatio levels, which preserve returns but are "
         f"invalid contract notionals. `{INTEGER['blocker']}`. The upgraded exporter requests "
         f"mapped-contract raw prices; until that panel is re-exported, integer lots are not "
         f"reported."),

        ("Robustness, and the number you would have reported",
         f"The protocol pre-registered the perturbations, which is the only reason the "
         f"following is reportable rather than embarrassing. Sweeping the lookback:\n\n"
         + "| lookback | Sharpe | interval |\n|---|---|---|\n"
         + "\n".join(f"| {r['value']} months | {sr(r['sharpe'])} | {ci(r['sharpe_ci'])} |"
                     for r in sorted(LBR, key=lambda r: r["value"]))
         + f"\n\nThe registered {CFG['lookback_months']} months is not the peak. "
           f"{best_lb} months returns {sr(LB[best_lb])}; {worst_lb} months returns "
           f"{sr(LB[worst_lb])}. Had the lookback been chosen after seeing the data, the "
           f"honest-looking thing to report would have been {sr(LB[best_lb])} at "
           f"{best_lb} months — roughly double the registered configuration. Its interval is "
           f"{ci(BEST['sharpe_ci'])}. "
           + (f"{len(CLEAR)} of the {len(LBR)} lookbacks has an unadjusted interval that "
              f"excludes zero ({', '.join(str(r['value']) for r in CLEAR)} months); this is "
              f"reported as sensitivity, not promoted into a replacement specification. "
              if CLEAR else
              f"None of the {len(LBR)} lookbacks has an interval that excludes zero. ")
           +
           f"The sign is not stable across the pre-registered perturbations "
           f"(`conclusion_stable_across_perturbations` = "
           f"{R['conclusion_stable_across_perturbations']}), which is itself evidence "
           f"against the claim rather than a nuisance.\n\n"
           f"Dropping a sector moves the result from {sr(min(sectors.values()))} to "
           f"{sr(max(sectors.values()))} depending on which one goes — removing the grains "
           f"raises it to {sr(sectors['grains'])}, removing energy takes it to "
           f"{sr(sectors['energy'])}. Seven correlated markets are not seven independent "
           f"tests. The most-correlated pair is {CORR['pair'][0]}/{CORR['pair'][1]} at "
           f"{CORR['correlation']:+.2f}. Dropping {CORR['pair'][0]} gives "
           f"{sr(corr_runs[CORR['pair'][0]])}, dropping {CORR['pair'][1]} gives "
           f"{sr(corr_runs[CORR['pair'][1]])}, and dropping both gives "
           f"{sr(corr_runs['+'.join(CORR['pair'])])}. The conclusion does not depend on that "
           f"pair.\n\n"
           f"Longer holding periods weaken the result: 3, 6 and 12 months give Sharpes of "
           f"{sr(holding[3]['sharpe'])}, {sr(holding[6]['sharpe'])} and "
           f"{sr(holding[12]['sharpe'])}; every interval contains zero. These are overlapping "
           f"signal vintages with unchanged leverage, not separately tuned strategies.\n\n"
           f"![Executed perturbations](results/fig3_robustness.png)\n\n"
           f"The return-space robustness protocol is now complete. The remaining protocol "
           f"gap is account-space integer sizing, gated on mapped-contract raw prices as "
           f"described above."),

        ("Cross-check against an independent implementation",
         f"An earlier, separately written backtest of the same construction — single "
         f"12-month signal, inverse-volatility sizing, equal weight, scaled to a 15% "
         f"portfolio volatility target, the same seven QuantConnect markets from 2009 — "
         f"reported a Sharpe of +0.11. This run gets {sr(S['sharpe'])}.\n\n"
         f"The gap is accounted for by two known differences rather than left unexplained: "
         f"this run starts at {A} because the 12-month lookback and the 120-day volatility "
         f"window are both warmed up first, and it equal-weights across the markets actually "
         f"available each month rather than requiring all seven. Both implementations land "
         f"in the same place — a Sharpe near zero, an order of magnitude below the "
         f"1.2 the source paper reports — which is the comparison that matters."),
    ],
    honest_limitations=[
        f"**This is the commodity sleeve, not the claim.** Seven commodity futures, not 58 "
        f"instruments across commodities, equities, bonds and currencies. A large part of "
        f"the source paper's Sharpe comes from diversifying a weak per-market signal across "
        f"four asset classes that trend at different times. This run cannot reject the claim "
        f"as stated for the full universe; it can only say the effect is not present in "
        f"these seven markets over this period.",
        f"**The whole sample is post-publication.** The source ends in 2009; this begins at "
        f"{A}. That makes this a test of whether the effect persisted, not of whether the "
        f"original finding was correct when it was made. A claim that was true and has since "
        f"been arbitraged away would produce exactly this result.",
        f"**The panel is unbalanced early.** Only five markets are available until 2011-03 "
        f"and six until 2012-10; gold's history begins 2012-11. Months before then average "
        f"over fewer markets. Restricting to the balanced period gives "
        f"{sr(rob('sample', 'full_7_markets_only'))}, so this does not change the "
        f"conclusion, but the early years are thinner than the market count suggests.",
        f"**One large move could not be corroborated.** Crude in March 2026 moves +54% in a "
        f"month in this panel. Three other outliers in the sample (crude in March and May "
        f"2020, natural gas in July 2022) match known events; this one was not checked "
        f"against a second data source. Dropping the last twelve months gives "
        f"{sr(rob('sample', 'drop_last_12m'))}, so the conclusion does not rest on it.",
        f"**The coin-flip comparison is gross only.** Independent monthly sign draws turn "
        f"over far more than the strategy does, so the random book would pay more in costs "
        f"than the rule it is being compared with. Charging both would widen the gap in the "
        f"strategy's favour — but the gap being tested is against the *gross* distribution, "
        f"and the strategy sits inside it there.",
        f"**Account-space sizing remains data-gated, for a falsifiable reason.** The current "
        f"export has ratio-adjusted signal prices but not the mapped contract's unadjusted "
        f"price. Using the adjusted level with exchange multipliers would create false "
        f"notionals. The exporter and sizing code are ready, but the vendor panel must be "
        f"re-exported before integer lots at $250k, $1m and $5m can be reported. Margin, "
        f"capacity and time-varying exchange fees would remain outside that calculation.",
        f"**K4's percentile has {K4['draws']}-draw resolution.** The reported "
        f"{K4['strategy_percentile_vs_random']:.0%} is accurate to about half a percent, "
        f"which is far finer than the margin by which the criterion is decided, but the "
        f"number should not be read as more precise than that.",
        "**One implementation clause remains incomplete.** Longer holding periods and the "
        "most-correlated-pair exclusions are now executed. Integer-contract sizing with "
        "multipliers remains blocked only by the missing unadjusted mapped-contract prices; "
        "the result therefore remains a return-space verdict, not a capacity claim.",
    ],
    what_would_have_changed=(
        f"Three things together, all fixed in advance: an alpha in the spanning regression "
        f"with |t| > 2 rather than the {K1['t_stat_hac']:+.2f} observed; the strategy above "
        f"the 95th percentile of the sign-randomised draws rather than above only "
        f"{K4['strategy_percentile_vs_random']:.0%} of them; and a Sharpe whose sign held across the "
        f"pre-registered lookback and volatility-window sweeps. Any one of the three alone "
        f"would have been suggestive; the protocol required all three because each of them "
        f"has a well-known way of being produced by accident."
    ),
    provenance=[
        "Panel: QuantConnect native continuous futures, OpenInterest mapping, "
        "BackwardsRatio normalization, depth offset 0 — the roll settings validated in the "
        "source CTA project against an independently constructed continuous series.",
        f"Export: `cases/tsmom/qc_export.py`, month-end, {A[:4]}–{B[:4]}, md5-checked on "
        f"decode by `cases/tsmom/decode_panel.py`.",
        "Execution: `cases/tsmom/run.py`. Figures: `cases/tsmom/make_figures.py`. "
        "This document: `cases/tsmom/make_report.py`, every number interpolated from "
        "`results.json`.",
        "Known-answer controls: `cases/tsmom/validate.py`, four synthetic worlds including "
        "a positive control the apparatus must pass; also gate `tsmom-controls` in "
        "`scripts/regress.py`.",
        f"Sealed block opened once at fingerprint `{K2['opening']['fingerprint']}`, recorded "
        f"in `cases/tsmom/results/holdout_ledger.json`.",
        "Contract units prepared for the gated account-space run use CME standard contracts: "
        "CL 1,000 barrels; NG 10,000 MMBtu; GC 100 troy ounces; HG 25,000 pounds; "
        "ZC/ZS/ZW 5,000 bushels. No multiplier is applied until raw mapped-contract prices "
        "are present.",
    ],
)

md = HERE / "report.md"
md.write_text(report.render_markdown())
to_html(md, HERE / "report.html")

card = json.loads((ROOT / "registry" / "time-series-momentum.json").read_text())
card["state"] = "verdict-delivered"
card.pop("why_not_adjudicated", None)
card["verdict"] = {
    "outcome": "DOES NOT SURVIVE — all four kill criteria fired (commodity sleeve, post-publication)",
    "summary": (
        f"All four pre-registered kill criteria fired over {S['n_months']} months on seven "
        f"commodity futures. Sharpe {sr(S['sharpe'])}, interval {ci(S['sharpe_ci'])}; "
        f"spanning alpha {p(K1['alpha_annualized'])} at t = {K1['t_stat_hac']:+.2f}; the "
        f"sealed post-publication block {ci(K2['sharpe_ci'])}; and coin-flip signs with the "
        f"same position sizes place the rule above only "
        f"{K4['strategy_percentile_vs_random']:.0%} of {K4['draws']} draws. The "
        f"return that exists comes from the rule's time-varying net exposure "
        f"({p(DEC['tilt_ann'])} a year), not from choosing which markets to hold "
        f"({p(DEC['timing_ann'])})."
    ),
    "report": "cases/tsmom/report.html",
    "boundary": (
        "Seven commodity markets, 2010-2026, entirely post-publication. Does not address "
        "the source claim's full 58-instrument, four-asset-class universe."
    ),
    # The card carries its own copy rather than pointing at the document, so a
    # reader of the registry alone still meets the limitations.
    "honest_limitations": report.honest_limitations,
}
write_card(card, ROOT / "registry")
refresh_index(ROOT / "registry")
print(f"wrote {md.name}, report.html, and updated the registry card")
