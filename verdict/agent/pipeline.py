"""The closed loop: paper in, verdict out — with the model kept off the numbers.

    extract  ->  pre-register  ->  [human approves]  ->  execute  ->  write  ->  audit

Two properties are structural rather than aspirational. The protocol is written
and approved **before** any tool runs, so it cannot be retrofitted to the
result. And the written verdict is checked against the tool results afterwards,
so a number the model invented is caught rather than published.

The loop is hand-written on the bare Messages API. That is the point: a reader
who wants to know what the agent was allowed to do can read this file, and the
transcript records every call and every value that came back.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable

from . import guardrails, providers
from .llm import Model, Reply
from .schema import CLAIM_CARD_SCHEMA, PROTOCOL_SCHEMA, ClaimCard, Protocol

MAX_TOOL_STEPS = 10

EXTRACT_SYSTEM = """\
You extract a testable claim from a research paper.

Read the paper and fill in the claim card. Be precise enough that someone could
rebuild the signal from your description alone: the exact predictor set, the
transformation, the estimator, the window. Where the paper reports several
results, take the headline claim the abstract leads with.

Report the claimed effect with the magnitude the paper states. Do not evaluate
whether the claim is true — that is the rest of the pipeline's job, and forming
a view now would bias the protocol you write next."""

PROTOCOL_SYSTEM = """\
You design a pre-registered test protocol for a claim, before seeing any data.

The protocol is binding: it is written now and cannot be revised once results
exist. Write it so that a sceptical reader would accept the answer whichever way
it comes out.

Cover what data is needed, how the sample is split in time, what the claim must
beat to count as new information, how trading frictions are charged, what
diagnostics run if the answer is negative, and what gets perturbed to check the
conclusion is not an artefact of one arbitrary choice.

Kill criteria are required and are the part most protocols get wrong. State
results that would falsify the claim — not results that would disappoint you.

A claim can be mechanically true and still be uninformative: consider what a
simple alternative would produce on the same data, and how you would tell the
two apart. Design a test that could distinguish them."""

EXECUTE_SYSTEM = """\
You are executing an approved protocol using the tools provided.

You cannot compute. Every number must come from a tool result; do not estimate,
extrapolate, or carry a figure over from the paper. If a tool does not exist for
something the protocol asks for, say so plainly and move on — an honest gap is
part of the finding.

Work through the protocol's diagnostics. Start by describing the dataset, then
reproduce the claimed effect, then run the tests that would distinguish a real
effect from a mechanical one. Stop when the protocol's questions are answered."""

WRITE_SYSTEM = """\
You write the verdict from results that already exist.

Every number in what you write must appear in the tool results you were given.
Do not round to a different figure, convert units, or infer a quantity that was
not returned — an automated check compares your text against the results and
flags anything unsupported.

State the verdict plainly, including when it is negative. Then explain the
mechanism the diagnostics revealed, because "it does not work" without a reason
wastes the experiment. Close with the honest limitations: what this run cannot
settle, and what a reader should not conclude from it."""


@dataclass
class AuditRun:
    case_id: str = ""
    execution_mode: str = ""
    claim: ClaimCard | None = None
    protocol: Protocol | None = None
    approved: bool = False
    tool_trace: list[dict] = field(default_factory=list)
    verdict_text: str = ""
    number_audit: dict = field(default_factory=dict)
    state: str = "in-progress"
    notes: list[str] = field(default_factory=list)

    @property
    def results(self) -> list[dict]:
        return [step["result"] for step in self.tool_trace if "result" in step]

    def to_dict(self) -> dict:
        return {"case_id": self.case_id, "execution_mode": self.execution_mode,
                "state": self.state, "approved": self.approved,
                "claim": self.claim.to_dict() if self.claim else None,
                "protocol": self.protocol.to_dict() if self.protocol else None,
                "tool_trace": self.tool_trace, "verdict_text": self.verdict_text,
                "number_audit": self.number_audit, "notes": self.notes}


def extract_claim(model: Model, paper_text: str) -> ClaimCard:
    reply = model.complete(
        system=EXTRACT_SYSTEM,
        messages=[{"role": "user", "content": paper_text}],
        schema=CLAIM_CARD_SCHEMA, effort="high")
    return ClaimCard.from_dict(reply.parsed or json.loads(reply.text))


