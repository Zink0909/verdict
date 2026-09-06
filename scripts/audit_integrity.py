#!/usr/bin/env python3
"""Audit the repository-wide evidence chain, not just individual functions."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from verdict.agent.providers import get_provider  # noqa: E402
from verdict.case_contract import CaseResult, load_case_result  # noqa: E402
from verdict.catalog import CASE_BY_ID, CASES, validate_catalog  # noqa: E402
from verdict.report import validate_card  # noqa: E402


def audit(root: Path = ROOT) -> dict:
    checks: list[dict] = []
    errors: list[str] = []

    def check(name: str, fn) -> None:
        try:
            detail = fn()
            checks.append({"name": name, "ok": True, "detail": detail or "pass"})
        except Exception as exc:
            message = f"{name}: {type(exc).__name__}: {exc}"
            checks.append({"name": name, "ok": False, "detail": message})
            errors.append(message)

    check("catalog-valid", lambda: validate_catalog())

    registry_paths = sorted((root / "registry").glob("*.json"))
    registry_ids = {p.stem for p in registry_paths}
    check("catalog-covers-registry", lambda: _equal_sets(
        registry_ids, set(CASE_BY_ID), "registry ids", "catalog ids"))

    cards: dict[str, dict] = {}
    for path in registry_paths:
        def card_check(path=path):
            card = json.loads(path.read_text())
            validate_card(card)
            if card["id"] != path.stem:
                raise ValueError(f"id {card['id']!r} differs from filename")
            cards[card["id"]] = card
            return card["state"]
        check(f"card:{path.stem}", card_check)

    site_manifest_path = root / "docs" / ".verdict-site-manifest.json"
    site_files = set()
    if site_manifest_path.is_file():
        site_manifest = json.loads(site_manifest_path.read_text())
        site_files = set(site_manifest.get("generated", []))
        check("site-manifest", lambda: _site_manifest(site_manifest, root))
    else:
        check("site-manifest", lambda: _require(
            False, "docs/.verdict-site-manifest.json is missing"))

    for spec in CASES:
        card = cards.get(spec.card_id)
        if card is None:
            continue
        if spec.role == "data-gated":
            check(f"gated:{spec.card_id}", lambda card=card: _require(
                card["state"] == "protocol-ready-data-gated" and not card.get("verdict"),
                "data-gated catalog entry must remain data-gated without a verdict"))
            continue

        def manifest_check(spec=spec, card=card):
            if card["state"] != "verdict-delivered":
                raise ValueError(f"expected verdict-delivered, got {card['state']!r}")
            path = root / "cases" / spec.folder / "case_result.json"
            actual = load_case_result(path)
            expected = CaseResult.build(spec, root, card["state"]).to_dict()
            if actual != expected:
                raise ValueError("case_result.json is stale; run scripts/run_case.py --all --verify")
            return f"{len(actual['artifacts'])} artifact digests"
        check(f"manifest:{spec.card_id}", manifest_check)

        check(f"provider:{spec.card_id}", lambda spec=spec: _provider_mode(spec))
        page = f"cases/{spec.folder}.html"
        check(f"site:{spec.card_id}", lambda page=page: _require(
            page in site_files and (root / "docs" / page).is_file(),
            f"generated site page missing or unmanaged: {page}"))

        json_results = [p for p in spec.result_files if p.endswith(".json")]
        for rel in json_results:
            payload = json.loads((root / "cases" / spec.folder / rel).read_text())
            coverage = payload.get("protocol_coverage") if isinstance(payload, dict) else None
            if coverage:
                check(f"coverage:{spec.card_id}", lambda coverage=coverage, spec=spec: _coverage(
                    coverage, spec.protocol_complete, spec.protocol_gaps))

    return {
        "schema_version": 1,
        "ok": not errors,
        "summary": {"passed": sum(c["ok"] for c in checks),
                    "failed": sum(not c["ok"] for c in checks)},
        "checks": checks,
        "errors": errors,
    }


def _require(condition: bool, message: str) -> str:
    if not condition:
        raise ValueError(message)
    return "pass"


def _equal_sets(a: set, b: set, a_name: str, b_name: str) -> str:
    if a != b:
        raise ValueError(f"{a_name} != {b_name}; difference: {sorted(a ^ b)}")
    return f"{len(a)} ids"


def _provider_mode(spec) -> str:
    provider = get_provider(spec.card_id)
    if provider.mode != spec.agent_mode:
        raise ValueError(f"provider mode {provider.mode!r} != catalog {spec.agent_mode!r}")
    if not provider.definitions():
        raise ValueError("provider exposes no tools")
    return provider.mode


def _coverage(coverage: dict, complete: bool, gaps: tuple[str, ...]) -> str:
    if bool(coverage.get("complete")) != complete:
        raise ValueError("result protocol-complete flag differs from catalog")
    actual_gaps = set(coverage.get("not_executed", coverage.get("gaps", [])))
    if actual_gaps != set(gaps):
        raise ValueError(f"result protocol gaps differ from catalog: {sorted(actual_gaps ^ set(gaps))}")
    return "complete" if complete else f"{len(gaps)} declared gap(s)"


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _site_manifest(manifest: dict, root: Path) -> str:
    if manifest.get("schema_version") != 2:
        raise ValueError("site manifest schema must be 2; rebuild with scripts/build_site.py")
    expected_inputs = [*sorted((root / "registry").glob("*.json")),
                       *sorted((root / "cases").glob("*/report.md")),
                       *sorted((root / "cases" / "agent_benchmark").glob("*.json")),
                       root / "cases/complexity/agent_run/run.json",
                       root / "cases/complexity/agent_eval/report.md",
                       root / "scripts/build_site.py", root / "verdict/catalog.py"]
    expected_inputs = {str(path.relative_to(root)): _digest(path)
                       for path in expected_inputs if path.is_file()}
    if manifest.get("inputs") != expected_inputs:
        raise ValueError("site source digests are stale; run scripts/build_site.py")
    generated = set(manifest.get("generated", []))
    outputs = manifest.get("outputs", {})
    if set(outputs) != generated:
        raise ValueError("site output digest keys differ from generated files")
    for rel in generated:
        path = root / "docs" / rel
        if not path.is_file() or outputs[rel] != _digest(path):
            raise ValueError(f"generated site output is stale or altered: {rel}")
    return f"{len(expected_inputs)} inputs -> {len(generated)} outputs"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = audit()
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for item in result["checks"]:
            print(f"  {'PASS' if item['ok'] else 'FAIL'}  {item['name']}: {item['detail']}")
        print(f"\n{result['summary']['passed']} passed, {result['summary']['failed']} failed")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
