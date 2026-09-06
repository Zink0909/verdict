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

import numpy as np
import pandas as pd

from ..catalog import CASE_BY_ID
from .. import costs, evaluate
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


def return_series_provider(frame: pd.DataFrame, *, periods_per_year: int = 12,
                           turnover: float = 1.0) -> ToolProvider:
    """Create a deterministic provider over a user-supplied return CSV.

    This evaluates already-produced outcome series.  It intentionally does not
    claim to reconstruct the paper's signal, verify point-in-time inputs, or
    prove that the series came from the described strategy.
    """
    required = {"date", "return"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError("CSV must contain columns: " + ", ".join(sorted(required)))
    if not isinstance(periods_per_year, int) or not 1 <= periods_per_year <= 365:
        raise ValueError("periods_per_year must be an integer from 1 to 365")
    if not np.isfinite(turnover) or turnover < 0:
        raise ValueError("turnover must be finite and non-negative")

    data = frame.copy()
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    if data["date"].isna().any():
        raise ValueError("CSV date column contains an unreadable date")
    if data["date"].duplicated().any() or not data["date"].is_monotonic_increasing:
        raise ValueError("CSV dates must be unique and ascending")
    numeric = [column for column in data.columns if column != "date"]
    if not numeric:
        raise ValueError("CSV must include a return column")
    for column in numeric:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    if data["return"].isna().any() or not np.isfinite(data["return"]).all():
        raise ValueError("CSV return column must contain only finite numeric values")
    if len(data) < 12:
        raise ValueError("CSV needs at least 12 dated return observations")
    benchmarks = [column for column in numeric if column != "return"
                  and data[column].notna().any()]
    for column in benchmarks:
        if not np.isfinite(data.loc[data[column].notna(), column]).all():
            raise ValueError(f"CSV benchmark {column!r} contains a non-finite value")

    def definitions() -> list[dict]:
        tools = [
            _tool(
                "describe_return_series",
                "Describe the user-supplied dated outcome series. It is not a reproduction "
                "of a paper strategy and this adapter cannot audit point-in-time inputs, "
                "signal construction, or the provenance of the supplied returns.", {}, []),
            _tool(
                "evaluate_return_series",
                "Compute the locked descriptive battery for the user-supplied return series: "
                "mean, annualized Sharpe, and fixed moving-block bootstrap intervals. "
                "These are deterministic calculations, not a strategy reconstruction.", {}, []),
            _tool(
                "cost_sensitivity",
                "Charge the declared constant turnover through a locked 0/5/10/20 bps grid "
                "and report net return, Sharpe, and the linear breakeven cost. This is an "
                "assumption sensitivity, not a market-execution simulation.", {}, []),
        ]
        if benchmarks:
            tools.append(_tool(
                "test_spanning",
                "Regress the supplied return series on every supplied benchmark using HAC "
                "standard errors. This asks whether the outcome series retains incremental "
                "alpha beyond those benchmarks, not whether a paper's signal was reproduced.",
                {}, []))
        return tools

    def run(name: str, arguments: dict) -> dict:
        allowed = {definition["name"] for definition in definitions()}
        if name not in allowed:
            raise KeyError(f"unknown tool {name!r}; available: {', '.join(sorted(allowed))}")
        if arguments:
            raise TypeError(f"{name} takes no arguments")
        returns = data["return"]
        boundary = ("user-supplied outcome series only; not a reproduction of the paper "
                    "strategy, and no point-in-time audit or source-data provenance check")
        if name == "describe_return_series":
            return {"execution_mode": "csv-evidence", "n_observations": int(len(data)),
                    "start": data["date"].iloc[0].date().isoformat(),
                    "end": data["date"].iloc[-1].date().isoformat(),
                    "periods_per_year": periods_per_year, "benchmarks": benchmarks,
                    "boundary": boundary}
        if name == "evaluate_return_series":
            mean_ci = evaluate.block_bootstrap_mean_ci(returns, n_boot=500, block=6, seed=0)
            sharpe_ci = evaluate.block_bootstrap_sharpe_ci(
                returns, n_boot=500, block=6, seed=0, periods_per_year=periods_per_year)
            return {"mean_per_period": float(returns.mean()),
                    "mean_annualized": float(returns.mean() * periods_per_year),
                    "sharpe_annualized": evaluate.sharpe(returns, periods_per_year),
                    "mean_ci_95": list(mean_ci), "sharpe_ci_95": list(sharpe_ci),
                    "bootstrap": {"method": "moving-block", "draws": 500, "block": 6,
                                  "seed": 0}, "boundary": boundary}
        if name == "cost_sensitivity":
            grid = costs.cost_sensitivity(returns, turnover, periods_per_year=periods_per_year)
            return {"turnover_assumption": float(turnover),
                    "cost_grid": grid.reset_index().to_dict(orient="records"),
                    "breakeven_cost_bps": costs.breakeven_cost_bps(float(returns.mean()), turnover),
                    "boundary": boundary}
        return {"benchmarks": benchmarks,
                "spanning": evaluate.spanning(returns, data[benchmarks], hac_lags=3),
                "boundary": boundary}

    return ToolProvider("uploaded-return-series", "csv-evidence", definitions, run)


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
