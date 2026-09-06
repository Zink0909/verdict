#!/usr/bin/env python3
"""One operational entry point for every Verdict case.

Examples:
  python scripts/run_case.py complexity-voc --verify
  python scripts/run_case.py gamma-signal-drift --execute
  python scripts/run_case.py --all --verify

`--verify` never recomputes research results. It validates declared artifacts
and refreshes the normalized `case_result.json` evidence envelope.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from verdict.case_contract import CaseResult  # noqa: E402
from verdict.catalog import CASE_BY_ID, CASES  # noqa: E402
from verdict.report import validate_card       # noqa: E402


def _run_step(step: tuple[str, ...]) -> None:
    command = [sys.executable if step[0] == "python" else step[0], *step[1:]]
    print("  $ " + " ".join(command), flush=True)
    subprocess.run(command, cwd=ROOT, check=True)


def run_case(case_id: str, execute: bool = False, report_only: bool = False) -> Path:
    if case_id not in CASE_BY_ID:
        raise ValueError(f"unknown case {case_id!r}; available: {', '.join(CASE_BY_ID)}")
    spec = CASE_BY_ID[case_id]
    if spec.role == "data-gated":
        raise ValueError(f"{case_id} is data-gated and has no executable result")

    if execute and report_only:
        raise ValueError("choose either execute or report-only")
    if execute:
        for step in (*spec.run_steps, *spec.report_steps):
            _run_step(step)
    elif report_only:
        for step in spec.report_steps:
            _run_step(step)

    card_path = ROOT / "registry" / f"{case_id}.json"
    card = json.loads(card_path.read_text())
    validate_card(card)
    if card["state"] != "verdict-delivered":
        raise ValueError(f"{case_id}: expected delivered card, got {card['state']!r}")

    result = CaseResult.build(spec, ROOT, card["state"])
    target = ROOT / "cases" / spec.folder / "case_result.json"
    result.write(target)
    print(f"  verified {case_id}: {len(result.artifacts)} hashed artifact(s) -> "
          f"{target.relative_to(ROOT)}")
    return target


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("case_id", nargs="?", choices=sorted(CASE_BY_ID))
    parser.add_argument("--all", action="store_true", help="verify all delivered cases")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--verify", action="store_true", help="validate existing artifacts (default)")
    mode.add_argument("--execute", action="store_true", help="run analysis and report steps")
    mode.add_argument("--report-only", action="store_true", help="regenerate reports, then verify")
    args = parser.parse_args()
    if args.all == bool(args.case_id):
        parser.error("give one case_id or --all")
    if args.all and (args.execute or args.report_only):
        parser.error("--all is verification-only; execute cases individually")

    ids = [c.card_id for c in CASES if c.role != "data-gated"] if args.all else [args.case_id]
    failures = []
    for case_id in ids:
        try:
            run_case(case_id, execute=args.execute, report_only=args.report_only)
        except Exception as exc:
            failures.append(f"{case_id}: {type(exc).__name__}: {exc}")
    if failures:
        print("case runner failed:")
        for failure in failures:
            print(f"  - {failure}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
