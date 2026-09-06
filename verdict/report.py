"""Verdict documents and the claim registry.

Two rules are enforced in code rather than left to good intentions:

1. **A verdict without honest limitations is not publishable.** The renderer
   raises if the limitations section is empty, so the cost of skipping it is a
   failure, not a slightly nicer-looking report.
2. **A registry card has three states and no fourth.** `in-progress`,
   `verdict-delivered`, `protocol-ready-data-gated`. There is deliberately no
   state for "it didn't work out", because that is a verdict, not a limbo.

The registry table in `registry/README.md` is regenerated from the cards, so the
index cannot drift away from the evidence.
"""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

CARD_STATES = ("in-progress", "verdict-delivered", "protocol-ready-data-gated")
_CARD_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


@dataclass
class VerdictReport:
    """The document model. `honest_limitations` is required, not optional."""
    title: str
    claim: str
    verdict: str
    sections: list[tuple[str, str]] = field(default_factory=list)
    honest_limitations: list[str] = field(default_factory=list)
    what_would_have_changed: str = ""
    provenance: list[str] = field(default_factory=list)

    def render_markdown(self) -> str:
        if not [x for x in self.honest_limitations if x and x.strip()]:
            raise ValueError(
                "a verdict without an honest-limitations section is not publishable "
                "(design principle 4: negative results and their boundaries are "
                "first-class content)")
        parts = [f"# {self.title}", "",
                 f"**Claim audited.** {self.claim}", "",
                 f"**Verdict.** {self.verdict}", ""]
        for heading, body in self.sections:
            parts += [f"## {heading}", "", body.strip(), ""]
        parts += ["## Honest limitations", ""]
        parts += [f"- {lim.strip()}" for lim in self.honest_limitations if lim.strip()]
        parts += [""]
        if self.what_would_have_changed.strip():
            parts += ["## What would have changed the verdict", "",
                      self.what_would_have_changed.strip(), ""]
        if self.provenance:
            parts += ["## Provenance and reproduction", ""]
            parts += [f"- {p.strip()}" for p in self.provenance if p.strip()]
            parts += [""]
        return "\n".join(parts)

    def write(self, md_path: Path | str, html: bool = True) -> Path:
        md_path = Path(md_path)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(self.render_markdown())
        if html:
            to_html(md_path)
        return md_path


def to_html(md_path: Path | str, out_path: Path | str | None = None) -> Path | None:
    """Render markdown to a self-contained HTML file (images embedded).

    Requires pandoc. Returns None — without raising — when pandoc is absent, so
    that a missing document-toolchain never invalidates a computed result.
    """
    md_path = Path(md_path)
    out_path = Path(out_path) if out_path else md_path.with_suffix(".html")
    try:
        # image paths in the document are relative to the document, not to the
        # working directory pandoc happens to be run from
        subprocess.run(["pandoc", str(md_path), "-o", str(out_path),
                        "--standalone", "--embed-resources", "--toc",
                        f"--resource-path={md_path.parent}",
                        "--metadata", f"title={md_path.stem}"],
                       check=True, capture_output=True)
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        print(f"  (HTML skipped: {e})")
        return None
    return out_path


# --------------------------------------------------------------------------
# registry
# --------------------------------------------------------------------------

def validate_card(card: dict) -> None:
    """Validate the cross-field invariants shared by every registry consumer."""
    if not isinstance(card, dict):
        raise ValueError("registry card must be a JSON object")
    for required in ("id", "state", "claim"):
        if required not in card:
            raise ValueError(f"registry card is missing '{required}'")
    if not isinstance(card["id"], str) or not _CARD_ID.fullmatch(card["id"]):
        raise ValueError("registry card id must be lower-case kebab-case")
    if card["state"] not in CARD_STATES:
        raise ValueError(f"invalid card state {card['state']!r}; allowed: {CARD_STATES}")
    if not isinstance(card["claim"], dict) or not any(
            str(card["claim"].get(k, "")).strip() for k in ("signal", "claimed_effect")):
        raise ValueError("registry card claim must describe a signal or claimed effect")
    if card["state"] == "verdict-delivered":
        v = card.get("verdict") or {}
        if not v.get("outcome"):
            raise ValueError("a delivered verdict must state an outcome")
        limitations = v.get("honest_limitations") or []
        if not isinstance(limitations, list) or not any(str(x).strip() for x in limitations):
            raise ValueError("a delivered verdict must list honest limitations")
    elif card.get("verdict"):
        raise ValueError("only a delivered card may carry a verdict")
    if card["state"] == "protocol-ready-data-gated":
        blocker = (card.get("why_not_adjudicated") or {}).get("blocker", "")
        if not str(blocker).strip():
            raise ValueError("a data-gated card must name its blocker")


def _atomic_write(path: Path, text: str) -> None:
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(text)
    tmp.replace(path)


def write_card(card: dict, registry_dir: Path | str = "registry") -> Path:
    """Validate and atomically write one claim card, then refresh the index."""
    validate_card(card)
    registry_dir = Path(registry_dir)
    registry_dir.mkdir(parents=True, exist_ok=True)
    path = registry_dir / f"{card['id']}.json"
    _atomic_write(path, json.dumps(card, indent=2) + "\n")
    refresh_index(registry_dir)
    return path


def refresh_index(registry_dir: Path | str = "registry") -> Path:
    """Regenerate the registry table in README.md from the cards on disk."""
    registry_dir = Path(registry_dir)
    readme = registry_dir / "README.md"
    cards = []
    for p in sorted(registry_dir.glob("*.json")):
        try:
            card = json.loads(p.read_text())
        except json.JSONDecodeError as exc:
            raise ValueError(f"malformed registry card {p.name}: {exc}") from exc
        validate_card(card)
        if card["id"] != p.stem:
            raise ValueError(f"registry id {card['id']!r} does not match filename {p.name!r}")
        cards.append(card)
    rows = ["| id | claim | source | state | verdict |",
            "|----|-------|--------|-------|---------|"]
    for c in cards:
        claim = c.get("claim", {})
        summary = claim.get("claimed_effect") or claim.get("signal") or ""
        source = claim.get("source", "")
        outcome = (c.get("verdict") or {}).get("outcome", "")
        if c["state"] == "protocol-ready-data-gated":
            outcome = outcome or "not adjudicable with available data"
        rows.append(f"| {_cell(c.get('id',''))} | {_cell(_clip(summary))} | "
                    f"{_cell(_clip(source))} | {_cell(c.get('state',''))} | "
                    f"{_cell(_clip(outcome))} |")
    table = "\n".join(rows)
    head = readme.read_text().split("## Cards")[0].rstrip() if readme.exists() else \
        "# Claim Registry"
    _atomic_write(readme, f"{head}\n\n## Cards\n\n{table}\n")
    return readme


def _clip(text: str, n: int = 160) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: n - 1] + "…"


def _cell(text: str) -> str:
    """Escape content that would corrupt a Markdown table row."""
    return str(text).replace("|", "\\|").replace("\n", " ")
