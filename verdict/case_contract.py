"""Shared execution and evidence contract for every Verdict case.

Cases may use different domain models, but they must expose the same operational
surface: declared commands, result artifacts, reports, protocol coverage, and a
deterministic evidence manifest.  This is the boundary between a case study and
the platform that runs and publishes it.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CaseSpec:
    card_id: str
    folder: str
    role: str
    evidence_pattern: str
    run_steps: tuple[tuple[str, ...], ...] = ()
    report_steps: tuple[tuple[str, ...], ...] = ()
    result_files: tuple[str, ...] = ()
    required_artifacts: tuple[str, ...] = ("report.md", "report.html")
    protocol_gaps: tuple[str, ...] = ()
    agent_mode: str = "evidence-readonly"

    @property
    def protocol_complete(self) -> bool:
        return not self.protocol_gaps

    @property
    def is_executable(self) -> bool:
        return bool(self.run_steps)


@dataclass(frozen=True)
class ArtifactDigest:
    path: str
    sha256: str
    bytes: int

    @classmethod
    def from_path(cls, path: Path, relative_to: Path) -> "ArtifactDigest":
        payload = path.read_bytes()
        return cls(
            path=str(path.relative_to(relative_to)),
            sha256=hashlib.sha256(payload).hexdigest(),
            bytes=len(payload),
        )


@dataclass(frozen=True)
class CaseResult:
    """Normalized evidence envelope; domain metrics stay in declared result files."""
    schema_version: int
    case_id: str
    role: str
    state: str
    evidence_pattern: str
    protocol_complete: bool
    protocol_gaps: tuple[str, ...]
    agent_mode: str
    artifacts: tuple[ArtifactDigest, ...]

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "case_id": self.case_id,
            "role": self.role,
            "state": self.state,
            "evidence_pattern": self.evidence_pattern,
            "protocol_coverage": {
                "complete": self.protocol_complete,
                "gaps": list(self.protocol_gaps),
            },
            "agent_mode": self.agent_mode,
            "artifacts": [a.__dict__ for a in self.artifacts],
        }

    @classmethod
    def build(cls, spec: CaseSpec, root: Path, state: str) -> "CaseResult":
        case_dir = root / "cases" / spec.folder
        paths = [root / "registry" / f"{spec.card_id}.json"]
        paths += [case_dir / rel for rel in (*spec.result_files, *spec.required_artifacts)]
        missing = [str(p.relative_to(root)) for p in paths if not p.is_file()]
        if missing:
            raise ValueError(f"{spec.card_id}: missing required artifact(s): {', '.join(missing)}")
        digests = tuple(ArtifactDigest.from_path(p, root) for p in paths)
        return cls(
            schema_version=1,
            case_id=spec.card_id,
            role=spec.role,
            state=state,
            evidence_pattern=spec.evidence_pattern,
            protocol_complete=spec.protocol_complete,
            protocol_gaps=spec.protocol_gaps,
            agent_mode=spec.agent_mode,
            artifacts=digests,
        )

    def write(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{path.name}.tmp")
        tmp.write_text(json.dumps(self.to_dict(), indent=2) + "\n")
        tmp.replace(path)
        return path


def load_case_result(path: Path) -> dict:
    data = json.loads(path.read_text())
    required = {"schema_version", "case_id", "state", "protocol_coverage", "artifacts"}
    if not isinstance(data, dict) or not required.issubset(data):
        raise ValueError(f"invalid normalized case result: {path}")
    if data["schema_version"] != 1:
        raise ValueError(f"unsupported case-result schema: {data['schema_version']}")
    return data
