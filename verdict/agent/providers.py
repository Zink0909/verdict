"""Case-scoped tool providers for the research-audit Agent.

The complexity case has an executable analysis adapter. Retrofitted cases expose
their pinned, hashed result documents through a read-only evidence adapter. The
mode is explicit in every run so replaying evidence is never presented as a new
computation.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from ..catalog import CASE_BY_ID
from . import tools as complexity_tools

ROOT = Path(__file__).resolve().parents[2]


def _tool(name: str, description: str, props: dict, required: list[str]) -> dict:
    return {
        "name": name,
        "description": description,
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": props,
            "required": required,
            "additionalProperties": False,
        },
    }


@dataclass(frozen=True)
class ToolProvider:
    case_id: str
    mode: str
    definitions_fn: Callable[[], list[dict]]
    run_fn: Callable[[str, dict], dict]

    def definitions(self) -> list[dict]:
        return self.definitions_fn()

    def run_tool(self, name: str, arguments: dict) -> dict:
        return self.run_fn(name, arguments)

    @staticmethod
    def collect_numbers(results: list[dict]) -> list[float]:
        return complexity_tools.collect_numbers(results)


def _complexity_provider() -> ToolProvider:
    return ToolProvider(
        case_id="complexity-voc",
        mode="executable",
        definitions_fn=complexity_tools.definitions,
        run_fn=complexity_tools.run_tool,
    )


def _evidence_documents(case_id: str) -> dict[str, Path]:
    spec = CASE_BY_ID[case_id]
    case_dir = ROOT / "cases" / spec.folder
    docs = {rel: case_dir / rel for rel in spec.result_files if rel.endswith(".json")}
    missing = [rel for rel, path in docs.items() if not path.is_file()]
    if not docs or missing:
        raise ValueError(f"{case_id}: readable JSON evidence is unavailable: {missing}")
    return docs


def _evidence_provider(case_id: str) -> ToolProvider:
    docs = _evidence_documents(case_id)

    def load_document(path: Path):
        return json.loads(path.read_text())

    def sections(path: Path) -> list[str]:
        payload = load_document(path)
        return sorted(payload) if isinstance(payload, dict) else ["$"]

    def definitions() -> list[dict]:
        return [
            _tool(
                "describe_case_evidence",
                "Describe the pinned result documents available for this specific Verdict "
                "case, including their top-level sections and the fact that this adapter "
                "replays existing evidence rather than recomputing the study.",
                {}, [],
            ),
            _tool(
                "read_case_result",
                "Read one top-level section from a pinned result document for this specific "
                "case. Every returned number comes from the case artifact on disk; use the "
                "description tool first to discover valid document and section names.",
                {
                    "document": {"type": "string", "enum": sorted(docs)},
                    "section": {"type": "string"},
                },
                ["document", "section"],
            ),
        ]

    def run(name: str, arguments: dict) -> dict:
        allowed = {d["name"]: d for d in definitions()}
        if name not in allowed:
            raise KeyError(f"unknown tool {name!r}; available: {', '.join(allowed)}")
        unknown = set(arguments) - set(allowed[name]["input_schema"]["properties"])
        if unknown:
            raise TypeError(f"{name} got unexpected argument(s): {', '.join(sorted(unknown))}")
        if name == "describe_case_evidence":
            return {
                "case_id": case_id,
                "execution_mode": "evidence-readonly",
                "documents": {
                    rel: sections(path) for rel, path in docs.items()
                },
                "warning": "pinned evidence replay; this call does not recompute the study",
            }
        document = arguments.get("document")
        section = arguments.get("section")
        if document not in docs:
            raise ValueError(f"document must be one of: {', '.join(docs)}")
        data = load_document(docs[document])
        if section == "$":
            value = data
        elif isinstance(data, dict) and section in data:
            value = data[section]
        else:
            raise ValueError(
                f"section {section!r} not found; available: {', '.join(sections(docs[document]))}")
        return {"case_id": case_id, "document": document, "section": section,
                "value": value}

    return ToolProvider(case_id, "evidence-readonly", definitions, run)


def get_provider(case_id: str) -> ToolProvider:
    if case_id not in CASE_BY_ID:
        raise ValueError(f"unknown case {case_id!r}")
    spec = CASE_BY_ID[case_id]
    if spec.role == "data-gated":
        raise ValueError(f"agent execution has no provider for data-gated case {case_id!r}")
    if case_id == "complexity-voc":
        return _complexity_provider()
    return _evidence_provider(case_id)


def supported_case_ids() -> tuple[str, ...]:
    return tuple(case.card_id for case in CASE_BY_ID.values() if case.role != "data-gated")