def draft_protocol(model: Model, claim: ClaimCard, available_tools: list[str] | None = None) -> Protocol:
    """Draft the protocol from the claim alone — no critique literature, no data."""
    ask = ("Design the pre-registered protocol for this claim.\n\n"
           + json.dumps(claim.to_dict(), indent=2))
    if available_tools:
        ask += ("\n\nTools that will be available at execution time:\n- "
                + "\n- ".join(available_tools))
    reply = model.complete(system=PROTOCOL_SYSTEM,
                           messages=[{"role": "user", "content": ask}],
                           schema=PROTOCOL_SCHEMA, effort="xhigh")
    return Protocol.from_dict(reply.parsed or json.loads(reply.text))


def execute_protocol(model: Model, claim: ClaimCard, protocol: Protocol,
                     provider: providers.ToolProvider,
                     max_steps: int = MAX_TOOL_STEPS) -> list[dict]:
    """The tool loop. The model chooses calls; this function runs them."""
    if max_steps <= 0:
        raise ValueError("max_steps must be positive")
    messages: list[dict] = [{"role": "user", "content":
                             "Claim:\n" + json.dumps(claim.to_dict(), indent=2)
                             + "\n\nApproved protocol:\n" + json.dumps(protocol.to_dict(), indent=2)
                             + f"\n\nProvider mode: {provider.mode}."
                             + (" Read the pinned evidence and identify coverage gaps; do not "
                                "describe it as a fresh recomputation."
                                if provider.mode == "evidence-readonly" else "")
                             + "\n\nExecute it."}]
    trace: list[dict] = []
    for step in range(max_steps):
        reply: Reply = model.complete(system=EXECUTE_SYSTEM, messages=messages,
                                      tools=provider.definitions(), effort="high")
        if not reply.wants_tools:
            trace.append({"step": step, "status": "execution-complete",
                          "note": reply.text or "execution complete"})
            break
        messages.append({"role": "assistant", "content": reply.raw.content if reply.raw
                         else [{"type": "tool_use", "id": c.id, "name": c.name,
                                "input": c.arguments} for c in reply.tool_calls]})
        results = []
        for call in reply.tool_calls:
            entry: dict = {"step": step, "tool": call.name, "arguments": call.arguments}
            try:
                entry["result"] = provider.run_tool(call.name, call.arguments)
                content = json.dumps(entry["result"])
                is_error = False
            except Exception as exc:                       # surfaced, never swallowed
                entry["error"] = f"{type(exc).__name__}: {exc}"
                content, is_error = entry["error"], True
            trace.append(entry)
            results.append({"type": "tool_result", "tool_use_id": call.id,
                            "content": content, "is_error": is_error})
        messages.append({"role": "user", "content": results})
    else:
        trace.append({"step": max_steps, "status": "max-steps-exhausted",
                      "note": "execution stopped before the model declared completion"})
    return trace


def draft_verdict(model: Model, claim: ClaimCard, protocol: Protocol,
                  trace: list[dict]) -> str:
    ask = ("Claim:\n" + json.dumps(claim.to_dict(), indent=2)
           + "\n\nProtocol:\n" + json.dumps(protocol.to_dict(), indent=2)
           + "\n\nResults:\n" + json.dumps([t for t in trace if "result" in t], indent=2)
           + "\n\nWrite the verdict.")
    return model.complete(system=WRITE_SYSTEM,
                          messages=[{"role": "user", "content": ask}], effort="high").text


def data_gated_audit(claim: ClaimCard, protocol: Protocol, blocker: str,
                     case_id: str = "") -> AuditRun:
    """Record an approved protocol when Verdict has no honest execution adapter."""
    if not blocker.strip():
        raise ValueError("a data-gated audit must name the missing data or execution adapter")
    return AuditRun(
        case_id=case_id,
        execution_mode="data-gated",
        claim=claim,
        protocol=protocol,
        approved=True,
        state="protocol-ready-data-gated",
        notes=["claim extracted and protocol pre-registered; no deterministic provider was "
               f"available, so no verdict was issued: {blocker.strip()}"],
    )


