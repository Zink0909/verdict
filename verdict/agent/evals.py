"""Scoring the agent's protocol against what human experts actually did.

The complexity case has something most agent evaluations lack: a published
ground truth. Two independent critiques of the same paper exist, and between
them they name the specific tests that settled it. An agent that reads only the
original paper — no critiques — and drafts a protocol can therefore be scored
against what the best human auditors thought to do.

The score has three parts, and the middle one matters most:

* **coverage** — checks the agent proposed that the experts also ran;
* **omissions** — checks the experts ran that the agent did not think of,
  listed individually, because the gap is the honest measure of the system's
  limits and is the thing a reader should see;
* **additions** — checks the agent proposed that the experts did not run, which
  are worth reading but are not automatically credited as insight.

Matching is by keyword, which is crude: a protocol can describe the right test
in words the checklist does not anticipate, and be scored as a miss. Every
report says so.
"""
from __future__ import annotations

import json
import re
from pathlib import Path


def load_checklist(path: str | Path) -> list[dict]:
    items = json.loads(Path(path).read_text())["items"]
    for it in items:
        for k in ("id", "label", "source", "any_of"):
            if k not in it:
                raise ValueError(f"checklist item missing {k!r}: {it}")
    return items


def _matches(text: str, patterns: list[str]) -> bool:
    t = " ".join(text.lower().split())
    return any(re.search(p.lower(), t) for p in patterns)


def score_protocol(protocol_items: list[str], checklist: list[dict]) -> dict:
    """Compare a drafted protocol with the expert checklist."""
    lines = [x for x in protocol_items if x and x.strip()]
    covered, missed = [], []
    matched_lines: set[int] = set()
    for item in checklist:
        hits = [i for i, line in enumerate(lines) if _matches(line, item["any_of"])]
        if hits:
            matched_lines.update(hits)
            covered.append({"id": item["id"], "label": item["label"],
                            "source": item["source"], "matched": lines[hits[0]]})
        else:
            missed.append({"id": item["id"], "label": item["label"], "source": item["source"]})
    additions = [lines[i] for i in range(len(lines)) if i not in matched_lines]
    by_source: dict[str, dict] = {}
    for item in checklist:
        s = by_source.setdefault(item["source"], {"total": 0, "covered": 0})
        s["total"] += 1
        s["covered"] += any(c["id"] == item["id"] for c in covered)
    return {
        "n_checklist": len(checklist), "n_protocol_lines": len(lines),
        "n_covered": len(covered), "n_missed": len(missed),
        "coverage": round(len(covered) / len(checklist), 4) if checklist else float("nan"),
        "covered": covered, "missed": missed, "additions": additions,
        "by_source": {k: {**v, "coverage": round(v["covered"] / v["total"], 4)}
                      for k, v in by_source.items()},
        "matching": "keyword; a correct test described in unanticipated words scores as a miss",
    }


def render_report(score: dict, title: str, provenance: str) -> str:
    """A markdown eval report, omissions listed rather than summarized away."""
    lines = [f"# {title}", "",
             f"Coverage: **{score['n_covered']}/{score['n_checklist']}** "
             f"({score['coverage']:.0%}) of the checks human auditors performed.", "",
             provenance.strip(), "", "## Covered", ""]
    for c in score["covered"]:
        lines.append(f"- **{c['label']}** ({c['source']}) — matched: “{_clip(c['matched'])}”")
    lines += ["", "## Missed — what the agent did not think of", ""]
    if score["missed"]:
        for m in score["missed"]:
            lines.append(f"- **{m['label']}** ({m['source']})")
    else:
        lines.append("- nothing on the checklist was missed")
    lines += ["", "## Proposed but not on the checklist", ""]
    if score["additions"]:
        for a in score["additions"][:12]:
            lines.append(f"- “{_clip(a)}”")
        lines.append("")
        lines.append("These are not automatically credited: a check the experts did not run "
                     "may be a good idea, a restatement of one they did, or padding.")
    else:
        lines.append("- none")
    lines += ["", "## Honest limitations", "",
              f"- Matching is {score['matching']}.",
              "- One checklist, one claim, one run: this measures whether the agent proposes "
              "the right tests on a case whose answer is already known, not whether it would "
              "on a fresh one.",
              "- The checklist itself is a judgment about what mattered, assembled from the "
              "published critiques after the fact.",
              "- Coverage is not correctness: proposing a test is not running it, and the "
              "execution stage is scored separately by whether its numbers survive the audit."]
    return "\n".join(lines) + "\n"


def _clip(text: str, n: int = 140) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: n - 1] + "…"
