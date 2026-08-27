"""Form definitions and card assembly for the working surface.

This lives in the library rather than in the interface for one reason: it can be
tested. The interface collects strings; everything that decides whether those
strings amount to a registrable claim happens here, behind the same validation
the rest of the system uses — so a claim entered through a form is held to the
identical standard as one written by hand or drafted by the agent.

In particular a protocol with no kill criteria is rejected here exactly as it is
everywhere else. The screen cannot be the place where the discipline is softened
to make the form easier to submit.
"""
from __future__ import annotations

import re

from .agent.schema import ClaimCard, Protocol

# (key, label, help text, render as a multi-line box)
CLAIM_FIELDS: list[tuple[str, str, str, bool]] = [
    ("signal", "The signal or rule",
     "Precise enough that someone could rebuild it from your description alone.", True),
    ("universe", "Universe", "What it is applied to.", False),
    ("frequency", "Frequency", "Rebalancing or forecast frequency.", False),
    ("claimed_effect", "The claimed effect",
     "With the magnitude the source states, not your estimate of it.", True),
    ("sample", "Sample", "The period and size the claim rests on.", False),
    ("source", "Source", "Author, year, venue — or 'practitioner thesis' if unpublished.", False),
    ("data_needs", "Data needed — one per line",
     "What you would have to have in hand to test this at all.", True),
]

PROTOCOL_FIELDS: list[tuple[str, str, str, bool]] = [
    ("data_requirements", "Data requirements — one per line",
     "Including how it must be constructed: point-in-time, survivorship-free, and so on.",
     True),
    ("splits", "Splits",
     "How the sample is divided in time, and what is sealed until the end.", True),
    ("benchmarks", "Benchmarks — one per line",
     "What the claim must beat to count as new information. A simple alternative that "
     "would produce the same result belongs here.", True),
    ("cost_model", "Cost model", "How trading frictions are charged, and at what levels.", True),
    ("diagnostics", "Diagnostics — one per line",
     "What you will run if the answer is no, to find the mechanism rather than stopping "
     "at 'it does not work'.", True),
    ("robustness", "Robustness — one per line",
     "What gets perturbed to check the conclusion is not an artefact of one arbitrary "
     "choice.", True),
    ("kill_criteria", "Kill criteria — one per line · REQUIRED",
     "Results that would falsify the claim. Not results that would disappoint you. If "
     "you cannot write one, the claim is not testable and that is the finding.", True),
    ("rationale", "Rationale",
     "Why this protocol tests this claim and not a more convenient one.", True),
]

_LIST_FIELDS = {"data_needs", "data_requirements", "benchmarks", "diagnostics",
                "robustness", "kill_criteria"}
_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _split(value) -> list[str]:
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    return [x.strip() for x in str(value or "").splitlines() if x.strip()]


def normalize(raw: dict, fields: list[tuple[str, str, str, bool]]) -> dict:
    """Turn form strings into the shape the schemas expect."""
    out = {}
    for key, *_ in fields:
        out[key] = _split(raw.get(key)) if key in _LIST_FIELDS else (raw.get(key) or "").strip()
    return out


def build_card(claim_raw: dict, protocol_raw: dict, card_id: str, title: str,
               data_available: bool, blocker: str = "") -> dict:
    """Validate a filled-in form and assemble a registry card.

    Raises `ValueError` with a readable message for anything that would make the
    card dishonest: a missing field, an unusable id, or — the one that matters —
    a protocol with no kill criteria.
    """
    card_id = (card_id or "").strip()
    if not _ID.match(card_id):
        raise ValueError("Register id must be lower-case words joined by hyphens, "
                         "for example 'lazy-prices-10k-changes'.")
    if not (title or "").strip():
        raise ValueError("Give the claim a short plain-English title — it is what a reader "
                         "sees first on the register.")

    claim = ClaimCard.from_dict(normalize(claim_raw, CLAIM_FIELDS))
    protocol = Protocol.from_dict(normalize(protocol_raw, PROTOCOL_FIELDS))

    if not data_available and not (blocker or "").strip():
        raise ValueError("A data-gated card must say what the blocker is. 'The data is not "
                         "available' is not a blocker; what specifically is missing, and "
                         "what would change it?")

    card: dict = {
        "id": card_id,
        "title": title.strip(),
        "state": "in-progress" if data_available else "protocol-ready-data-gated",
        "claim": claim.to_dict(),
        "protocol": protocol.to_dict(),
        "verdict": None,
    }
    if not data_available:
        card["why_not_adjudicated"] = {
            "blocker": blocker.strip(),
            "detail": "The protocol is complete and pre-registered; executing it needs data "
                      "that is not in hand.",
            "what_would_change_it": "Assembling and auditing that data, at which point this "
                                    "card moves to in-progress.",
        }
    return card