def execute_approved_protocol(model: Model, claim: ClaimCard, protocol: Protocol,
                              case_id: str, max_steps: int = MAX_TOOL_STEPS,
                              request: str | None = None) -> AuditRun:
    """Run an already displayed and human-approved protocol without re-drafting it."""
    if request:
        guardrails.check_request(request)
    provider = providers.get_provider(case_id)
    run = AuditRun(case_id=case_id, execution_mode=provider.mode, claim=claim,
                   protocol=protocol, approved=True)
    if provider.mode == "evidence-readonly":
        run.notes.append(
            "provider replays pinned case evidence read-only; this run does not recompute "
            "the underlying study")

    run.tool_trace = execute_protocol(model, claim, protocol, provider, max_steps=max_steps)
    errors = [step for step in run.tool_trace if "error" in step]
    completed = any(step.get("status") == "execution-complete" for step in run.tool_trace)
    results = [step for step in run.tool_trace if "result" in step]
    if errors or not completed or not results:
        run.state = "in-progress"
        if errors:
            run.notes.append(f"execution failed closed after {len(errors)} tool error(s)")
        if not completed:
            run.notes.append("execution did not complete before the step limit")
        if not results:
            run.notes.append("execution produced no computed results")
        return run

    run.verdict_text = draft_verdict(model, claim, protocol, run.tool_trace)
    run.number_audit = guardrails.audit_numbers(
        run.verdict_text, provider.collect_numbers(run.results),
        context=json.dumps(claim.to_dict()) + json.dumps(protocol.to_dict()))
    if not run.number_audit["clean"]:
        run.state = "draft-withheld"
        run.notes.append(
            "number audit found unsupported figures in the draft: "
            f"{run.number_audit['unsupported']} — the draft is retained with this flag "
            "rather than published")
    else:
        run.state = "verdict-delivered"
    return run


def run_audit(model: Model, paper_text: str, data_available: bool = True,
              approve: Callable[[ClaimCard, Protocol], bool] | None = None,
              max_steps: int = MAX_TOOL_STEPS, request: str | None = None,
              case_id: str = "") -> AuditRun:
    """Paper in, verdict out — stopping honestly wherever it must.

    `approve` is the human in the loop; omitting it does not approve. `data_available=False`
    stops after pre-registration and yields the 'protocol-ready-data-gated' state,
    which is the honest outcome for a claim that cannot be adjudicated here.
    """
    provider = providers.get_provider(case_id)
    run = AuditRun(case_id=case_id, execution_mode=provider.mode)
    if provider.mode == "evidence-readonly":
        run.notes.append(
            "provider replays pinned case evidence read-only; this run does not recompute "
            "the underlying study")
    if request:
        guardrails.check_request(request)          # raises before anything runs

    run.claim = extract_claim(model, paper_text)
    run.protocol = draft_protocol(model, run.claim,
                                  available_tools=[d["name"] for d in provider.definitions()])

    run.approved = False if approve is None else bool(approve(run.claim, run.protocol))
    if not run.approved:
        run.state = "in-progress"
        run.notes.append("protocol not approved; nothing was executed")
        return run

    if not data_available:
        run.state = "protocol-ready-data-gated"
        run.notes.append("claim extracted and protocol pre-registered; the data needed to "
                         "execute it is not available here, so no verdict is issued")
        return run

    run.tool_trace = execute_protocol(model, run.claim, run.protocol, provider,
                                      max_steps=max_steps)
    errors = [step for step in run.tool_trace if "error" in step]
    completed = any(step.get("status") == "execution-complete" for step in run.tool_trace)
    results = [step for step in run.tool_trace if "result" in step]
    if errors or not completed or not results:
        run.state = "in-progress"
        if errors:
            run.notes.append(f"execution failed closed after {len(errors)} tool error(s)")
        if not completed:
            run.notes.append("execution did not complete before the step limit")
        if not results:
            run.notes.append("execution produced no computed results")
        return run

    run.verdict_text = draft_verdict(model, run.claim, run.protocol, run.tool_trace)
    run.number_audit = guardrails.audit_numbers(
        run.verdict_text, provider.collect_numbers(run.results),
        context=json.dumps(run.claim.to_dict()) + json.dumps(run.protocol.to_dict()))
    if not run.number_audit["clean"]:
        run.state = "draft-withheld"
        run.notes.append(
            "number audit found unsupported figures in the draft: "
            f"{run.number_audit['unsupported']} — the draft is retained with this flag "
            "rather than published")
    else:
        run.state = "verdict-delivered"
    return run
