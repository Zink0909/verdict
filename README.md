# verdict

**[The claim register →](https://zink0909.github.io/verdict/registry.html)**

A validation harness for time-series prediction claims — and a case library of claims
put through it.

Predictive claims are cheap to make and expensive to check. Checking one properly means
the same unglamorous discipline every time: build the data as it stood at the time, split
only by time, seal a block and open it once, benchmark against what you already had,
price the frictions, perturb the definitions, and — when the answer is no — find out
*which* mechanism said no. `verdict` is that discipline as code, extracted from four
completed studies, plus the verdicts those studies produced.

Three of the four case verdicts are negative, one is a mechanical explanation of somebody
else's positive, and none of them is a story about a strategy that worked. That is not an
accident of the sample: a harness that can only confirm is not a harness, and every
component here ships with a control proving it can detect an effect that is really
present.

```bash
micromamba env create -f environment.yml
micromamba run -n verdict pip install -e .

micromamba run -n verdict streamlit run app.py          # the working surface
micromamba run -n verdict python scripts/regress.py     # 61 known-answer gates, seconds
micromamba run -n verdict python scripts/run_case.py --all --verify
micromamba run -n verdict python scripts/audit_integrity.py
```

## The working surface

`app.py` is the way in — four screens, no code required:

| | |
|---|---|
| **The register** | every claim that has been adjudicated, its protocol, its verdict, its limitations |
| **Audit a paper** | paste or upload a `.txt`, `.md`, or `.pdf` paper; extract a Claim Card, pre-register a protocol, approve it, then execute through a matching provider, a clearly bounded return/benchmark CSV evaluation, or stop honestly at data-gated |
| **Evidence vault** | inspect, hash-verify, compare, and export local approved paper-audit packages without silently promoting them to the public register |
| **New claim** | fill in a claim card and pre-register a local protocol draft. The cheapest thing the system does: if you cannot write a result that would falsify the claim, the claim is not testable and you have saved yourself the weeks you were about to spend. A draft is not silently published into the evidence register |
| **Evaluate a result** | point at a return series and get the battery — bootstrap interval, spanning, cost sensitivity, breakeven cost, the diagnosis playbooks, the sealed-holdout ledger, and a verdict document that will not render without limitations |
| **The agent** | watch the loop run end to end |

The interface computes nothing. It collects inputs, calls the library, and shows what came
back — so there is one source of truth, and it is the part with the tests.

## A three-minute demo

Open the public [system overview](https://zink0909.github.io/verdict/) first, then follow
the [guided tour](https://zink0909.github.io/verdict/demo.html): system origin → claim
register → one evidence case → recorded Agent loop. For a live demo, run
`micromamba run -n verdict streamlit run app.py` and use **Start here**. It guides a viewer
through a local protocol draft, the deterministic CSV evaluation battery, and the Agent
boundary. The interactive surface is research infrastructure, not a trading interface.

For a presentation-ready route, use the public
[portfolio briefing](https://zink0909.github.io/verdict/portfolio.html). It gives a bounded
five-minute path: four source studies → reusable constraints → evidence register → local
interactive proof → explicit research boundaries.

For a paper audit, use **Audit a paper**. The offline Complexity walkthrough works without
credentials and visibly labels the model turns as a fixture. To process a new paper, install
the optional Agent dependency (`micromamba run -n verdict pip install anthropic`) and configure
its API credentials; PDF-to-text support is included in `environment.yml`. If you have a dated
CSV with `date`, `return`, and optional numeric benchmark columns, the CSV route calculates
descriptive return, bootstrap, spanning, and cost-sensitivity outputs — but explicitly does
not reproduce the paper's strategy or validate its source/PIT data. Every approved audit is
saved locally under `.verdict-workspace/audits/` as a hashed evidence package (paper text,
claim, protocol, approval, tool trace, outcome, and supplied CSV); it is not silently published
to the public register. A new paper without a matching data/provider adapter ends as
`protocol-ready-data-gated`, never as an invented verdict.

For privacy, new-paper extraction sends pasted/uploaded text to the configured Anthropic API;
do not supply confidential or restricted material. The offline Complexity walkthrough does not
make that external model call.

Open **Evidence vault** after an audit to verify every declared artifact, review the Claim,
Protocol, Outcome and tool trace, download a portable ZIP, or compare two approved audit
records. A hash mismatch fails closed: the package stays visible as invalid but cannot be
opened as verified evidence.

## The case library

| Case | Claim under audit | Verdict |
|---|---|---|
| [`cases/chart_cnn`](cases/chart_cnn) | Jiang–Kelly–Xiu chart-image CNN: price-chart features add information beyond the large-cap book's existing factors | **Negative in the tested setting.** Validation spanning alpha of +0.68% per month (t=2.41) became -0.29% (t=-0.62) on the sealed 2020-2024 holdout; high turnover then made the holdout negative at every tested cost level. This is a fingerprinted source-evidence retrofit, not a new recomputation. |
| [`cases/buy_the_dip`](cases/buy_the_dip) | Practitioner thesis: dips in wide-moat names can be bought profitably, expressed as long calls | **Negative on the instrument, not the thesis.** The calls lose $263 per trade on average, $2,428 at the median; the same dips in the underlying are roughly flat to positive. The killer is the expiry clock, not the volatility headwind everyone expects — implied volatility *rose* on recovering trades. |
| [`cases/vol_harvest`](cases/vol_harvest) | Practitioner thesis: the volatility risk premium is real, so a small account can harvest it with defined-risk spreads | **Falsified — true premise, unreachable conclusion.** On real option chains the model's own pick returned −43.9% against a modelled +0.7% CAGR. The modelled edge crosses zero at 0.082 index points of friction per leg: the whole result lived inside a spread assumption only real quotes could settle. |
| [`cases/drift`](cases/drift) | A deployed feature discriminates winning from losing days for a live trading rule | **Decayed, detectable 2.8 years early, cause unproven.** Discrimination fell 0.597 → 0.442 (below chance) and partly recovered. The obvious culprit correlates at −0.72 over the full sample and flips to +0.76 after 2022 — it coincides with the inversion and explains neither the onset nor the recovery. |
| [`cases/volatility_managed`](cases/volatility_managed) | Moreira–Muir volatility management adds incremental return beyond the unscaled market | **No clear incremental holdout evidence in the bounded public-data test.** Sharpe is modestly higher (0.50 vs 0.48), but the 2000+ HAC alpha is +0.16% per month (t=1.21; 95% interval crosses zero). |

Each case names its evidence mode and reproduction boundary in its README. Some run
offline from pinned data; some are explicitly read-only replays of source evidence; one
is data-gated. Every case ends in a registry card ([`registry/`](registry)) recording the
claim, protocol, verdict, and honest limitations. The registry index is regenerated from
the cards, so it cannot drift.

All delivered cases also implement one platform contract. `verdict.case_contract`
defines their commands, reports, known protocol gaps and normalized `case_result.json`;
the latter hashes every declared evidence artifact. Use `scripts/run_case.py CASE_ID
--execute` to recompute one case, `--report-only` to rebuild its presentation, or
`--all --verify` for the non-computing content-addressed check. The repository-wide
`scripts/audit_integrity.py` then closes the chain across catalog, registry cards,
artifact hashes, protocol coverage, Agent providers and generated site pages.

These four are the **foundational studies**: Chart-CNN contributed the sealed-holdout and
spanning playbook; Buy the Dip contributed point-in-time construction and expression
diagnosis; Vol Harvest contributed friction and implementability; Distribution Shift
contributed deployment-drift diagnosis. Their exact catalog IDs are an executable
invariant, so adding a case cannot rewrite the system's origin story.

Three later studies prove that the framework travels beyond its source material:
[`cases/complexity`](cases/complexity) is the first fresh, end-to-end audit, and
[`cases/tsmom`](cases/tsmom) is a post-publication commodity momentum extension;
[`cases/volatility_managed`](cases/volatility_managed) is a bounded public-data market
reconstruction. None is allowed to become a foundational source merely because it is newer
or more executable.

A further claim is recorded as **not adjudicable here**: the protocol is written and
pre-registered, and the corpus needed to execute it has not been built. That state exists
because the alternative — silence, or a verdict on data that was never assembled — is worse.

```bash
micromamba run -n verdict python scripts/build_site.py   # -> docs/, served by GitHub Pages
```

The site is generated from the cards, the case reports and the recorded agent run, so it
cannot claim something the repository does not.

## The framework

| Module | What it carries |
|---|---|
| `verdict.splits` | Chronological splits; walk-forward; the **sealed-holdout ledger** — every unseal is stamped with a reason and a configuration fingerprint, and re-opening under a *changed* configuration raises |
| `verdict.pointintime` | Persistence screens and as-of universes; audits for signal timing, universe membership, and disclosure lag that never import the construction code |
| `verdict.evaluate` | Spanning regressions (HAC), block-bootstrap intervals, out-of-sample R², Clark–West and Diebold–Mariano, AUC with block-bootstrap bands |
| `verdict.costs` | Turnover, cost-sensitivity grids, breakeven cost and breakeven friction, IV-scaled spreads, budgeted position sizing |
| `verdict.options` | Black–Scholes, Greeks, implied volatility, and delta/vega/theta P&L attribution |
| `verdict.features` | Random Fourier features and the full ridge path from one SVD per window |
| `verdict.synthetic` | Known-answer generators: pure noise, planted linear and nonlinear signal, reversal world, wild bootstrap |
| `verdict.robust` | Parameter sweeps, membership stability, conclusion stability, untested-additions accounting |
| `verdict.diagnose` | The playbooks: false positive caught by a holdout, cost anatomy, expression vs underlying, kernel equivalence, drift detection, attribution split tests |
| `verdict.report` | Verdict documents whose limitations section is mandatory, and the claim registry |

## The agent

A thin layer over the framework that reads a paper and produces a verdict:

```
extract the claim  ->  pre-register the protocol  ->  [a person approves]
                   ->  execute via tools  ->  write  ->  audit the numbers
```

```bash
# real numbers, scripted model turns, no API key needed
micromamba run -n verdict python scripts/run_agent.py --offline --yes
micromamba run -n verdict python scripts/run_agent_eval.py
```

Two properties are structural rather than promised:

- **The protocol binds.** It is written and approved before any tool runs, and a
  later request to tune a parameter, re-open a sealed block, or drop inconvenient
  observations is refused with the clause it violates.
- **Prose may not invent numbers.** Every figure in the written verdict is checked
  against the values the tools returned; anything unsupported is flagged and the
  draft is withheld rather than published. Rounding is judged at the precision the
  figure was written to.

The agent chooses which tools to call and writes the prose. It never computes. A
case-scoped provider supplies the numbers: `complexity-voc` has an executable framework
adapter, while the retrospective and extension cases have explicitly labelled read-only
providers over pinned result documents. Evidence replay is never presented as a fresh
recomputation. The model is a swappable dependency (`llm.py`), so the whole layer —
schema validation, provider routing, the tool loop and both guardrails — is tested
offline and deterministically.

**Evaluating the agent** is possible here in a way it usually is not: two published
critiques of the complexity claim name the specific tests that settled it, so a
protocol drafted from the paper alone can be scored against expert practice. The
report in [`cases/complexity/agent_eval`](cases/complexity/agent_eval) lists what the
agent *missed*, item by item, because that gap is the honest measure of the system's
reach.

## Design principles

1. **Numbers come from deterministic code.** Prose describes them; it never produces them.
2. **A sealed holdout opens once**, and the act is recorded where a reader can check it.
3. **The protocol precedes the data.** Parameters are fixed in advance, not tuned afterwards.
4. **Negative results are first-class.** A verdict without honest limitations does not render.
5. **Every component has a known-answer test**, including controls that must find a
   planted effect. `scripts/regress.py` must exit 0.
6. **Audits do not import what they audit.** A pipeline vouching for itself proves nothing.

## Status

Built: the framework, the working surface, the multi-case Agent provider layer, the
claim-registry site, four provenance-preserving foundational cases, a fresh Complexity
audit, and the TSMOM extension. Each completed case ends in a registry card and a
normalized, content-addressed result envelope; the integrity audit rejects drift between
results, reports, cards, providers and site output.

Not built yet: a fresh Chart-CNN recomputation from the original point-in-time platform
inputs, and a live agent run, which needs the paper itself, `pip install anthropic`, and
credentials. The offline path exercises every part of the loop except the model's own
judgment. The Chart-CNN case therefore labels its imported result as evidence replay
rather than presenting it as a new run.

Provenance: the components were extracted from completed research projects rather
than designed in the abstract, which is why the playbooks are specific — they are the
questions those studies actually had to answer. Where a case rests on a number that
cannot be recomputed offline, the report says so in its limitations and pins the
number with its provenance rather than restating it as if it were re-derived.
