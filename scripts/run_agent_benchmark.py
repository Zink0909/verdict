#!/usr/bin/env python3
"""Run a protocol-only, omissions-first benchmark against a live Agent.

The command intentionally stops after claim extraction and protocol drafting.
It never approves a protocol, sees market data, invokes a provider, computes a
result, or writes to the public registry.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from verdict.agent import benchmark, paper, pipeline  # noqa: E402
from verdict.agent.llm import MODEL, AnthropicModel   # noqa: E402

GOLD = ROOT / "cases" / "agent_benchmark"


def specs() -> dict[str, Path]:
    return {path.stem: path for path in sorted(GOLD.glob("*.json"))}


def read_paper(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"paper not found: {path}")
    if path.suffix.lower() == ".pdf":
        return paper.paper_text(path.read_bytes(), path.name)
    return path.read_text()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--list", action="store_true", help="show curated benchmark specifications")
    ap.add_argument("--benchmark", choices=sorted(specs()),
                    help="benchmark to run; required unless --list")
    ap.add_argument("--paper", type=Path,
                    help="lawful local copy of that benchmark's paper; overrides its local default")
    a = ap.parse_args()

    available = specs()
    if a.list:
        for identifier, path in available.items():
            item = benchmark.load(path)
            print(f"{identifier}\n  {item['title']}\n  {item['paper']['citation']}\n"
                  f"  default: {item['paper']['local_default']}\n"
                  f"  checks: {len(item['checklist'])}\n")
        return 0
    if not a.benchmark:
        ap.error("give --benchmark ID, or use --list")

    item = benchmark.load(available[a.benchmark])
    path = a.paper or (ROOT / item["paper"]["local_default"])
    try:
        text = read_paper(path)
    except Exception as exc:
        print(f"cannot start benchmark: {exc}", file=sys.stderr)
        return 1
    if not text.strip():
        print("cannot start benchmark: extracted paper text is empty", file=sys.stderr)
        return 1

    print("LIVE MODEL RUN — paper text is sent to the configured Anthropic API.\n"
          "This is protocol drafting only: no data provider, execution, verdict, or publication.\n")
    model = AnthropicModel()
    claim = pipeline.extract_claim(model, text)
    protocol = pipeline.draft_protocol(model, claim)
    scored = benchmark.score(claim, protocol, item)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = ROOT / ".verdict-workspace" / "benchmarks" / item["id"] / timestamp
    output.mkdir(parents=True, exist_ok=False)
    origin = str(path.resolve())
    payload = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "model": MODEL,
        "benchmark": item,
        "paper_input": {"origin": origin, "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
                        "characters": len(text)},
        "claim": claim.to_dict(),
        "protocol": protocol.to_dict(),
        "score": scored,
        "state": "protocol-drafted-not-approved-not-executed",
    }
    (output / "run.json").write_text(json.dumps(payload, indent=2) + "\n")
    (output / "report.md").write_text(benchmark.render_report(scored, MODEL, origin))
    print(f"coverage {scored['protocol']['n_covered']}/{scored['protocol']['n_checklist']} "
          f"({scored['protocol']['coverage']:.0%})")
    print(f"saved {output / 'run.json'} and report.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
