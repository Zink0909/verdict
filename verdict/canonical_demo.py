"""The fixed, API-free five-minute demonstration of Verdict's core contract.

This module is intentionally case-specific.  A canonical demo should be one
clear, reproducible argument, not another generic orchestration framework.  It
uses the existing executable Complexity provider, fixes every tool argument and
decision threshold before execution, and returns presentation-ready structured
data.  The Streamlit page only displays this result.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .agent.providers import get_provider
from .case_contract import load_case_result

ROOT = Path(__file__).resolve().parents[1]
CASE_ID = "complexity-voc"

LEARNING_MAP = [
    {"source project": "Chart-CNN", "lesson carried into Verdict":
     "chronological generalization and benchmark spanning"},
    {"source project": "Buy the Dip", "lesson carried into Verdict":
     "separate a signal from the instrument used to express it"},
    {"source project": "Vol Harvest", "lesson carried into Verdict":
     "treat real friction and implementability as part of the claim"},
    {"source project": "Distribution Shift", "lesson carried into Verdict":
     "monitor decay without promoting correlation into causal explanation"},
]

# These are part of the protocol, not values selected after seeing a run.
PROTOCOL = {
    "configuration": {
        "window_months": 12,
        "small_model_features": 60,
        "large_model_features": 1200,
        "ridge_penalty": 0.001,
        "random_feature_seeds": 2,
        "counterfactual_draws": 3,
    },
    "tests": [
        "reproduce whether performance rises from 60 to 1,200 random features",
        "test forecast accuracy against the no-predictability benchmark",
        "test whether a deterministic kernel smoother spans the complex model",
        "inject reversal to diagnose a momentum mechanism",
        "destroy predictor information while preserving nuisance structure",
    ],
    "decision_rules": {
        "kernel_equivalence": (
            "forecast correlation >= 0.90, spanning R2 >= 0.85, and "
            "absolute residual-alpha t < 1.96"),
        "information_survival": (
            "counterfactual Sharpe after destroying predictor information is at least "
            "75% of the real-data Sharpe"),
        "bounded_kill_criterion": (
            "if kernel equivalence and information survival both hold, the observed "
            "performance is not sufficient evidence of learned predictor signal"),
    },
    "decision_rule_rationale": {
        "kernel_equivalence": (
            "0.90 forecast correlation and 0.85 spanning R2 require the simple mechanism "
            "to explain most, not merely some, of the complex result; |t| < 1.96 requires "
            "no conventionally detectable residual alpha"),
        "information_survival": (
            "a learned-predictor interpretation should materially weaken when predictor "
            "information is destroyed; retaining at least three quarters is pre-defined as "
            "failure to show that expected collapse in this short demonstration"),
    },
    "preregistered": True,
}


def load_context(root: Path = ROOT) -> dict:
    """Load the public claim and content-addressed evidence envelope."""
    card = json.loads((root / "registry" / f"{CASE_ID}.json").read_text())
    evidence = load_case_result(root / "cases" / "complexity" / "case_result.json")
    checked = []
    for artifact in evidence["artifacts"]:
        path = root / artifact["path"]
        raw = path.read_bytes()
        checked.append({
            **artifact,
            "verified": (len(raw) == artifact["bytes"] and
                         hashlib.sha256(raw).hexdigest() == artifact["sha256"]),
        })
    return {"case_id": CASE_ID, "learning_map": LEARNING_MAP,
            "claim": card["claim"], "published_verdict": card["verdict"],
            "protocol": PROTOCOL, "evidence": {**evidence, "artifacts": checked}}


def _by_tool(trace: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for step in trace:
        grouped.setdefault(step["tool"], []).append(step["result"])
    return grouped


def adjudicate(trace: list[dict]) -> dict:
    """Apply the fixed decision rule to tool output; no prose model is involved."""
    grouped = _by_tool(trace)
    small, large = grouped["run_complex_model"]
    forecast = grouped["forecast_comparison_test"][0]
    kernel = grouped["kernel_equivalence_check"][0]
    counterfactuals = {item["kind"]: item for item in grouped["counterfactual_world"]}
    reversal = counterfactuals["reversal"]
    destroyed = counterfactuals["destroy_information"]
    base = destroyed["sharpe_real_data"]
    retention = destroyed["sharpe_counterfactual_mean"] / base if base > 0 else float("nan")

    checks = {
        "headline_direction_reproduced": large["sharpe_annualized"] > small["sharpe_annualized"],
        "formal_forecast_test_passed": forecast["rejects_equal_accuracy_5pct"],
        "kernel_equivalence": (
            kernel["forecast_correlation"] >= 0.90
            and kernel["kernel_spans_r2"] >= 0.85
            and abs(kernel["residual_alpha_t"]) < 1.96),
        "information_survives_destruction": retention >= 0.75,
        "reversal_is_negative": reversal["share_negative"] >= 0.80,
    }
    killed = checks["kernel_equivalence"] and checks["information_survives_destruction"]
    outcome = ("PERFORMANCE REPRODUCES; LEARNED-SIGNAL INTERPRETATION NOT SUPPORTED"
               if killed else "INCONCLUSIVE IN THE BOUNDED DEMO")
    return {
        "outcome": outcome,
        "state": "bounded-verdict-delivered" if killed else "bounded-inconclusive",
        "checks": checks,
        "information_retention_ratio": round(retention, 4),
        "summary": (
            "The performance pattern and formal forecast comparison survive in this fixed "
            "configuration, but a simple kernel spans most of the complex forecast and the "
            "result largely survives when predictor information is destroyed. Complexity is "
            "therefore not sufficient evidence of learned predictor signal here." if killed else
            "The fixed tests did not jointly meet the pre-registered mechanism threshold; the "
            "short demonstration does not adjudicate the interpretation."),
        "limitations": [
            "This fast demonstration uses 1,200 rather than the paper's 12,000 features, two "
            "random-feature seeds, and three counterfactual draws.",
            "It tests the short-window aggregate-market configuration, not every specification "
            "or the general value of over-parameterized models.",
            "It is a live bounded demonstration of the core contract, not a replacement for "
            "the full case report and its larger pinned evidence record.",
        ],
        "headline": {"small": small, "large": large, "forecast": forecast,
                     "kernel": kernel, "reversal": reversal,
                     "destroy_information": destroyed},
    }


def run() -> dict:
    """Execute the complete fixed battery through the existing deterministic provider."""
    provider = get_provider(CASE_ID)
    if provider.mode != "executable":
        raise RuntimeError(f"canonical demo requires executable evidence, got {provider.mode!r}")
    cfg = PROTOCOL["configuration"]
    calls = [
        ("describe_dataset", {}),
        ("run_complex_model", {"n_features": cfg["small_model_features"],
                               "window": cfg["window_months"],
                               "shrinkage": cfg["ridge_penalty"],
                               "seeds": cfg["random_feature_seeds"]}),
        ("run_complex_model", {"n_features": cfg["large_model_features"],
                               "window": cfg["window_months"],
                               "shrinkage": cfg["ridge_penalty"],
                               "seeds": cfg["random_feature_seeds"]}),
        ("forecast_comparison_test", {"n_features": cfg["large_model_features"],
                                      "window": cfg["window_months"],
                                      "seeds": cfg["random_feature_seeds"]}),
        ("kernel_equivalence_check", {"window": cfg["window_months"],
                                      "n_features": cfg["large_model_features"],
                                      "seeds": cfg["random_feature_seeds"]}),
        ("counterfactual_world", {"kind": "reversal",
                                  "n_features": cfg["large_model_features"],
                                  "window": cfg["window_months"],
                                  "draws": cfg["counterfactual_draws"],
                                  "seeds": cfg["random_feature_seeds"]}),
        ("counterfactual_world", {"kind": "destroy_information",
                                  "n_features": cfg["large_model_features"],
                                  "window": cfg["window_months"],
                                  "draws": cfg["counterfactual_draws"],
                                  "seeds": cfg["random_feature_seeds"]}),
    ]
    trace = [{"step": i, "tool": name, "arguments": arguments,
              "result": provider.run_tool(name, arguments)}
             for i, (name, arguments) in enumerate(calls)]
    return {"case_id": CASE_ID, "execution_mode": provider.mode,
            "protocol": PROTOCOL, "trace": trace, "verdict": adjudicate(trace)}
