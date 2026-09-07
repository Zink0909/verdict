# Verdict project charter

Status: **scope fixed for the graduate-application version**.

This document is the boundary of the project. A possible feature is not a
reason to build it. New work must strengthen the argument below, fix a
correctness or reproducibility problem, or close one of the stated completion
criteria.

## 1. Project thesis

Verdict is an end-to-end **predictive-ML evidence system**. It turns a model or
research claim into a pre-specified, reproducible and inspectable conclusion.

The system originated in four finance research projects, but its application
claim is about ML and data-science practice: predictive performance is not one
metric. It is an evidence chain spanning problem formulation, point-in-time
data, temporal evaluation, useful benchmarks, implementation constraints,
distribution shift and honest communication.

Verdict is not a trading system, an automated investment adviser, a strategy
discovery engine, or a universal paper-reproduction service.

## 2. Audience and question

The primary audience is an ML, Data Science or AI graduate admissions reader.
The project should let that reader answer one question:

> What did the applicant learn across four projects, and can they turn that
> learning into one coherent system spanning research, data, software and user
> communication?

The working user represented by the interface is a researcher or data
scientist deciding whether a predictive claim has enough evidence to report,
extend or deploy.

## 3. The learning argument

The four foundational studies are fixed. They are sources of reusable research
discipline, not four products placed beside one another.

| Foundational study | Failure mode encountered | Reusable lesson carried into Verdict |
|---|---|---|
| Chart-CNN stock selection | Validation evidence did not survive the sealed temporal holdout | Generalization must be checked chronologically and against information already in the benchmark set |
| Buy the Dip | The underlying thesis and its long-call expression produced different outcomes | Signal, decision rule and implementation instrument are separate claims |
| Retail volatility harvesting | A theoretical edge lived inside assumptions that real quotes and friction could overturn | Implementability, provenance and cost belong inside the evaluation, not in a footnote |
| Gamma-signal distribution shift | A deployed feature changed and its obvious correlate did not establish a stable cause | ML systems have a monitored lifecycle; detecting drift is different from explaining it |

Together they support the central lesson:

> A predictive result is credible only when its full evidence chain can survive
> a negative answer and be inspected afterwards.

## 4. Capability evidence

The project demonstrates breadth by connecting the lifecycle, not by collecting
technologies.

| Capability | Concrete evidence in the repository |
|---|---|
| Problem formulation | Typed Claim Card, pre-registered Protocol and required kill criteria |
| Data engineering | Point-in-time construction, as-of membership, chronology checks and source provenance |
| ML and statistical evaluation | Sealed holdout, spanning, block bootstrap, forecast tests, controls and robustness sweeps |
| Deployment reasoning | Trading-friction accounting, instrument diagnosis and distribution-shift checks |
| Backend/software engineering | Reusable Python modules, strict provider boundary, case contract, regression gates and integrity audit |
| Frontend/product communication | A guided Streamlit workflow, generated public site, bounded Verdict report and evidence register |
| Responsible AI | Optional LLM layer may structure claims and choose closed tools, but cannot compute, bypass approval or conceal a data gap |

“Full stack” here means ownership from question and data through evaluation,
software, interface and communication. It does not require adding a separate
web framework, database, cloud platform or infrastructure layer when the
research workflow does not need one.

## 5. Canonical product flow

The graduate-application demo must work without an API key and complete in
about five minutes:

```text
four projects and the lessons extracted from them
    -> one prepared predictive-ML claim
    -> Claim Card and fixed Protocol
    -> deterministic evaluation
    -> holdout / benchmark / uncertainty / constraint evidence
    -> bounded Verdict and honest limitations
    -> inspectable evidence record
```

The Complexity case is the principal technical demonstration because it runs
the shared contract end to end and is recognizably an ML evaluation problem.
Its presentation should be simplified before another principal case is added.

The main interactive route is:

1. **New claim** — make the hypothesis and kill criteria explicit;
2. **Evaluate a result** — run the deterministic validation battery;
3. **Evidence register** — inspect what was computed, what was replayed, what
   was data-gated and what cannot be concluded.

## 6. Product layers

### Core

- the four fixed foundational studies and their learning map;
- deterministic validation modules and known-answer controls;
- Claim Card, Protocol, case contract and evidence modes;
- the Complexity canonical case;
- the three-step interactive route and public evidence register.

### Advanced

- new-paper ingestion;
- the constrained research-audit Agent;
- the local hash-verified Evidence Vault;
- user-supplied CSV evidence evaluation beyond the prepared demo.

### Appendix

- additional cases that demonstrate portability;
- Agent protocol benchmarks and evaluation reports;
- detailed tool traces, artifact manifests and implementation notes.

Advanced and Appendix material remains maintained and inspectable, but it must
not displace the Core narrative or become a second product identity.

## 7. Explicit non-goals

The application version will not pursue:

- live trading, broker connectivity, portfolio recommendations or real-time
  signal delivery;
- automatic strategy discovery or autonomous research publication;
- support for arbitrary papers, datasets, asset classes or model families;
- a large paper library, Agent leaderboard or expanding benchmark suite;
- authentication, multi-user collaboration, a production database or a
  microservice architecture;
- additional frontend/backend/cloud technologies added only to increase the
  apparent stack;
- another case unless it replaces an inadequate canonical demonstration rather
  than merely increasing the count.

## 8. Definition of done

The application version is complete when:

1. a new reader can explain the project in one sentence after 30 seconds;
2. the relationship between all four foundational studies and the shared
   system is explicit;
3. the API-free canonical demo completes in about five minutes without needing
   code changes;
4. the principal case is traceable from claim and protocol to code, result,
   limitations and content hashes;
5. README, public site and interface explain what was learned rather than only
   listing features;
6. the regression and repository-integrity checks pass;
7. the public version is deployed, its instructions are tested from a clean
   environment, and no confidential internship artifact is exposed.

After these criteria are met, the graduate-application version is frozen.
Allowed changes are correctness, security, dependency maintenance, clearer
communication and application-specific presentation edits.

## 9. Change gate

Before implementing a proposed change, answer all four questions:

1. Which capability or learning outcome above does it make easier to verify?
2. Does it improve the canonical five-minute path, or only enlarge the
   Appendix?
3. Can the same result be achieved by simplifying or reorganizing existing
   work?
4. Which completion criterion does it close?

If questions 1 and 4 have no concrete answer, the change is out of scope. If it
only enlarges the Appendix, it is deferred until the graduate-application
version has been frozen.
