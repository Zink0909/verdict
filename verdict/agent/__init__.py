"""Layer B — the research-audit agent.

The agent reads a paper, extracts the claim into a fixed shape, drafts a
pre-registered protocol, executes that protocol by calling the deterministic
framework, and writes the verdict. It is a thin layer over Layer A by design:
the interesting work is in the tools it calls, and the interesting guarantees
are the two it cannot evade —

* the protocol is written and approved before any tool runs, and requests to
  bend it afterwards are refused with the clause they violate;
* every number in the written verdict is checked against the values the tools
  returned, so a figure the model invented is caught rather than published.

    schema      the claim card and protocol, JSON-schema constrained
    llm         the model boundary: bare Messages API, plus an offline stand-in
    tools       Layer A exposed as tools — the only source of numbers
    guardrails  protocol enforcement and the number audit
    pipeline    the loop: extract -> pre-register -> approve -> execute -> write
    evals       scoring a drafted protocol against what human auditors did
    demo        an offline transcript for demonstration and regression testing
"""
