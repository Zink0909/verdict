#!/usr/bin/env python3
"""Score a drafted protocol against what human auditors actually did.

    micromamba run -n verdict python scripts/run_agent_eval.py

The complexity case is unusual: two published critiques of the same paper name
the specific tests that settled it, so a protocol written from the paper alone
can be scored against expert practice. The interesting output is not the
coverage number — it is the list of checks the agent did not think of.

A run whose model turns were scripted is scored and labelled as a fixture: a
protocol written by hand and then graded against a checklist measures its
author, not the model.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from verdict.agent import evals            # noqa: E402
from verdict.agent.schema import Protocol  # noqa: E402

EVAL_DIR = ROOT / "cases" / "complexity" / "agent_eval"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", type=Path, default=ROOT / "cases/complexity/agent_run/run.json")
    ap.add_argument("--checklist", type=Path, default=EVAL_DIR / "ground_truth.json")
    a = ap.parse_args()

    if not a.run.exists():
        print(f"no run at {a.run} — produce one with scripts/run_agent.py first")
        return 1
    payload = json.loads(a.run.read_text())
    if not payload.get("protocol"):
        print("that run has no protocol to score")
        return 1

    protocol = Protocol.from_dict(payload["protocol"])
    checklist = evals.load_checklist(a.checklist)
    score = evals.score_protocol(protocol.items(), checklist)

    model = (payload.get("provenance") or {}).get("model", "unknown")
    scripted = model == "scripted"
    provenance = (
        "**This scores a fixture, not the model.** The protocol came from a scripted "
        "offline run, so the coverage below measures the transcript's author. It exercises "
        "the eval machinery end to end; it is not a measurement of agent capability. Re-run "
        "with a live model and the paper itself for that."
        if scripted else
        f"Protocol drafted by `{model}` from the paper alone, with no access to the critique "
        "literature and no data. Scored against the checklist in "
        "`ground_truth.json`, assembled from the published critiques after the fact."
    )

    print(f"coverage {score['n_covered']}/{score['n_checklist']} ({score['coverage']:.0%})"
          + ("   [FIXTURE — not a measurement of the model]" if scripted else ""))
    for source, s in score["by_source"].items():
        print(f"  {source:<24} {s['covered']}/{s['total']}")
    print("\nmissed:")
    for m in score["missed"] or [{"label": "(nothing)", "source": ""}]:
        print(f"  - {m['label']} ({m.get('source','')})")

    EVAL_DIR.mkdir(parents=True, exist_ok=True)
    report = evals.render_report(
        score, "Agent evaluation — protocol coverage against expert practice", provenance)
    (EVAL_DIR / "report.md").write_text(report)
    (EVAL_DIR / "score.json").write_text(json.dumps(
        {**score, "provenance_model": model, "is_fixture": scripted}, indent=2))
    print(f"\nsaved {EVAL_DIR/'report.md'} and score.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
