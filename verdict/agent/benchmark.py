"""Protocol-only benchmarks for the research-audit Agent.

These benchmarks answer a deliberately limited question: after reading one
paper, did a model draft a protocol that includes the checks a human curator
specified *before looking at that model run*?  They do not score whether the
model understood every nuance of a claim, reproduce a paper, or establish that
the underlying strategy works.  The execution layer remains a separate,
deterministic audit.

Gold files contain no paper text and no copied tables.  They are short,
versioned human checklists with source links and a stated scope.  This keeps
the benchmark reviewable while avoiding an accidental claim that a proprietary
or copyrighted source has been bundled with the repository.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from . import evals
from .schema import ClaimCard, Protocol


REQUIRED = ("schema_version", "id", "title", "paper", "scope", "checklist")
PAPER_REQUIRED = ("citation", "source_url", "local_default")


def load(path: str | Path) -> dict[str, Any]:
    """Load a curator-authored benchmark specification and validate its boundary."""
    item = json.loads(Path(path).read_text())
    missing = [key for key in REQUIRED if not item.get(key)]
    if missing:
        raise ValueError(f"benchmark missing: {', '.join(missing)}")
    missing_paper = [key for key in PAPER_REQUIRED if not item["paper"].get(key)]
    if missing_paper:
        raise ValueError(f"benchmark paper missing: {', '.join(missing_paper)}")
    if item["schema_version"] != 1:
        raise ValueError(f"unsupported benchmark schema: {item['schema_version']}")
    # Reuse the evaluation checklist validator, including non-empty patterns.
    checklist = item["checklist"]
    if not isinstance(checklist, list) or not checklist:
        raise ValueError("benchmark checklist must be a non-empty list")
    for check in checklist:
        if not all(check.get(key) for key in ("id", "label", "source", "any_of")):
            raise ValueError(f"malformed benchmark check: {check}")
    return item


def score(claim: ClaimCard, protocol: Protocol, benchmark: dict[str, Any]) -> dict[str, Any]:
    """Score only the typed protocol against a pre-existing human checklist.

    Claim cards have a closed required schema, but natural-language claim
    quality requires human review.  We therefore report schema completion and
    review prompts rather than fabricate a semantic accuracy percentage.
    """
    protocol_score = evals.score_protocol(protocol.items(), benchmark["checklist"])
    fields = claim.to_dict()
    return {
        "benchmark_id": benchmark["id"],
        "benchmark_title": benchmark["title"],
        "paper": benchmark["paper"],
        "scope": benchmark["scope"],
        "claim_card": {
            "schema_complete": all(bool(value) for value in fields.values()),
            "human_review_prompts": benchmark.get("claim_review_prompts", []),
            "note": ("Claim-card quality is deliberately not reduced to keyword coverage; "
                     "review the saved card against these prompts."),
        },
        "protocol": protocol_score,
        "result_boundary": (
            "Protocol-drafting benchmark only. No provider was called, no data was supplied "
            "to the model, no paper result was reproduced, and no investment conclusion follows."),
    }


def render_report(result: dict[str, Any], model: str, paper_origin: str) -> str:
    """Render a readable report whose omissions remain more prominent than a score."""
    protocol = result["protocol"]
    lines = [
        f"# Agent protocol benchmark — {result['benchmark_title']}", "",
        f"**Model:** `{model}`  ",
        f"**Paper input:** {paper_origin}  ",
        f"**Paper source:** {result['paper']['source_url']}", "",
        result["scope"], "",
        "## Result", "",
        f"Protocol coverage: **{protocol['n_covered']}/{protocol['n_checklist']}** "
        f"({protocol['coverage']:.0%}) of the pre-written curator checklist.", "",
        "The Claim Card passed required-field validation. Its semantic faithfulness still needs "
        "human review against the prompts in `run.json`; it is not assigned a synthetic score.",
        "", "## Covered", "",
    ]
    for item in protocol["covered"]:
        lines.append(f"- **{item['label']}** ({item['source']}) — matched: “{item['matched']}”")
    lines += ["", "## Missed — items absent from this drafted protocol", ""]
    if protocol["missed"]:
        for item in protocol["missed"]:
            lines.append(f"- **{item['label']}** ({item['source']})")
    else:
        lines.append("- Nothing on this checklist was missed.")
    lines += ["", "## Proposed but not on the checklist", ""]
    if protocol["additions"]:
        lines.extend(f"- “{line}”" for line in protocol["additions"])
    else:
        lines.append("- None.")
    lines += ["", "## Boundary", "", f"- {result['result_boundary']}",
              f"- Matching is {protocol['matching']}.",
              "- This is one curated paper and one model run, not a general capability claim.",
              "- The checklist was written by this project's curator from the public paper and "
              "the bounded audit protocol; it is not a claim that the authors endorsed it."]
    return "\n".join(lines) + "\n"
