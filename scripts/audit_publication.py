#!/usr/bin/env python3
"""Audit pre-release data coverage, review status, size risk, and obvious secrets.

Default mode reports unresolved publication decisions and exits successfully so
the inventory can be inspected during development.  ``--strict`` is the v1.0
release gate: every tracked data-like artifact must be covered and every group
must have documented approval.

This scanner cannot determine contractual permission, recognize all PII, or
prove that a derived dataset is non-confidential.  Those are explicit human
sign-offs in ``governance/publication_data.json`` rather than conclusions inferred from a
regex.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "governance" / "publication_data.json"
DATA_SUFFIXES = {".csv", ".xlsx", ".xls", ".mat", ".parquet", ".zip", ".pdf"}
SECRET_PATTERNS = {
    "private-key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "credential-assignment": re.compile(
        r"(?i)(?:api[_-]?key|secret|password|access[_-]?token)\s*[:=]\s*['\"][^'\"\s]{8,}['\"]"),
}


def tracked_files(root: Path = ROOT) -> list[str]:
    result = subprocess.run(["git", "ls-files", "-z"], cwd=root, check=True,
                            capture_output=True)
    return sorted(path for path in result.stdout.decode().split("\0") if path)


def data_like(paths: list[str]) -> set[str]:
    return {path for path in paths
            if Path(path).suffix.lower() in DATA_SUFFIXES
            or "/data/" in f"/{path}" or "/source/" in f"/{path}"}


def _covered(path: str, declarations: list[str]) -> bool:
    return any(path == declared or (declared.endswith("/") and path.startswith(declared))
               for declared in declarations)


def scan_secrets(root: Path, paths: list[str]) -> list[dict]:
    findings = []
    for relative in paths:
        path = root / relative
        if not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        raw = path.read_bytes()
        if b"\0" in raw:
            continue
        text = raw.decode("utf-8", errors="ignore")
        for kind, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                findings.append({"path": relative, "kind": kind})
    return findings


def audit(root: Path = ROOT) -> dict:
    manifest = json.loads((root / "governance" / "publication_data.json").read_text())
    if manifest.get("schema_version") != 1:
        raise ValueError("publication manifest schema must be 1")
    allowed = set(manifest.get("allowed_statuses", []))
    groups = manifest.get("groups", [])
    if not groups or len({group.get("id") for group in groups}) != len(groups):
        raise ValueError("publication groups must be non-empty and have unique ids")
    declarations = []
    malformed = []
    unresolved = []
    for group in groups:
        declarations.extend(group.get("paths", []))
        missing = [field for field in ("id", "paths", "origin", "status", "required_evidence")
                   if not group.get(field)]
        if missing or group.get("status") not in allowed:
            malformed.append({"id": group.get("id"), "missing": missing,
                              "status": group.get("status")})
        if group.get("status") != "approved":
            unresolved.append({"id": group.get("id"), "status": group.get("status"),
                               "required_evidence": group.get("required_evidence")})

    tracked = tracked_files(root)
    candidates = data_like(tracked)
    uncovered = sorted(path for path in candidates if not _covered(path, declarations))
    empty_declarations = sorted(declared for declared in declarations
                                if not any(_covered(path, [declared]) for path in candidates))
    large = [{"path": path, "bytes": (root / path).stat().st_size}
             for path in sorted(candidates) if (root / path).stat().st_size >= 50_000_000]
    secrets = scan_secrets(root, tracked)
    release_ready = not any((malformed, uncovered, empty_declarations, unresolved, secrets))
    return {
        "schema_version": 1,
        "release_ready": release_ready,
        "summary": {"tracked_data_artifacts": len(candidates), "groups": len(groups),
                    "unresolved_groups": len(unresolved), "uncovered_artifacts": len(uncovered),
                    "obvious_secret_findings": len(secrets), "large_artifacts": len(large)},
        "unresolved": unresolved, "uncovered": uncovered,
        "empty_declarations": empty_declarations, "malformed": malformed,
        "obvious_secret_findings": secrets, "large_artifacts": large,
        "human_boundary": (
            "No automated scan can grant redistribution permission or prove the absence of "
            "confidential information. Required evidence must be reviewed by the owner."),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true",
                        help="exit non-zero until every publication group is approved")
    parser.add_argument("--json", action="store_true", help="emit the full JSON report")
    args = parser.parse_args()
    report = audit()
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        summary = report["summary"]
        print(f"tracked data artifacts: {summary['tracked_data_artifacts']}")
        print(f"coverage gaps: {summary['uncovered_artifacts']}")
        print(f"obvious secret findings: {summary['obvious_secret_findings']}")
        print(f"publication groups awaiting review: {summary['unresolved_groups']}")
        for item in report["unresolved"]:
            print(f"  {item['id']}: {item['status']}")
        for item in report["large_artifacts"]:
            print(f"  large: {item['path']} ({item['bytes'] / 1_000_000:.1f} MB)")
        print("RELEASE READY" if report["release_ready"] else "NOT RELEASE READY")
        print(report["human_boundary"])
    return 1 if args.strict and not report["release_ready"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
