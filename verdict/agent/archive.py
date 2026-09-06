"""Local, content-addressed evidence packages for paper-audit runs.

These packages deliberately live outside the public claim register.  A paper
audit is a working record until a person promotes it through the normal case
contract; saving it must not make it look like a published Verdict case.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
from numbers import Real
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .pipeline import AuditRun

SCHEMA_VERSION = 1


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write(path: Path, data: bytes) -> None:
    """Atomically write one immutable artifact into a new package directory."""
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    temporary.write_bytes(data)
    os.replace(temporary, path)


def _json_safe(value: object) -> object:
    """JSON has no NaN; record an unavailable numeric result as null, not a lie."""
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, Real):
        numeric = float(value)
        return numeric if math.isfinite(numeric) else None
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _json(value: object) -> bytes:
    return (json.dumps(_json_safe(value), indent=2, sort_keys=True, ensure_ascii=False,
                       allow_nan=False) + "\n").encode("utf-8")


def _safe_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:48] or "paper-audit"


def save_audit_package(root: Path, *, paper_text: str, origin: str,
                       run: AuditRun, extra_artifacts: dict[str, bytes] | None = None) -> Path:
    """Persist an approved run and return its new local evidence-package directory.

    ``root`` is normally ``.verdict-workspace/audits`` (ignored by git).  The
    manifest hashes every artifact, so a reviewer can later see exactly which
    text, protocol, tool transcript, and supplied evidence produced the state.
    """
    if not run.approved:
        raise ValueError("only human-approved paper-audit runs may be archived")
    if not paper_text.strip():
        raise ValueError("an evidence package requires the paper text used for extraction")

    now = datetime.now(timezone.utc)
    package = root / f"{now:%Y%m%dT%H%M%SZ}-{_safe_label(run.case_id or 'data-gated')}-{uuid4().hex[:8]}"
    package.mkdir(parents=True, exist_ok=False)
    artifacts: dict[str, bytes] = {
        "paper.txt": paper_text.encode("utf-8"),
        "claim.json": _json(run.claim.to_dict() if run.claim else None),
        "protocol.json": _json(run.protocol.to_dict() if run.protocol else None),
        "approval.json": _json({"approved": True, "approved_at": now.isoformat()}),
        "tool_trace.json": _json(run.tool_trace),
        "number_audit.json": _json(run.number_audit),
        "run.json": _json(run.to_dict()),
    }
    if run.verdict_text:
        artifacts["verdict.md"] = run.verdict_text.encode("utf-8") + b"\n"
    for name, data in (extra_artifacts or {}).items():
        candidate = Path(name)
        if candidate.name != name or not name or name == "manifest.json":
            raise ValueError(f"unsafe or reserved evidence artifact name: {name!r}")
        if not isinstance(data, bytes):
            raise TypeError(f"evidence artifact {name!r} must be bytes")
        artifacts[name] = data

    for name, data in artifacts.items():
        _write(package / name, data)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "created_at": now.isoformat(),
        "kind": "local-paper-audit-evidence-package",
        "origin": origin,
        "case_id": run.case_id,
        "execution_mode": run.execution_mode,
        "state": run.state,
        "public_registry_status": "not-published",
        "artifacts": {name: {"sha256": _sha256(data), "bytes": len(data)}
                      for name, data in sorted(artifacts.items())},
    }
    _write(package / "manifest.json", _json(manifest))
    return package
