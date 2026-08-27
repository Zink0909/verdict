"""Two rules the agent cannot talk its way past.

**The protocol is binding.** Once a protocol is pre-registered, a request to
adjust parameters, re-open a sealed block, or drop inconvenient observations is
refused with the clause it violates. This is the one place where "the agent
plays the intern and a human plays the supervisor" has teeth: the intern is not
allowed to negotiate the experiment after seeing the result.

**Prose may not invent numbers.** Every quantity in a written verdict must trace
to a value a tool returned, or to the claim being audited. `audit_numbers` finds
the ones that do not. This is the enforcement of the system's first design
principle — that the model never computes — and it is a check rather than a
promise, because a promise is not auditable.
"""
from __future__ import annotations

import re

# Requests that ask for the protocol to be bent after the fact. Deliberately
# narrow: each pattern describes an action on the *experiment*, not a topic.
_TUNING_PATTERNS: list[tuple[str, str]] = [
    (r"\btun(e|ing)\b.{0,40}\b(until|so that|to get|to make)\b", "parameters are fixed in advance"),
    (r"\b(adjust|change|tweak|raise|lower)\b.{0,40}\b(threshold|parameter|window|cutoff|penalty)\b.{0,40}\b(until|so that|to get|to make)\b",
     "parameters are fixed in advance"),
    (r"\b(try|test)\b.{0,30}\b(other|different|more)\b.{0,20}\b(values?|parameters?|settings?|configurations?)\b.{0,30}\b(until|till)\b",
     "parameters are fixed in advance"),
    (r"\b(until|till)\b.{0,30}\b(significant|positive|works?|profitable)\b", "the result is not a target"),
    (r"\bmake (it|the (result|alpha|sharpe))\b.{0,30}\b(significant|positive|work|better|look good)\b",
     "the result is not a target"),
    (r"\bcherry.?pick|\bhand.?pick\b.{0,30}\b(result|window|sample|period)", "no selecting on the outcome"),
    (r"\b(drop|remove|exclude|ignore)\b.{0,40}\b(bad|worst|inconvenient|losing|outlier)\b.{0,20}\b(month|year|trade|observation|period|name)s?\b",
     "the sample is fixed in advance"),
    (r"\b(re-?open|re-?run|look at|peek at|check)\b.{0,30}\b(sealed|held.?out|holdout)\b",
     "a sealed block opens once"),
    (r"\b(skip|drop|leave out|omit)\b.{0,30}\b(cost|friction|spread|limitation)s?\b",
     "costs and limitations are not optional"),
]


class ProtocolViolation(RuntimeError):
    """Raised when a request would break the pre-registered protocol."""

    def __init__(self, request: str, clause: str, quote: str):
        self.clause, self.quote = clause, quote
        super().__init__(
            f"Refused: this asks me to change the experiment after seeing its result "
            f"(\"{quote}\"). The pre-registered protocol says {clause}. If the protocol "
            f"itself is wrong, revise and re-register it before running anything — that "
            f"is a different, honest action, and it goes in the record.")


def check_request(request: str, raise_on_violation: bool = True) -> dict | None:
    """Screen an instruction against the protocol. Returns the violation, or None."""
    text = " ".join(request.lower().split())
    for pattern, clause in _TUNING_PATTERNS:
        m = re.search(pattern, text)
        if m:
            found = {"pattern": pattern, "clause": clause, "quote": m.group(0)}
            if raise_on_violation:
                raise ProtocolViolation(request, clause, m.group(0))
            return found
    return None


# --------------------------------------------------------------- numbers ----

_NUMBER = re.compile(r"-?\d[\d,]*\.?\d*")


def _scan(text: str) -> list[tuple[float, int]]:
    """Every numeral with the precision it was written to — rounding needs both."""
    out: list[tuple[float, int]] = []
    for raw in _NUMBER.findall(text or ""):
        clean = raw.replace(",", "")
        try:
            value = float(clean)
        except ValueError:
            continue
        decimals = len(clean.split(".")[1]) if "." in clean else 0
        out.append((value, decimals))
    return out


def extract_numbers(text: str) -> list[float]:
    """Every numeral in a piece of prose, thousands separators handled."""
    return [v for v, _ in _scan(text)]


def _supported(value: float, decimals: int, allowed: list[float],
               rel_tol: float, abs_tol: float) -> bool:
    """Does a written number match a computed one?

    Rounding is judged at the precision the number was *written* to — "-0.09" is
    a faithful rendering of -0.0855, while "0.9" is not — because a relative
    tolerance is the wrong instrument here: it is too tight on small magnitudes
    and too loose on large ones. Percentages count either way round, with the
    written precision shifted by the two decimal places the conversion moves.
    """
    for candidate, dp in ((value, decimals), (value / 100.0, decimals + 2),
                          (value * 100.0, max(decimals - 2, 0))):
        for a in allowed:
            if round(a, dp) == round(candidate, dp):
                return True
            if abs(candidate - a) <= max(abs_tol, rel_tol * abs(a)):
                return True
    return False


def audit_numbers(draft: str, allowed: list[float], context: str = "",
                  rel_tol: float = 0.02, abs_tol: float = 1e-6) -> dict:
    """Find numbers in a written verdict that no tool result or source claim supports.

    `allowed` is the values the tools returned; `context` is the claim card and
    protocol text, whose numbers came from the source rather than from the model.
    Rounding is permitted at the precision the figure was written to, and a
    percentage may be written either way; a number that matches nothing is
    reported, not silently accepted.

    What this cannot catch: a correct number described wrongly. "the R-squared is
    0.004, which is negative" passes, because the figure is real and only the
    sentence around it is false. The audit bounds fabrication, not interpretation.
    """
    allow = list(allowed) + extract_numbers(context)
    written = _scan(draft)
    unsupported = [v for v, dp in written if not _supported(v, dp, allow, rel_tol, abs_tol)]
    return {"n_numbers": len(written),
            "n_allowed_values": len(allow),
            "unsupported": unsupported,
            "clean": not unsupported}
