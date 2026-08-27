"""verdict — a validation harness for time-series prediction claims.

Layer A of the Verdict system: deterministic components that implement the
discipline of honest out-of-sample evaluation. Every number in a verdict comes
from this layer; the agent layer (B) only orchestrates and writes.

    splits        chronological splits, walk-forward, the sealed-holdout ledger
    pointintime   as-of universes, persistence screens, independent leakage audits
    evaluate      spanning, block bootstrap, OOS R-squared, Clark-West, Diebold-Mariano
    costs         turnover, cost sensitivity, breakeven cost, spreads, budgeted sizing
    options       Black-Scholes, Greeks, implied volatility, P&L attribution
    features      random Fourier features and the full ridge path
    synthetic     known-answer generators and counterfactual worlds
    robust        parameter sweeps, membership and conclusion stability
    diagnose      mechanism playbooks (false positive, cost anatomy, expression, kernel)
    report        verdict documents with mandatory limitations, and the claim registry

Provenance: components are extracted and generalized from four completed
research projects (two clean nulls, one falsification, one drift diagnosis);
see the case library under cases/.
"""
__version__ = "0.1.0"
