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
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

CARD_STATES = ("in-progress", "verdict-delivered", "protocol-ready-data-gated")


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

def write_card(card: dict, registry_dir: Path | str = "registry") -> Path:
    """Validate and write one claim card, then refresh the registry index."""
    for required in ("id", "state", "claim"):
        if required not in card:
            raise ValueError(f"registry card is missing '{required}'")
    if card["state"] not in CARD_STATES:
        raise ValueError(f"invalid card state {card['state']!r}; allowed: {CARD_STATES}")
    if card["state"] == "verdict-delivered":
        v = card.get("verdict") or {}
        if not v.get("outcome"):
            raise ValueError("a delivered verdict must state an outcome")
        if not v.get("honest_limitations"):
            raise ValueError("a delivered verdict must list honest limitations")
    registry_dir = Path(registry_dir)
    registry_dir.mkdir(parents=True, exist_ok=True)
    path = registry_dir / f"{card['id']}.json"
    path.write_text(json.dumps(card, indent=2))
    refresh_index(registry_dir)
    return path


def refresh_index(registry_dir: Path | str = "registry") -> Path:
    """Regenerate the registry table in README.md from the cards on disk."""
    registry_dir = Path(registry_dir)
    readme = registry_dir / "README.md"
    cards = []
    for p in sorted(registry_dir.glob("*.json")):
        try:
            cards.append(json.loads(p.read_text()))
        except json.JSONDecodeError:
            continue
    rows = ["| id | claim | source | state | verdict |",
            "|----|-------|--------|-------|---------|"]
    for c in cards:
        claim = c.get("claim", {})
        summary = claim.get("claimed_effect") or claim.get("signal") or ""
        source = claim.get("source", "")
        outcome = (c.get("verdict") or {}).get("outcome", "")
        if c["state"] == "protocol-ready-data-gated":
            outcome = outcome or "not adjudicable with available data"
        rows.append(f"| {c.get('id','')} | {_clip(summary)} | {_clip(source)} | "
                    f"{c.get('state','')} | {_clip(outcome)} |")
    table = "\n".join(rows)
    head = readme.read_text().split("## Cards")[0].rstrip() if readme.exists() else \
        "# Claim Registry"
    readme.write_text(f"{head}\n\n## Cards\n\n{table}\n")
    return readme


def _clip(text: str, n: int = 160) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: n - 1] + "…"
