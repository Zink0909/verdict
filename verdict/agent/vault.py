"""Read-only inspection, verification, comparison, and export of local audit packages.

The Vault is deliberately separate from the public registry.  It makes working
paper audits reviewable without promoting them into published Verdict evidence.
"""
from __future__ import annotations

import difflib
import hashlib
import io
import json
import zipfile
from pathlib import Path
from typing import Any

from .archive import SCHEMA_VERSION


def _safe_package(root: Path, package: Path) -> Path:
    root, package = root.resolve(), package.resolve()
    if package.parent != root:
        raise ValueError("audit package must be an immediate child of the configured vault")
    return package


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_package(root: Path, package: Path) -> dict:
    """Verify every declared artifact hash; malformed packages fail closed."""
    package = _safe_package(root, package)
    errors: list[str] = []
    manifest_path = package / "manifest.json"
    try:
        manifest = _read_json(manifest_path)
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "package": package.name, "errors": [f"manifest: {exc}"],
                "manifest": None, "checked": 0}
    if manifest.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"unsupported schema_version: {manifest.get('schema_version')!r}")
    if manifest.get("kind") != "local-paper-audit-evidence-package":
        errors.append("manifest kind is not a local paper-audit evidence package")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or not artifacts:
        errors.append("manifest has no artifact map")
        artifacts = {}
    declared = set()
    for name, metadata in artifacts.items():
        candidate = Path(name)
        if candidate.name != name or not name:
            errors.append(f"unsafe artifact name in manifest: {name!r}")
            continue
        declared.add(name)
        path = package / name
        if not path.is_file():
            errors.append(f"missing artifact: {name}")
            continue
        data = path.read_bytes()
        if not isinstance(metadata, dict):
            errors.append(f"invalid metadata: {name}")
            continue
        if metadata.get("bytes") != len(data):
            errors.append(f"byte count mismatch: {name}")
        if metadata.get("sha256") != hashlib.sha256(data).hexdigest():
            errors.append(f"hash mismatch: {name}")
    actual = {path.name for path in package.iterdir() if path.is_file()} - {"manifest.json"}
    for name in sorted(actual - declared):
        errors.append(f"undeclared artifact: {name}")
    return {"ok": not errors, "package": package.name, "errors": errors,
            "manifest": manifest, "checked": len(declared)}


def list_packages(root: Path) -> list[dict]:
    """Return compact, newest-first Vault records without trusting them implicitly."""
    if not root.exists():
        return []
    rows = []
    for package in root.iterdir():
        if not package.is_dir() or package.name.startswith("."):
            continue
        check = verify_package(root, package)
        manifest = check["manifest"] or {}
        rows.append({"path": package, "name": package.name, "ok": check["ok"],
                     "errors": check["errors"], "created_at": manifest.get("created_at", ""),
                     "case_id": manifest.get("case_id", ""),
                     "state": manifest.get("state", ""),
                     "execution_mode": manifest.get("execution_mode", ""),
                     "origin": manifest.get("origin", "")})
    return sorted(rows, key=lambda row: (row["created_at"], row["name"]), reverse=True)


def load_package(root: Path, package: Path) -> dict:
    """Read an integrity-checked package into a compact review record."""
    check = verify_package(root, package)
    if not check["ok"]:
        raise ValueError("cannot load an invalid package: " + "; ".join(check["errors"]))
    package = _safe_package(root, package)
    contents: dict[str, Any] = {"manifest": check["manifest"]}
    paper = package / "paper.txt"
    if paper.is_file():
        contents["paper"] = paper.read_text(encoding="utf-8")
    for name in ("claim.json", "protocol.json", "approval.json", "tool_trace.json",
                 "number_audit.json", "run.json"):
        path = package / name
        if path.is_file():
            contents[name.removesuffix(".json")] = _read_json(path)
    verdict = package / "verdict.md"
    if verdict.is_file():
        contents["verdict"] = verdict.read_text(encoding="utf-8")
    return contents


def artifact_bytes(root: Path, package: Path, name: str) -> bytes:
    """Return one declared artifact only after the entire package verifies."""
    check = verify_package(root, package)
    if not check["ok"]:
        raise ValueError("cannot read an artifact from an invalid package")
    if name not in check["manifest"]["artifacts"]:
        raise ValueError(f"artifact is not declared by this package: {name}")
    package = _safe_package(root, package)
    return (package / name).read_bytes()


def compare_packages(root: Path, left: Path, right: Path) -> dict:
    """Compare two verified records, preserving a reviewer-readable JSON diff."""
    left, right = _safe_package(root, left), _safe_package(root, right)
    if left == right:
        raise ValueError("choose two different audit packages to compare")
    a, b = load_package(root, left), load_package(root, right)
    fields = ("claim", "protocol", "run", "number_audit")
    differences = {}
    for field in fields:
        first = json.dumps(a.get(field), indent=2, sort_keys=True, ensure_ascii=False).splitlines()
        second = json.dumps(b.get(field), indent=2, sort_keys=True, ensure_ascii=False).splitlines()
        diff = list(difflib.unified_diff(first, second, fromfile=left.name, tofile=right.name,
                                         lineterm=""))
        if diff:
            differences[field] = "\n".join(diff)
    return {"left": a["manifest"], "right": b["manifest"], "same_paper":
            a["manifest"]["artifacts"]["paper.txt"]["sha256"] ==
            b["manifest"]["artifacts"]["paper.txt"]["sha256"],
            "differences": differences}


def package_zip(root: Path, package: Path) -> bytes:
    """Export one verified package as a portable ZIP without mutating it."""
    check = verify_package(root, package)
    if not check["ok"]:
        raise ValueError("cannot export an invalid package")
    package = _safe_package(root, package)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(package.iterdir()):
            if path.is_file():
                archive.writestr(f"{package.name}/{path.name}", path.read_bytes())
    return out.getvalue()
