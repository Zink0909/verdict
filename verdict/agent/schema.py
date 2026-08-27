"""The two documents the agent produces before it is allowed to touch data.

A **claim card** is what the paper says, in a fixed shape: the signal, the
universe, the frequency, the claimed effect, the sample, the source, and what
data would be needed to test it. Forcing extraction into a schema is what makes
the next step possible — you cannot pre-register a protocol against a claim you
have only paraphrased.

A **protocol** is how the claim will be tested, written down *before* the data
is touched: what data, how to split it, what to compare against, how costs are
charged, which diagnostics run if the answer is no, and — the part everyone
skips — what result would kill the claim. A protocol without kill criteria is a
plan to find something.

Both are JSON-schema-constrained so the model's output is validated rather than
parsed hopefully, and both are plain dataclasses afterwards so the rest of the
system never touches model output directly.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field


def _obj(props: dict, required: list[str]) -> dict:
    """A closed object schema — no additional properties, everything required."""
    return {"type": "object", "properties": props, "required": required,
            "additionalProperties": False}


_STR = {"type": "string"}
_STRS = {"type": "array", "items": {"type": "string"}}


CLAIM_CARD_SCHEMA = _obj({
    "signal": {**_STR, "description": "The predictor or rule, precisely enough to rebuild it"},
    "universe": {**_STR, "description": "What it is applied to"},
    "frequency": {**_STR, "description": "Rebalancing or forecast frequency"},
    "claimed_effect": {**_STR, "description": "The effect the source claims, with its magnitude"},
    "sample": {**_STR, "description": "Sample period and size the claim rests on"},
    "source": {**_STR, "description": "Author, year, venue"},
    "data_needs": _STRS,
}, ["signal", "universe", "frequency", "claimed_effect", "sample", "source", "data_needs"])


PROTOCOL_SCHEMA = _obj({
    "data_requirements": _STRS,
    "splits": {**_STR, "description": "How the sample is divided in time, and what is sealed"},
    "benchmarks": {**_STRS, "description": "What the claim must beat to count as new"},
    "cost_model": {**_STR, "description": "How trading frictions are charged"},
    "diagnostics": {**_STRS, "description": "Mechanism tests to run, especially if the answer is no"},
    "robustness": {**_STRS, "description": "What gets perturbed to see if the conclusion holds"},
    "kill_criteria": {**_STRS, "description": "Results that would falsify the claim. Required."},
    "rationale": {**_STR, "description": "Why this protocol tests this claim and not another"},
}, ["data_requirements", "splits", "benchmarks", "cost_model", "diagnostics",
    "robustness", "kill_criteria", "rationale"])


@dataclass
class ClaimCard:
    signal: str
    universe: str
    frequency: str
    claimed_effect: str
    sample: str
    source: str
    data_needs: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ClaimCard":
        missing = [k for k in CLAIM_CARD_SCHEMA["required"] if not d.get(k)]
        if missing:
            raise ValueError(f"claim card is missing: {', '.join(missing)}")
        return cls(**{k: d[k] for k in CLAIM_CARD_SCHEMA["properties"]})


@dataclass
class Protocol:
    data_requirements: list[str]
    splits: str
    benchmarks: list[str]
    cost_model: str
    diagnostics: list[str]
    robustness: list[str]
    kill_criteria: list[str]
    rationale: str
    preregistered: bool = True

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Protocol":
        missing = [k for k in PROTOCOL_SCHEMA["required"] if not d.get(k)]
        if missing:
            raise ValueError(f"protocol is missing: {', '.join(missing)}")
        if not [k for k in d["kill_criteria"] if k.strip()]:
            raise ValueError(
                "a protocol with no kill criteria is not a protocol — it is a plan to "
                "find something")
        return cls(**{k: d[k] for k in PROTOCOL_SCHEMA["properties"]})

    def items(self) -> list[str]:
        """Every testable line in the protocol, flattened — what evals score."""
        return [*self.benchmarks, *self.diagnostics, *self.robustness, *self.kill_criteria,
                self.splits, self.cost_model]
