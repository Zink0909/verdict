#!/usr/bin/env python3
"""One command: a paper goes in, a verdict comes out.

    # offline: real numbers, scripted model turns, no API key needed
    micromamba run -n verdict python scripts/run_agent.py --offline

    # live: needs `pip install anthropic` and credentials in the environment
    micromamba run -n verdict python scripts/run_agent.py --paper path/to/paper.txt \
      --case-id time-series-momentum

    # the honest third outcome: claim extracted, protocol registered, no data to run it
    micromamba run -n verdict python scripts/run_agent.py --offline --data-gated

Writes the full run — claim card, protocol, every tool call and result, the
verdict draft, and the number audit — to the selected case's `agent_run/`.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from verdict.agent import demo, pipeline, providers  # noqa: E402
from verdict.agent.llm import MODEL, AnthropicModel  # noqa: E402
from verdict.catalog import CASE_BY_ID               # noqa: E402

def approval_gate(auto: bool):
    """The human in the loop. The agent drafts; a person signs off before execution."""
    def approve(claim, protocol) -> bool:
        print("\n--- claim card " + "-" * 48)
        print(json.dumps(claim.to_dict(), indent=2))
        print("\n--- pre-registered protocol " + "-" * 35)
        print(json.dumps(protocol.to_dict(), indent=2))
        if auto:
            print("\n[auto-approved: --yes]")
            return True
        answer = input("\nApprove this protocol and execute it? [y/N] ").strip().lower()
        return answer in ("y", "yes")
    return approve


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--paper", type=Path, help="text file containing the paper")
    ap.add_argument("--offline", action="store_true",
                    help="use the scripted transcript (real numbers, fixture model turns)")
    ap.add_argument("--data-gated", action="store_true",
                    help="stop after pre-registration, as if the data were unavailable")
    ap.add_argument("--plant-error", action="store_true",
                    help="offline only: inject an unsupported figure to show the audit catch it")
    ap.add_argument("--yes", action="store_true", help="approve the protocol without prompting")
    ap.add_argument("--max-steps", type=int, default=8)
    ap.add_argument("--case-id", choices=providers.supported_case_ids(),
                    default="complexity-voc",
                    help="case-scoped tool provider (default: complexity-voc)")
    a = ap.parse_args()

    if a.offline:
        if a.case_id != "complexity-voc":
            ap.error("the offline fixture is specific to complexity-voc; use a live model "
                     "for another case provider")
        model, paper, provenance = (demo.scripted_model(a.plant_error), demo.PAPER_STAND_IN,
                                    "scripted")
        print("OFFLINE RUN — the model's turns are a fixture; every number below is computed "
              "live by the framework.\n")
    else:
        if not a.paper:
            ap.error("give --paper PATH, or use --offline")
        model, paper, provenance = AnthropicModel(), a.paper.read_text(), MODEL

    run = pipeline.run_audit(model, paper, data_available=not a.data_gated,
                             approve=approval_gate(a.yes), max_steps=a.max_steps,
                             case_id=a.case_id)

    print("\n--- execution " + "-" * 49)
    for step in run.tool_trace:
        if "tool" in step:
            print(f"  {step['tool']}({', '.join(f'{k}={v}' for k, v in step['arguments'].items())})")
            print(f"      -> {json.dumps(step.get('result', step.get('error')))[:180]}")
        elif "note" in step:
            print(f"  [model] {step['note'][:160]}")

    if run.verdict_text:
        print("\n--- verdict draft " + "-" * 45)
        print(run.verdict_text)
        audit = run.number_audit
        print("\n--- number audit " + "-" * 46)
        print(f"  {audit['n_numbers']} figures written, checked against "
              f"{audit['n_allowed_values']} computed or source values")
        print("  CLEAN — every figure traces to a tool result" if audit["clean"]
              else f"  UNSUPPORTED: {audit['unsupported']}  <- the model wrote these; "
                   "nothing computed them")

    print(f"\nstate: {run.state}")
    for note in run.notes:
        print(f"  note: {note}")

    spec = CASE_BY_ID[a.case_id]
    out = ROOT / "cases" / spec.folder / "agent_run"
    out.mkdir(parents=True, exist_ok=True)
    payload = run.to_dict()
    provider = providers.get_provider(a.case_id)
    payload["provenance"] = {"model": provenance,
                             "provider_mode": provider.mode,
                             "tools": [d["name"] for d in provider.definitions()],
                             "note": "tool results are computed by the framework in every mode; "
                                     "in a scripted run the model's turns are a fixture"}
    (out / "run.json").write_text(json.dumps(payload, indent=2, default=str))
    if run.verdict_text:
        (out / "verdict_draft.md").write_text(run.verdict_text + "\n")
    print(f"\nsaved {out/'run.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
