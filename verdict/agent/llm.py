"""The model boundary — bare Messages API, no framework, and swappable.

Two implementations behind one interface:

* `AnthropicModel` calls the Messages API directly. No orchestration framework:
  the tool loop lives in `pipeline.py` where it can be read, logged and audited,
  which is the point of a system whose whole claim is that its numbers are
  checkable.
* `ScriptedModel` replays canned replies. It exists so the entire agent layer —
  schema validation, the tool loop, the guardrails, the number audit — is
  testable offline and deterministically. A component that can only be tested
  by calling a paid API in a nondeterministic mode is a component with no
  regression test.

The model never computes a number that reaches a verdict. It extracts, plans,
selects tools, and writes prose; every quantity comes back from `tools.py`,
which runs the deterministic framework. `guardrails.audit_numbers` enforces
that at the end rather than trusting it.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol as TypingProtocol

MODEL = "claude-opus-5"
MAX_TOKENS = 16_000


class ModelRefused(RuntimeError):
    """The model declined the request; `stop_reason` was 'refusal'."""


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class Reply:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str = "end_turn"
    parsed: dict | None = None
    raw: Any = None

    @property
    def wants_tools(self) -> bool:
        return bool(self.tool_calls)


class Model(TypingProtocol):
    def complete(self, system: str, messages: list[dict], tools: list[dict] | None = None,
                 schema: dict | None = None, effort: str = "high") -> Reply:
        ...


class AnthropicModel:
    """The real thing: `POST /v1/messages` through the official SDK."""

    def __init__(self, model: str = MODEL, max_tokens: int = MAX_TOKENS):
        try:
            import anthropic
        except ModuleNotFoundError as e:      # pragma: no cover - environment dependent
            raise ModuleNotFoundError(
                "the agent layer needs the anthropic SDK: "
                "micromamba run -n verdict pip install anthropic") from e
        self._client = anthropic.Anthropic()   # resolves key or CLI profile from the env
        self.model = model
        self.max_tokens = max_tokens
        self.calls: list[dict] = []

    def complete(self, system: str, messages: list[dict], tools: list[dict] | None = None,
                 schema: dict | None = None, effort: str = "high") -> Reply:
        kwargs: dict = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system,
            "messages": messages,
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": effort},
        }
        if tools:
            kwargs["tools"] = tools
        if schema is not None:
            kwargs["output_config"]["format"] = {"type": "json_schema", "schema": schema}
        response = self._client.messages.create(**kwargs)
        self.calls.append({"messages": len(messages), "tools": len(tools or []),
                           "schema": schema is not None, "effort": effort})

        # Always before reading content: a declined request returns HTTP 200
        # with an empty or partial body.
        if response.stop_reason == "refusal":
            detail = getattr(response, "stop_details", None)
            raise ModelRefused(f"model declined the request ({getattr(detail, 'category', None)})")

        text = "".join(b.text for b in response.content if b.type == "text")
        calls = [ToolCall(id=b.id, name=b.name, arguments=dict(b.input))
                 for b in response.content if b.type == "tool_use"]
        parsed = None
        if schema is not None and text:
            parsed = json.loads(text)
        return Reply(text=text, tool_calls=calls, stop_reason=response.stop_reason,
                     parsed=parsed, raw=response)


class ScriptedModel:
    """Replays prepared replies in order; records what it was asked.

    Used by the regression suite and by `--offline` demos. It is not a mock of
    the API surface — it is a stand-in for the one thing the pipeline needs from
    a model: a reply, possibly with tool calls.
    """

    def __init__(self, replies: list):
        """`replies` are `Reply` objects, or callables that build one from the turn.

        The callable form matters for the write step: a real model composes prose
        around numbers it has just been shown, so a fixture that wants its number
        audit to mean anything has to do the same rather than hard-coding figures
        that were computed at run time.
        """
        self._replies = list(replies)
        self.calls: list[dict] = []

    def complete(self, system: str, messages: list[dict], tools: list[dict] | None = None,
                 schema: dict | None = None, effort: str = "high") -> Reply:
        self.calls.append({"system": system, "messages": messages,
                           "tools": [t["name"] for t in (tools or [])],
                           "schema": schema is not None, "effort": effort})
        if not self._replies:
            raise AssertionError("ScriptedModel ran out of replies — the pipeline made "
                                 "more model calls than the script expected")
        reply = self._replies.pop(0)
        if callable(reply):
            reply = reply(system, messages, tools, schema, effort)
        if schema is not None and reply.parsed is None and reply.text:
            reply.parsed = json.loads(reply.text)
        return reply

    @staticmethod
    def json_reply(payload: dict) -> Reply:
        return Reply(text=json.dumps(payload), parsed=payload)

    @staticmethod
    def tool_reply(name: str, arguments: dict, call_id: str = "call_1") -> Reply:
        return Reply(tool_calls=[ToolCall(id=call_id, name=name, arguments=arguments)],
                     stop_reason="tool_use")
